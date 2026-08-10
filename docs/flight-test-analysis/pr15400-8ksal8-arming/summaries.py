#!/usr/bin/env python3
"""The rounded summary forms quoted in prose, and how each is derived.

The other scripts print per-log measurements. Prose needs ranges, group counts
and "about" figures, and those are exactly the places where a number can drift
away from its evidence unnoticed. Every summary phrase used in ANALYSIS.md, in
the ADRC-028 tracker paragraph and in the reply is generated here, next to the
underlying values and the rounding rule that produced it.

Run with --check for a regression guard over the prose. It is a guard, NOT a
proof, and the difference matters: it catches the mutation classes listed in
check(), and a determined edit can still slip past it - rewording the
non-numeric part of a phrase, flipping a sign, or writing a number in a form
the pattern does not recognise. Treat a green run as "no known class of drift
detected", never as "the text is verified".
"""
import os

import numpy as np

from common import LOGS, headers, load, time_s, gyro, motors, fs_nominal
from frequency import lomb_peak, peak_spacing, growth_window
from provenance import events, FEATURE_AIRMODE_BIT

DEDLIKE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'pr15400-dedlike-mamba')
GROUND = ['b8_Airmode_on_ADRC_btfl_001', 'b9_Airmode_on_ADRC_btfl_002',
          'b9_Airmode_on_PID_btfl_004', 'b9_Airmode_switch_PID_btfl_005']


# Which artifact each phrase must appear in, verbatim. ANALYSIS is the write-up,
# TRACKER the ADRC-028 paragraph, REPLY the draft answer to the reporter.
ANALYSIS, TRACKER, REPLY = 'ANALYSIS.md', 'ADRC_REMEDIATION_TRACKER.md', 'DRAFT_reply.md'
PHRASES = []


def full(x):
    """Shortest round-trip decimal for a float - the full computed precision."""
    return repr(float(x))


def line(phrase, derivation, artifacts=(ANALYSIS,)):
    """Record and print one prose phrase together with how it was produced.

    `artifacts` names every text that must contain this exact phrase. Requiring
    the specific file, rather than "somewhere in the union", is what makes a
    mutation in one of them fail the check.
    """
    PHRASES.append((phrase, tuple(artifacts)))
    print(f'  "{phrase}"')
    print(f'      from: {derivation}')


def check(sources):
    """A regression guard over the prose, in two directions.

    Forward: every phrase printed above appears verbatim in each artifact that
    is declared to use it, and no near-variant of it appears anywhere in that
    artifact - the phrase is wildcarded over its numbers and every match of that
    shape must be the phrase itself. Whitespace is normalised because prose is
    hard-wrapped; nothing else is.

    Reverse: every measured value in the prose is produced by one of the scripts
    in this directory, compared as whole tokens rather than substrings.

    Known blind spots, stated rather than papered over: rewording the
    non-numeric part of a phrase takes it out of its own family pattern; a sign
    change or scientific notation is not recognised as a measured value; and a
    number that legitimately appears in some unrelated script output satisfies
    the reverse direction wherever it is used. This catches drift, not a
    determined edit.
    """
    import contextlib
    import io
    import re

    blobs = {}
    for key, path in sources.items():
        try:
            text = open(path).read()
        except OSError as exc:
            print(f'  cannot read {path}: {exc}')
            return 1
        if key == TRACKER:
            # only the paragraph this corpus owns; the rest of the tracker is
            # other entries with their own evidence
            start = text.find('**A third ground event')
            end = text.find('Instrumentation defect found alongside', start)
            if start < 0 or end < 0:
                print(f'  cannot locate the ADRC-028 paragraph in {path}')
                return 1
            text = text[start:end]
        blobs[key] = ' '.join(text.split())

    bad = 0
    print('\n# Forward: each phrase must appear verbatim where it is used\n')
    for phrase, artifacts in PHRASES:
        norm = ' '.join(phrase.split())
        for want in artifacts:
            if want not in blobs:
                bad += 1
                print(f'  ABSENT  [{want}] not supplied, cannot verify: {phrase}')
                continue
            blob = blobs[want]
            if norm not in blob:
                bad += 1
                print(f'  MISSING [{want}] {phrase}')
                continue
            # Presence is not enough: a phrase used twice can be mutated in one
            # place and still be found in the other. Rebuild the phrase as a
            # pattern with its numbers wildcarded, and require every occurrence
            # of that shape to be the exact phrase.
            family = re.escape(norm)
            family = re.sub(r'\\?\d+(?:\\?\.\d+)?', r'\\d+(?:\\.\\d+)?', family)
            variants = {m for m in re.findall(family, blob) if m != norm}
            if variants:
                bad += len(variants)
                print(f'  VARIANT [{want}] {phrase}  <- also found: '
                      + ', '.join(sorted(variants)))
            else:
                n = blob.count(norm)
                print(f'  ok      [{want}] {phrase}' + (f'  (x{n})' if n > 1 else ''))

    missing_artifacts = {a for _, arts in PHRASES for a in arts} - set(blobs)
    if missing_artifacts:
        print(f'\n  all three artifacts are required; missing: '
              f'{", ".join(sorted(missing_artifacts))}')

    print('\n# Reverse: every measured value in the prose must come from a script\n')
    corpus = io.StringIO()
    with contextlib.redirect_stdout(corpus):
        for mod in ('provenance', 'ground_events', 'frequency', 'flight003',
                    'dedlike_compare'):
            __import__(mod).main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _ in PHRASES)

    # What counts as a measured value: a decimal, an integer of three digits or
    # more, an integer carrying a unit, or a cell count like 4S. Bare small
    # integers (section numbers, list markers, "two of three") are prose.
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|°/s|frames|g\b))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'          # any decimal
        r'|(?<![\w.])\d{3,}(?![\w.])'            # 3+ digit integer
        r'|(?<![\w.])\d{1,2}S(?![\w])'           # cell count
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')  # small integer with a unit

    # The haystack is tokenised loosely - a number in stdout is often followed by
    # a unit or a full stop ("1.003g", "524272.", "1000..1000") and must still be
    # recognised. Tokens are then compared for equality, never as substrings, so
    # "0.356" is not satisfied by "0.3562" appearing somewhere in the output.
    token = re.compile(r'(?<![\w.])\d{1,2}S(?![\w])|(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    # Values that are not measurements of this corpus and are labelled in place.
    ALLOWED = {
        '15400', '2026', '5231336333', '5235424105',   # PR, dates, comment ids
        '87.017', '612', '65', '72', '73',             # external, labelled in place
        '029', '028', '024', '021', '020',             # tracker entry numbers
        '0.5', '1.0',        # mixer.c constants quoted from source, not measured
    }

    for name, blob in blobs.items():
        prose = re.sub(r'`[^`]*\.(c|h|md|py)[^`]*`', '', blob)
        prose = re.sub(r'\d{4}-\d{2}-\d{2}', '', prose)          # dates
        unexplained = sorted({n for n in measured.findall(prose)
                              if n not in known and n not in ALLOWED})
        if unexplained:
            bad += len(unexplained)
            print(f'  UNEXPLAINED in {name}: {", ".join(unexplained)}')
        else:
            print(f'  ok      {name}: every measured value traced to script output')

    print(f'\n  {bad} problem(s).')
    return 1 if bad else 0


def main():
    print('# Summary phrases used in prose, with their derivation\n')

    # --- saved frame rate
    rates = [fs_nominal(load(s)) for _, s, _, _ in LOGS]
    line(f'{min(rates):.0f}\u2013{max(rates):.0f} frames/s saved',
         f'per-log mean rates {", ".join(full(r) for r in rates)}; '
         f'endpoints rounded to the NEAREST whole frame/s (not outward: outward '
         f'would give {int(np.floor(min(rates)))}\u2013{int(np.ceil(max(rates)))})',
         artifacts=(ANALYSIS,))

    # --- unlogged head interval
    gaps = []
    for _, stem, _, _ in LOGS:
        d = load(stem)
        ev = events(stem)
        sync = next((e['time'] for e in ev if 'Sync' in e.get('name', '')), None)
        gaps.append((d['time (us)'][0] - sync) / 1000.0)
    ground_gaps = gaps[:3] + [gaps[4]]
    line(f'the first {min(ground_gaps):.1f}\u2013{max(ground_gaps):.1f} ms are not recorded',
         f'per-log gaps (ground logs) {", ".join(full(g) for g in ground_gaps)} ms; '
         f'endpoints rounded to the nearest 0.1 ms', artifacts=(ANALYSIS, REPLY))
    print(f'      (all five, adding log 003 at {full(gaps[3])} ms, would be '
          f'{min(gaps):.1f}\u2013{max(gaps):.1f} ms - not used in prose)')

    # --- the Airmode activation threshold, quoted in prose from the header
    thr = float(headers(LOGS[0][1])['airmode_activate_throttle'])
    print()
    line(f'`airModeActivateThreshold` ({thr:.0f} % here)',
         f'airmode_activate_throttle from the header, identical in all five logs',
         artifacts=(ANALYSIS,))
    line(f'{thr:.0f} % on your craft',
         f'the same header field, addressed to the reporter', artifacts=(REPLY,))

    # --- Airmode outcome split
    on, off, on_fail, off_fail = [], [], 0, 0
    for _, stem, _, _ in LOGS:
        feat = int(headers(stem).get('features', '0')) & (1 << FEATURE_AIRMODE_BIT)
        dd = load(stem)
        ground = dd['setpoint[3]'] == 0
        failed = bool((motors(dd).max(axis=0)[ground] >= 2047).any())
        (on if feat else off).append(stem)
        if feat and failed:
            on_fail += 1
        if (not feat) and failed:
            off_fail += 1
    print()
    line(f'{on_fail} of the {len(on)} feature-enabled logs failed and '
         f'{off_fail} of the {len(off)} feature-off ones did',
         f'"failed" = any motor reaches 2047 in any saved frame where setpoint[3] == 0 '
         f'(that is the literal criterion - it is not a ground-contact test and it is '
         f'not restricted to the initial arm window; in this corpus the two coincide, '
         f'since log 003 has a 1.94 s zero-command prefix and its 550 rail frames all '
         f'fall outside it). All five logs are counted because each begins with an arm; '
         f'003 is the one that went on to fly. Enabled {[s[-3:] for s in on]}, '
         f'off {[s[-3:] for s in off]}', artifacts=(ANALYSIS, TRACKER, REPLY))
    n_ground_fail = on_fail + off_fail
    words = {2: 'Two', 3: 'Three', 4: 'Four', 5: 'five'}
    line(f'{words.get(on_fail + off_fail, on_fail + off_fail)} arms of '
         f'{words.get(len(LOGS), len(LOGS))}',
         f'{on_fail + off_fail} of the five logs reach the motor rail in a frame with '
         f'setpoint[3] == 0', artifacts=(ANALYSIS, TRACKER))

    # --- frequency agreement
    print()
    rows = []
    for stem in GROUND[:2]:
        d = load(stem)
        t, gu = time_s(d), gyro(d, filtered=False)
        peak = np.abs(gyro(d)).max(axis=0)
        win = growth_window(t, peak)
        for ax, name in ((0, 'roll'), (1, 'pitch')):
            x, tw = gu[ax][win], t[win]
            ps = peak_spacing(tw, x)
            rows.append((stem[-3:], name, lomb_peak(tw, x), ps[0] if ps else None))
    paired = [abs(l - p) for _, _, l, p in rows if p is not None]
    vals = [v for _, _, l, p in rows for v in ((l, p) if p is not None else (l,))]
    line(f'agree within {max(paired):.2f} Hz per row',
         f'largest per-row |Lomb - peak spacing| over the four roll/pitch rows is '
         f'{full(max(paired))}, rounded to the nearest 0.01 Hz; per row: '
         + ', '.join(f'{s} {n} {full(abs(l-p))}' for s, n, l, p in rows if p is not None),
         artifacts=(ANALYSIS, REPLY))
    line(f'about {np.median(vals):.0f} Hz',
         f'roll and pitch; all eight timestamp-honest values are '
         + ', '.join(full(v) for v in sorted(vals))
         + f'; median {full(np.median(vals))}, rounded to the nearest whole Hz',
         artifacts=(ANALYSIS, TRACKER, REPLY))
    line(f'span {min(vals):.2f}\u2013{max(vals):.2f} Hz',
         f'same eight values; endpoints rounded to the nearest 0.01 Hz',
         artifacts=(ANALYSIS, REPLY))

    yaw = []
    for stem in GROUND[:2]:
        d = load(stem)
        t, gu = time_s(d), gyro(d, filtered=False)
        win = growth_window(t, np.abs(gyro(d)).max(axis=0))
        yaw.append(lomb_peak(t[win], gu[2][win]))
    line(f'yaw carries a component near {np.mean(yaw):.0f} Hz',
         f'Lomb-Scargle yaw peaks {full(yaw[0])} and {full(yaw[1])} Hz, mean '
         f'{full(np.mean(yaw))}, rounded to the nearest whole Hz '
         f'(peak spacing returns nothing usable on this axis)',
         artifacts=(ANALYSIS, REPLY))

    # --- current
    print()
    amps = [load(s)['amperageLatest (A)'].max() for s in GROUND[:2]]
    line(f'{min(amps):.0f}\u2013{max(amps):.1f} A',
         f'peak current {full(amps[0])} and {full(amps[1])} A in the two runaways; '
         f'lower endpoint rounded to the nearest whole amp, upper to the nearest '
         f'0.1 A - deliberately asymmetric so neither endpoint overstates the range',
         artifacts=(ANALYSIS,))

    # --- dedlike yaw frequency range
    print()
    from dedlike_compare import DEDLIKE_STEM
    from frequency import welch_peak
    d = load(DEDLIKE_STEM, basedir=DEDLIKE_DIR)
    t, gu = time_s(d), gyro(d, filtered=False)
    win = growth_window(t, np.abs(gyro(d)).max(axis=0))
    fs = fs_nominal(d)
    fw, _ = welch_peak(t[win], gu[2][win], fs, 128)
    fl = lomb_peak(t[win], gu[2][win])
    bw = welch_peak(t[win], gu[2][win], fs, 128)[1]
    line(f'Lomb {fl:.2f}, Welch/128 {fw:.2f} Hz (bin width {bw:.2f} Hz)',
         f'@dedlike yaw; full precision Lomb {full(fl)}, Welch/128 {full(fw)}, bin '
         f'{full(bw)}, all rounded to the nearest 0.01 Hz, on a {full(t[-1])} s record; '
         f'a band, not a point estimate', artifacts=(ANALYSIS, TRACKER, REPLY))

    # --- runaway record lengths
    spans = [time_s(load(s))[-1] for s in GROUND[:2]]
    line(f'{min(spans):.2f}\u2013{max(spans):.2f} s',
         f'@8ksal8 record lengths {full(spans[0])} and {full(spans[1])} s, endpoints '
         f'rounded to the nearest 0.01 s', artifacts=(REPLY,))

    print('\nNot derivable from any log, and labelled as external where used:')
    print('  "65 mm" - the craft model, from the reporter and the header craft name AIR65 R')
    print('  "612 g with battery" and "5-inch" - @dedlike, PR #15400 comment 5231336333')
    print('''       of 2026-08-09, which reads: 5" / 612g with battery. The log itself''')
    print('       carries only the board name MAMBAF722.')
    print('  "87.017 ms" - reconstructed in pr15400-dedlike-mamba/, not recomputed here')
    print('\nCell counts: dedlike_compare.py applies the autoDetectCellCount arithmetic to')
    print('the header vbatref. It differs from the firmware path in three ways, all stated')
    print('in its output: the firmware divides the filtered voltage rather than this')
    print('unfiltered snapshot, it caps at MAX_AUTO_DETECT_CELL_COUNT = 8, and a non-zero')
    print('forceBatteryCellCount would bypass autodetect without appearing in the header.')


if __name__ == '__main__':
    import sys
    main()
    if '--check' in sys.argv:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(here))
        sources = {
            ANALYSIS: os.path.join(here, 'ANALYSIS.md'),
            TRACKER: os.path.join(root, 'ADRC_REMEDIATION_TRACKER.md'),
        }
        if 'ARMING_REPLY' in os.environ:
            sources[REPLY] = os.environ['ARMING_REPLY']
        sys.exit(check(sources))

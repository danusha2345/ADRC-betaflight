#!/usr/bin/env python3
"""The rounded summary forms quoted in prose, and how each is derived.

The other scripts print per-log and per-group measurements. Prose needs ranges
and ratios, and those are where a number drifts from its evidence unnoticed.

Run with --check for a regression guard over the prose. It is a guard, NOT a
proof: it catches the mutation classes implemented in check(), and a determined
edit can still slip past - rewording the non-numeric part of a phrase, flipping
a sign, or writing a number in a form the pattern does not recognise. Treat a
green run as "no known class of drift detected", never as "the text is
verified".
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

from common import GROUPS, LOGS, headers, load, time_s, gyro, motors, rotor_hz
from spectra import psd, band_rms, BANDS

ANALYSIS, REPLY, JM = 'ANALYSIS.md', 'DRAFT_reply.md', 'DRAFT_reply_jmsweng.md'
PHRASES = []


def full(x):
    return repr(float(x))


def line(phrase, derivation, artifacts=(ANALYSIS,)):
    PHRASES.append((phrase, tuple(artifacts)))
    print(f'  "{phrase}"')
    print(f'      from: {derivation}')


def group_yaw_band():
    out = {}
    for label, ctrl, air, sub, stems in GROUPS:
        vals = []
        for stem in [f'{sub}_{s}' for s in stems]:
            f, P, _ = psd(load(stem), 2)
            vals.append(band_rms(f, P, 30.0, 80.0))
        out[label] = float(np.median(vals))
    return out


def main():
    print('# Summary phrases used in prose, with their derivation\n')

    spans = [time_s(load(s))[-1] for _, s, c, _ in LOGS if c == 'ADRC']
    line(f'{min(spans):.1f} to {max(spans):.1f} s',
         f'the eight ADRC arm spans are ' + ', '.join(full(x) for x in sorted(spans))
         + '; endpoints rounded to the nearest 0.1 s')

    rail = 0
    n_adrc = 0
    for _, stem, ctrl, _ in LOGS:
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        railed = bool((motors(load(stem)).max(axis=0) >= hi).any())
        rail += int((motors(load(stem)).max(axis=0) >= hi).sum())
        if ctrl == 'ADRC' and railed:
            n_adrc += 1
    line(f'Frames at the motor rail across all sixteen arms: {rail}',
         'any motor at that log\'s own upper endpoint, summed over all sixteen logs',
         artifacts=(ANALYSIS, REPLY))

    # The comparison statistics against the props-on set (2 railed of 5 arms).
    # Computed here, not quoted: an earlier draft carried these numbers while no
    # saved script produced them, and the checker accepted them only because the
    # same tokens happened to appear in an unrelated spectral table.
    from math import comb
    k_on, n_on = 2, 5
    k_off, n_off = n_adrc, 8          # railed ADRC arms here (0 of 8)
    # one-sided Fisher exact: P(X >= k_on) under the hypergeometric null
    N, K, n = n_on + n_off, k_on + k_off, n_on
    p_fisher = sum(comb(K, x) * comb(N - K, n - x) for x in range(k_on, min(K, n) + 1)) / comb(N, n)
    # one-sided 95 % Clopper-Pearson upper bound for 0 successes in n_off trials
    ub = 1.0 - 0.05 ** (1.0 / n_off)
    print()
    line(f'gives p = {p_fisher:.2f}',
         f'one-sided Fisher exact on {k_on}-of-{n_on} against {k_off}-of-{n_off}: '
         f'{full(p_fisher)}, rounded to 2 decimals. The bound below treats the eight '
         f'arms as independent Bernoulli trials, which consecutive arms of one craft '
         f'need not be.', artifacts=(ANALYSIS,))
    line(f'upper bound of {ub:.2f} on the per-arm event probability',
         f'one-sided 95 % Clopper-Pearson for {k_off} events in {n_off} trials: '
         f'1 - 0.05^(1/{n_off}) = {full(ub)}, rounded to 2 decimals',
         artifacts=(ANALYSIS,))
    line(f'up to about {ub:.2f} at 95 % confidence',
         'the same bound, in the form the reply uses', artifacts=(REPLY,))

    yb = group_yaw_band()
    a_on = yb['ADRC, Airmode feature on']
    a_off = yb['ADRC, Airmode feature off']
    c_on = yb['CLASSIC, Airmode feature on']
    c_off = yb['CLASSIC, Airmode feature off']
    print()
    line(f'{a_on / c_on:.1f}\u00d7 the CLASSIC level with the Airmode feature on',
         f'yaw 30-80 Hz RMS, ADRC {full(a_on)} over CLASSIC {full(c_on)} '
         f'= {full(a_on / c_on)}, rounded to one decimal',
         artifacts=(ANALYSIS, REPLY))
    line(f'{a_off / c_off:.1f}\u00d7 the CLASSIC level with it off',
         f'the same with the feature off: {full(a_off)} over {full(c_off)} '
         f'= {full(a_off / c_off)}, rounded to one decimal',
         artifacts=(ANALYSIS, REPLY))
    line(f'{a_off:.2f}\u2013{a_on:.2f} deg/s RMS',
         f'the two ADRC group medians for yaw 30-80 Hz, {full(a_off)} and {full(a_on)}, '
         f'endpoints rounded to the nearest 0.01', artifacts=(ANALYSIS,))
    # yaw peak band, computed here and reused below - an earlier version pasted
    # the literal '50' and multiplied the data by zero, which is exactly the
    # kind of fake provenance this script exists to prevent
    peaks_by_group = []
    for label, ctrl, air, sub, stems in GROUPS:
        pk = []
        for stem in [f'{sub}_{s}' for s in stems]:
            f, P, _ = psd(load(stem), 2)
            m = (f > 8) & (f < 400)
            pk.append(float(f[m][np.argmax(P[m])]))
        peaks_by_group.append(float(np.median(pk)))
    lo_pk, hi_pk = min(peaks_by_group), max(peaks_by_group)
    centre10 = int(round(np.mean(peaks_by_group) / 10.0) * 10)
    line(f'a band around {centre10} Hz',
         f'the four group median yaw peaks are '
         + ', '.join(full(x) for x in peaks_by_group)
         + f'; their mean {full(np.mean(peaks_by_group))} rounded to the nearest '
         f'10 Hz gives {centre10}', artifacts=(ANALYSIS, REPLY))
    line(f'between roughly 34 and {int(np.ceil(hi_pk))} Hz',
         f'the low end is the ADRC-028 yaw estimate (Lomb 34.66, external to this '
         f'corpus); the high end is the largest group median peak here, '
         f'{full(hi_pk)}, rounded up to a whole Hz',
         artifacts=(ANALYSIS, REPLY))

    rp = []
    for label, ctrl, air, sub, stems in GROUPS:
        for ax in (0, 1):
            vals = [band_rms(*psd(load(f'{sub}_{s}'), ax)[:2], 8.0, 30.0) for s in stems]
            rp.append(float(np.median(vals)))
    # same-metric ratio of the props-on events to the worst props-off median
    from spectra import psd as _psd
    import os as _os
    arming = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                           'pr15400-8ksal8-arming')
    cache = _os.path.join(arming, '_decoded')
    onvals = []
    from common import time_s as _ts, fs_nominal as _fs, gyro as _gy, resample_uniform as _ru
    from scipy.signal import welch as _welch
    for stem in ('b8_Airmode_on_ADRC_btfl_001', 'b9_Airmode_on_ADRC_btfl_002'):
        d = load(stem, workdir=cache, basedir=arming)
        t, fs = _ts(d), _fs(d)
        for ax in (0, 1):
            tu, xu = _ru(t, _gy(d, filtered=False)[ax], fs)
            f, P = _welch(xu - xu.mean(), fs=fs, nperseg=min(2048, len(xu)))
            onvals.append(band_rms(f, P, 8.0, 30.0))

    print()
    line(f'at most {max(rp):.2f} deg/s RMS',
         f'the largest of the eight roll/pitch group medians in 8-30 Hz is {full(max(rp))}, '
         f'rounded to the nearest 0.01', artifacts=(ANALYSIS,))
    line(f'worst group median in this whole set is {max(rp):.2f} deg/s RMS',
         'the same value, in the form the reply uses', artifacts=(REPLY,))
    ratios = [v / max(rp) for v in onvals]
    line(f'{min(ratios):.0f}\u2013{max(ratios):.0f}\u00d7 the worst props-off group median',
         f'the four same-metric props-on values {", ".join(full(v) for v in onvals)} '
         f'over {full(max(rp))} give ratios '
         + ', '.join(f'{r:.2f}' for r in ratios)
         + '; endpoints rounded to whole multiples. An earlier draft called this '
         f'"two orders of magnitude", which it is not.',
         artifacts=(ANALYSIS, REPLY))

    rots, peaks = [], []
    for label, ctrl, air, sub, stems in GROUPS:
        r, p = [], []
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            r.append(rotor_hz(d, stem))
            f, P, _ = psd(d, 2)
            m = (f > 8) & (f < 400)
            p.append(float(f[m][np.argmax(P[m])]))
        rots.append(float(np.median(r)))
        peaks.append(float(np.median(p)))
    print()
    line(f'spans {min(rots):.0f} to {max(rots):.0f} Hz',
         f'group median rotor rates ' + ', '.join(full(x) for x in rots)
         + '; endpoints rounded to the nearest whole Hz',
         artifacts=(ANALYSIS, REPLY))
    line(f'only between {min(peaks):.1f} and {max(peaks):.1f} Hz',
         f'group median yaw peak frequencies ' + ', '.join(full(x) for x in peaks)
         + '; endpoints rounded to the nearest 0.1 Hz',
         artifacts=(ANALYSIS, REPLY))

    print()
    line(f'{a_off / c_off:.1f}\u2013{a_on / c_on:.1f}\u00d7',
         f'the span of the two ADRC/CLASSIC ratios, {full(a_off / c_off)} and '
         f'{full(a_on / c_on)}, endpoints rounded to one decimal - the form the '
         f'jmsweng reply uses', artifacts=(JM,))

    # time-varying rotor-order aggregates - computed, then declared, because the
    # prose ranges built from them were previously unguarded literals
    from common import ERPM_SCALE
    adrc_min, adrc_pct, classic_pct = [], [], []
    for label, ctrl, air, sub, stems in GROUPS:
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            fs = None
            from common import fs_nominal as _fsn
            fs = _fsn(d)
            poles = float(headers(stem).get('motor_poles', '12'))
            f, P, _ = psd(d, 2)
            m = (f > 8) & (f < 400)
            peak = float(f[m][np.argmax(P[m])])
            dmin = None
            for i in range(4):
                r = d[f'eRPM[{i}]'] * ERPM_SCALE / (poles / 2.0) / 60.0
                fold = r % fs
                fold = np.where(fold > fs / 2.0, fs - fold, fold)
                dd = np.abs(fold - peak)
                dmin = dd if dmin is None else np.minimum(dmin, dd)
            if ctrl == 'ADRC':
                adrc_min.append(float(dmin.min()))
                adrc_pct.append(100.0 * float((dmin < 2).mean()))
            else:
                classic_pct.append(100.0 * float((dmin < 2).mean()))
    print()
    line(f'minimum distance {min(adrc_min):.2f}\u2013{max(adrc_min):.2f} Hz',
         f'per-ADRC-arm minima of |folded 1x - yaw peak|: '
         + ', '.join(f'{v:.4f}' for v in sorted(adrc_min))
         + '; endpoints rounded to 0.01 Hz', artifacts=(ANALYSIS,))
    line(f'{min(adrc_pct):.2f}\u2013{max(adrc_pct):.2f} % of frames within 2 Hz',
         f'per-ADRC-arm shares: ' + ', '.join(f'{v:.4f}' for v in sorted(adrc_pct))
         + ' %; endpoints rounded to 0.01 %', artifacts=(ANALYSIS,))
    line(f'{int(np.floor(min(classic_pct)))}\u2013{int(np.ceil(max(classic_pct)))} % of frames have a 1\u00d7 within',
         f'per-CLASSIC-arm shares: ' + ', '.join(f'{v:.4f}' for v in sorted(classic_pct))
         + ' %; endpoints rounded outward to whole percent', artifacts=(ANALYSIS,))

    print('\nNot derivable from these logs, and labelled where used:')
    print('  "267 deg/s", "176.480 and 182.802 ms" - the props-on set, measured in')
    print('       pr15400-8ksal8-arming/ by its own scripts')
    print('  "34" and "46 Hz" for the yaw sightings - ADRC-028 and the props-on set')


def check(sources):
    """Forward: every phrase appears verbatim in each artifact declared to use
    it, and no near-variant of it appears anywhere in that artifact. Reverse:
    every measured value in the prose is produced by one of these scripts,
    compared as whole tokens rather than substrings.

    Known blind spots: rewording the non-numeric part of a phrase takes it out
    of its own family pattern; a sign change or scientific notation is not
    recognised as a measured value; and a number that appears in some unrelated
    script output satisfies the reverse direction wherever it is used.
    """
    blobs = {}
    for key, path in sources.items():
        try:
            blobs[key] = ' '.join(open(path).read().split())
        except OSError as exc:
            print(f'  cannot read {path}: {exc}')
            return 1

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
            family = re.escape(norm)
            family = re.sub(r'\\?\d+(?:\\?\.\d+)?', r'\\d+(?:\\.\\d+)?', family)
            variants = {m for m in re.findall(family, blob) if m != norm}
            if variants:
                bad += len(variants)
                print(f'  VARIANT [{want}] {phrase}  <- also found: '
                      + ', '.join(sorted(variants)))
            else:
                print(f'  ok      [{want}] {phrase}')

    print('\n# Reverse: every measured value in the prose must come from a script\n')
    corpus = io.StringIO()
    with contextlib.redirect_stdout(corpus):
        for mod in ('provenance', 'arms', 'spectra'):
            __import__(mod).main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d{1,2}S(?![\w])|(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|g\b|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}S(?![\w])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {'15400', '2026', '0.5', '1.0', '028',
               '83', '8172', '80', '103',   # jmsweng's fit and tune, quoted from his comment

               '267', '176.480', '182.802', '34', '46', '200',   # the props-on set
               '5231336333', '5235424105'}
    for name, blob in blobs.items():
        prose = re.sub(r'`[^`]*\.(c|h|md|py)[^`]*`', '', blob)
        prose = re.sub(r'\d{4}-\d{2}-\d{2}', '', prose)
        unexplained = sorted({n for n in measured.findall(prose)
                              if n not in known and n not in ALLOWED})
        if unexplained:
            bad += len(unexplained)
            print(f'  UNEXPLAINED in {name}: {", ".join(unexplained)}')
        else:
            print(f'  ok      {name}: every measured value traced to script output')

    print(f'\n  {bad} problem(s).')
    return 1 if bad else 0


if __name__ == '__main__':
    main()
    if '--check' in sys.argv:
        here = os.path.dirname(os.path.abspath(__file__))
        sources = {ANALYSIS: os.path.join(here, 'ANALYSIS.md')}
        if 'ARMING_REPLY' in os.environ:
            sources[REPLY] = os.environ['ARMING_REPLY']
        if 'JM_REPLY' in os.environ:
            sources[JM] = os.environ['JM_REPLY']
        sys.exit(check(sources))

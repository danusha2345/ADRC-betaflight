#!/usr/bin/env python3
"""The rounded summary forms quoted in prose, and how each is derived.

Run with --check for a regression guard over the prose. It is a guard, NOT a
proof: it catches the mutation classes implemented in check(), and a
determined edit can still slip past - rewording the non-numeric part of a
phrase, flipping a sign, or writing a number in a form the pattern does not
recognise. Treat a green run as "no known class of drift detected", never as
"the text is verified".
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

from common import GROUPS, SWEEP, LOGS, load, time_s
from spectra import (OLD_GROUPS, group_table, phase_rows, yaw_metrics)
from common import OLD

ANALYSIS, REPLY = 'ANALYSIS.md', 'DRAFT_reply.md'
PHRASES = []


def full(x):
    return repr(float(x))


def line(phrase, derivation, artifacts=(ANALYSIS,)):
    PHRASES.append((phrase, tuple(artifacts)))
    print(f'  "{phrase}"')
    print(f'      from: {derivation}')


def main():
    print('# Summary phrases used in prose, with their derivation\n')

    new_t = group_table(GROUPS)
    old_t = group_table(OLD_GROUPS, basedir=OLD)
    c_on_old = old_t['CLASSIC yawD=0, Airmode on'][0]
    c_on_new = new_t['CLASSIC yawD=26, Airmode on'][0]
    a_on_old = old_t['ADRC dynIdle=0, Airmode on'][0]
    a_on_new = new_t['ADRC dynIdle=30, Airmode on'][0]

    line(f'from {c_on_old:.2f} to {c_on_new:.2f} deg/s RMS ({c_on_new / c_on_old:.2f}\u00d7)',
         f'CLASSIC feature-on yaw 30-80 medians: old {full(c_on_old)}, new {full(c_on_new)}, '
         f'ratio {full(c_on_new / c_on_old)}; rounded to 0.01',
         artifacts=(ANALYSIS, REPLY))
    line(f'from {a_on_old:.2f} to {a_on_new:.2f} ({a_on_new / a_on_old:.2f}\u00d7',
         f'ADRC feature-on yaw 30-80 medians: old {full(a_on_old)}, new {full(a_on_new)}, '
         f'ratio {full(a_on_new / a_on_old)}; rounded to 0.01',
         artifacts=(ANALYSIS, REPLY))
    line(f'**{a_on_new / c_on_new:.1f}\u00d7** (was {a_on_old / c_on_old:.1f}\u00d7)',
         f'feature-on ADRC/CLASSIC: new {full(a_on_new / c_on_new)}, old '
         f'{full(a_on_old / c_on_old)}; rounded to one decimal',
         artifacts=(ANALYSIS,))

    print()
    ph_old = phase_rows(OLD_GROUPS, basedir=OLD)
    ph_new = phase_rows(GROUPS)

    def phase_med(rows, label, air):
        vals = [r[5] for r in rows if r[0] == label and r[2] == air]
        return float(np.median(vals)), len(vals)

    a_off_off, n1 = phase_med(ph_old, 'ADRC dynIdle=0, Airmode off', False)
    line(f'ADRC on this tune sits at {a_off_off:.2f} — near the CLASSIC floor',
         f'first-corpus ADRC switch cells, airmode-off phases (n={n1}): median '
         f'{full(a_off_off)}; rounded to 0.01', artifacts=(ANALYSIS,))

    # the phase table, emitted as full rows so each phrase is unique
    TABLE = [
        ('ADRC dynIdle=0 (first corpus, "feature off" cell)',
         'ADRC dynIdle=0, Airmode off', ph_old, '**{:.2f}** (n={})'),
        ('CLASSIC yawD=0 (first corpus)',
         'CLASSIC yawD=0, Airmode off', ph_old, '{:.2f} (n={})'),
        ('CLASSIC yawD=26 (this corpus)',
         'CLASSIC yawD=26, Airmode off', ph_new, '{:.2f} (n={})'),
        ('ADRC dynIdle=30 (this corpus)',
         'ADRC dynIdle=30, Airmode off', ph_new, '{:.2f} (n={})'),
    ]
    for row_label, label, rows, fmt in TABLE:
        off_v, off_n = phase_med(rows, label, False)
        on_v, on_n = phase_med(rows, label, True)
        line(f'| {row_label} | {fmt.format(off_v, off_n)} | {fmt.format(on_v, on_n)} |',
             f'{label}: off-phase median {full(off_v)} (n={off_n}), '
             f'ON-phase median {full(on_v)} (n={on_n})',
             artifacts=(ANALYSIS,))

    print()
    sweep_vals = {wc: yaw_metrics(load(stem))[0] for wc, stem in SWEEP}
    sweep_pks = [yaw_metrics(load(stem))[1] for _, stem in SWEEP]
    line(f'**{sweep_vals[120] / sweep_vals[80]:.1f}\u00d7** over the sweep',
         f'wc120 {full(sweep_vals[120])} / wc80 {full(sweep_vals[80])} = '
         f'{full(sweep_vals[120] / sweep_vals[80])}; one decimal',
         artifacts=(ANALYSIS,))
    line(f'{sweep_vals[120] / sweep_vals[80]:.1f}\u00d7 from wc 80 to wc 120',
         'the same ratio in the verdict paragraph and the reply',
         artifacts=(ANALYSIS, REPLY))
    line(f'({min(sweep_pks):.1f}\u2013{max(sweep_pks):.1f} Hz across a 50 % wc sweep)',
         f'sweep peak frequencies {", ".join(full(p) for p in sweep_pks)}; '
         f'endpoints to 0.1 Hz; wc 80 to 120 is a 50 % increase',
         artifacts=(ANALYSIS,))
    line(f'frequency {min(sweep_pks):.1f}\u2013{max(sweep_pks):.1f} Hz and not monotonic',
         'the same endpoints in the sweep section', artifacts=(ANALYSIS,))
    mono = all(sweep_vals[a] < sweep_vals[b]
               for a, b in zip(sorted(sweep_vals), sorted(sweep_vals)[1:]))
    assert mono, 'sweep monotonicity claim would be false: ' + repr(sweep_vals)
    line('Amplitude strictly monotonic in wc',
         'asserted from per-wc values: '
         + ', '.join(f'wc{w} {full(v)}' for w, v in sorted(sweep_vals.items())),
         artifacts=(ANALYSIS,))
    consistency = phase_med(ph_new, 'ADRC dynIdle=30, Airmode off', False)[0]
    line(f'pooled median {consistency:.2f} lands between the wc 90 and wc 100 sweep points',
         f'{full(consistency)} against wc90 {full(sweep_vals[90])} and '
         f'wc100 {full(sweep_vals[100])}; the between-ness is checked by sweep.py',
         artifacts=(ANALYSIS,))

    spans = sorted(time_s(load(s))[-1] for _, s in SWEEP)
    line(f'the short spans ({spans[0]:.1f}\u2013{spans[-1]:.1f} s)',
         f'sweep spans ' + ', '.join(full(x) for x in spans) + '; endpoints to 0.1 s',
         artifacts=(ANALYSIS,))

    print('\nNot derivable from these logs, labelled where used:')
    print('  first-corpus whole-arm medians and peaks are computed here from the')
    print('  neighbouring corpus (spectra.py loads it directly)')


def check(sources):
    """Forward: every phrase appears verbatim in each artifact declared to use
    it, and no near-variant appears. Reverse: every measured value in the
    prose is produced by one of these scripts, compared as whole tokens.

    Known blind spots, demonstrated by mutation testing in review: rewording
    the non-numeric part of a phrase; sign flips; scientific notation; and -
    the big one - MISATTRIBUTION. The reverse check is token-level, not
    claim-level: a number that any script prints for log A passes even if the
    prose attributes it to log B or to a different quantity entirely. A green
    run means "no known drift class detected", never "the text is verified".
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
        for mod in ('modemask', 'provenance', 'arms', 'spectra', 'sweep'):
            __import__(mod).main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|arms|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {
        '15400', '2026',            # PR number, year
        '2048',                     # nperseg, stated as method
        '026',                      # ADRC-026 tracker id
        '0.5', '1.0',               # the mixer authority scales, from the code
        '800', '3.2',               # "~800 Hz of a 3.2 kHz loop", stated approximations
        '1.5',                      # the MIN_PHASE_S constant, stated as method
    }
    for name, blob in blobs.items():
        prose = re.sub(r'`[^`]*`', '', blob)          # code spans: keys, values, ids
        prose = re.sub(r'\d{4}-\d{2}-\d{2}', '', prose)
        prose = re.sub(r'\[[^\]]*\]\([^)]*\)', '', prose)   # link targets
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
        if 'PROPSOFF2_REPLY' in os.environ:
            sources[REPLY] = os.environ['PROPSOFF2_REPLY']
        sys.exit(check(sources))

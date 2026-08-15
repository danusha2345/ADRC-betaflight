#!/usr/bin/env python3
"""Rounded summary forms quoted in the ladder prose, with derivations.

--check is the same guard as in the neighbouring campaigns; a guard, not a
proof (token-level, cannot catch misattribution) - blind spots documented
in pr15400-8ksal8-propsoff2/summaries.py.
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

from common import LOGS, load, time_s

ANALYSIS, REPLY = 'ANALYSIS.md', 'DRAFT_reply.md'
PHRASES = []


def full(x):
    return repr(float(x))


def line(phrase, derivation, artifacts=(ANALYSIS,), allow_variants=False):
    # allow_variants: for table rows whose config labels differ only in a
    # digit (LP1 vs LP2), the number-wildcarded family pattern of one row
    # necessarily matches its sibling rows. Only variants that are
    # THEMSELVES registered phrases are tolerated - a duplicated row
    # carrying foreign numbers is not registered and still flags.
    PHRASES.append((phrase, tuple(artifacts), allow_variants))
    print(f'  "{phrase}"')
    print(f'      from: {derivation}')


def main():
    print('# Summary phrases used in prose, with their derivation\n')
    from ladder import seg_metrics
    rows = {}
    for label, stem in LOGS:
        lo, hi, dur, v0, v1, g, c, inb, prom, rail = seg_metrics(stem)
        rows[label] = dict(dur=dur, v0=v0, v1=v1, g=g, c=c, inb=inb, prom=prom, rail=rail)
        line(f'| {label}{" *" if label == "LP1+LP2+RPM" else ""} | {dur:.1f} s | '
             f'{v0:.2f}–{v1:.2f} | {g:.2f} | {c:.1f} | {inb:.1f} Hz | {prom:.0f}× | {rail} |',
             f'{label}: segment metrics from ladder.seg_metrics', artifacts=(ANALYSIS,),
             allow_variants=True)

    r = rows['off']
    line(f'prominence is {r["prom"]:.0f}× (band peak {r["inb"]:.1f} Hz)',
         'the all-off segment', artifacts=(ANALYSIS,))
    proms = [rows[l]['prom'] for l, _ in LOGS if l != 'off']
    line(f'prominences of {min(proms):.0f}×–{max(proms):.0f}×',
         'prominence range over the six on-configs: '
         + ', '.join(full(p) for p in proms), artifacts=(ANALYSIS,))
    lr = rows['LP1+RPM']
    line(f'(gyro {lr["g"]:.2f}, command {lr["c"]:.1f}, {lr["prom"]:.0f}×, '
         f'{lr["rail"]} rail samples in the segment)',
         'the LP1+RPM segment', artifacts=(ANALYSIS,))
    line(f'{rows["LP1"]["g"]:.2f} vs {rows["LP2"]["g"]:.2f}, '
         f'{rows["LP1"]["prom"]:.0f}× vs {rows["LP2"]["prom"]:.0f}×',
         'LP1-alone vs LP2-alone', artifacts=(ANALYSIS,))
    line(f'ends with the arm after {rows["LP1+LP2+RPM"]["dur"]:.1f} s (post-trim)',
         'the censored full-stack segment', artifacts=(ANALYSIS,))

    meds = {}
    for label, stem in LOGS:
        d = load(stem)
        meds[label] = [float(np.median(np.abs(d[f'setpoint[{ax}]'] - d[f'gyroADC[{ax}]'])))
                       for ax in range(3)]
    line(f'off runs {"/".join(f"{v:.0f}" for v in meds["off"])} deg/s',
         'whole-log off medians', artifacts=(ANALYSIS,))
    line(f'RPM-only reaches {"/".join(f"{v:.0f}" for v in meds["RPM"])}',
         'whole-log RPM-only medians', artifacts=(ANALYSIS,))

    print('\nEvery other AcroBee-derived number appears directly in overview.py /')
    print('ladder.py output and is traced by the reverse check. Cross-campaign')
    print('references are links only in this campaign; no external numbers are')
    print('quoted.')


def check(sources):
    blobs = {}
    for key, path in sources.items():
        try:
            blobs[key] = ' '.join(open(path).read().split())
        except OSError as exc:
            print(f'  cannot read {path}: {exc}')
            return 1

    bad = 0
    all_norms = {' '.join(p.split()) for p, _, _ in PHRASES}
    print('\n# Forward\n')
    for phrase, artifacts, allow_variants in PHRASES:
        norm = ' '.join(phrase.split())
        for want in artifacts:
            if want not in blobs:
                bad += 1
                print(f'  ABSENT  [{want}] not supplied: {phrase}')
                continue
            blob = blobs[want]
            if norm not in blob:
                bad += 1
                print(f'  MISSING [{want}] {phrase}')
                continue
            family = re.escape(norm)
            family = re.sub(r'\\?\d+(?:\\?\.\d+)?', r'\\d+(?:\\.\\d+)?', family)
            variants = {mm for mm in re.findall(family, blob) if mm != norm
                        and not (allow_variants and ' '.join(mm.split()) in all_norms)}
            if variants:
                bad += len(variants)
                print(f'  VARIANT [{want}] {phrase}  <- also: ' + ', '.join(sorted(variants)))
            else:
                print(f'  ok      [{want}] {phrase}')

    print('\n# Reverse\n')
    corpus = io.StringIO()
    with contextlib.redirect_stdout(corpus):
        for mod in ('overview', 'ladder'):
            __import__(mod).main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {'15400', '2026', '029',
               '45', '55', '0.3'}   # prominence band and trim, stated as method
    for name, blob in blobs.items():
        prose = re.sub(r'`[^`]*`', '', blob)
        prose = re.sub(r'\d{4}-\d{2}-\d{2}', '', prose)
        prose = re.sub(r'\[[^\]]*\]\([^)]*\)', '', prose)
        unexplained = sorted({n for n in measured.findall(prose)
                              if n not in known and n not in ALLOWED})
        if unexplained:
            bad += len(unexplained)
            print(f'  UNEXPLAINED in {name}: {", ".join(unexplained)}')
        else:
            print(f'  ok      {name}')

    print(f'\n  {bad} problem(s).')
    return 1 if bad else 0


if __name__ == '__main__':
    main()
    if '--check' in sys.argv:
        here = os.path.dirname(os.path.abspath(__file__))
        sources = {ANALYSIS: os.path.join(here, 'ANALYSIS.md')}
        if 'ACROBEE2_REPLY' in os.environ:
            sources[REPLY] = os.environ['ACROBEE2_REPLY']
        sys.exit(check(sources))

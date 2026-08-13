#!/usr/bin/env python3
"""Rounded summary forms quoted in the TH3 prose, with derivations.

--check is the same guard as in the neighbouring campaigns (forward verbatim
phrases with number-wildcarded variant detection; reverse token tracing of
every measured value to script stdout). A guard, not a proof: it cannot
catch a number attributed to the wrong log or quantity - see
pr15400-8ksal8-propsoff2/summaries.py for the demonstrated blind spots.
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

from common import LOGS, headers, load

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

    packs = {}
    for pack, role, stem in LOGS:
        if role != 'flight':
            continue
        h = headers(stem)
        d = load(stem)
        packs[pack] = (float(h['adrcB0'].split(',')[0]),
                       float(np.median(d['vbatLatest (V)'])))
    rb32 = packs['3s'][0] / packs['2s'][0]
    rb43 = packs['4s'][0] / packs['3s'][0]
    rv32 = packs['3s'][1] / packs['2s'][1]
    rv43 = packs['4s'][1] / packs['3s'][1]
    line(f'3s/2s = {rb32:.3f}, 4s/3s = {rb43:.3f}',
         f'b0 roll ratios: {full(rb32)}, {full(rb43)}; rounded to 3 decimals',
         artifacts=(ANALYSIS, REPLY))
    line(f'ratios {rv32:.3f} and {rv43:.3f}',
         f'flight-median vbat ratios: {full(rv32)}, {full(rv43)}',
         artifacts=(ANALYSIS, REPLY))

    from common import motors
    rails = []
    for pack, role, stem in LOGS:
        if role != 'flight':
            continue
        d = load(stem)
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        rails.append(int((motors(d) >= hi).sum()))
    line(f'{rails[0]} → {rails[1]} → {rails[2]}',
         'motor-rail samples per flight log, 2s/3s/4s',
         artifacts=(ANALYSIS,))

    clips_f, clips_w = [], []
    for pack, role, stem in LOGS:
        d = load(stem)
        c = 100.0 * float((np.abs(d['debug[6]']) >= 32767).sum()) / d['_n']
        (clips_f if role == 'flight' else clips_w).append(c)
    line(f'**{min(clips_f):.1f}–{max(clips_f):.1f} %** of frames in the acro flights '
         f'and **{min(clips_w):.1f}–{max(clips_w):.1f} %**',
         'yaw z3 rail shares: flights ' + ', '.join(full(c) for c in clips_f)
         + '; wobble ' + ', '.join(full(c) for c in clips_w) + '; rounded to 0.1',
         artifacts=(ANALYSIS,))
    line(f'up to {max(clips_f):.1f} % of flight frames and '
         f'{min(clips_w):.1f}–{max(clips_w):.1f} % of the wobble-log frames',
         'the same rail shares, in the form the reply uses',
         artifacts=(REPLY,))

    print('\nEverything else quoted in ANALYSIS.md appears directly in')
    print('overview.py output and is traced by the reverse check.')


def check(sources):
    blobs = {}
    for key, path in sources.items():
        try:
            blobs[key] = ' '.join(open(path).read().split())
        except OSError as exc:
            print(f'  cannot read {path}: {exc}')
            return 1

    bad = 0
    print('\n# Forward\n')
    for phrase, artifacts in PHRASES:
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
            variants = {mm for mm in re.findall(family, blob) if mm != norm}
            if variants:
                bad += len(variants)
                print(f'  VARIANT [{want}] {phrase}  <- also: ' + ', '.join(sorted(variants)))
            else:
                print(f'  ok      [{want}] {phrase}')

    print('\n# Reverse\n')
    corpus = io.StringIO()
    with contextlib.redirect_stdout(corpus):
        __import__('overview').main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {'15400', '2026', '029',
               '5022', '1204.5',         # motor size/kv, quoted from the tester
               '2.5'}                    # craft size, quoted from the tester
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
        if 'TH3_REPLY' in os.environ:
            sources[REPLY] = os.environ['TH3_REPLY']
        sys.exit(check(sources))

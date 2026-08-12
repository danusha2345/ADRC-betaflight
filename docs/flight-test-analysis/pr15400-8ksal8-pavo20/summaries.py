#!/usr/bin/env python3
"""Rounded summary forms quoted in the Pavo20 prose, with derivations.

--check is the same guard as in the neighbouring campaigns: forward
verbatim-phrase presence with number-wildcarded variant detection, reverse
tracing of every measured value in the prose to script stdout. A guard, not
a proof; blind spots as documented in pr15400-8ksal8-propsoff2/summaries.py -
in particular the reverse check is token-level, not claim-level, so it
cannot catch a number attributed to the wrong log or quantity.
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

from common import STEMS, headers, load, motors, time_s, text_column, DEBUG_CLIP

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

    for stem, fmt in (('Return_to_home_btfl_002',
                       'from **{:.2f} s to {:.2f} s** — a {:.1f} s rescue'),
                      ('Finished_minus_5_percent_btfl_001',
                       '**{:.2f} s to {:.2f} s** ({:.1f} s)')):
        d = load(stem)
        t = time_s(d)
        ph = text_column(stem, 'failsafePhase')
        idx = [i for i in range(1, len(ph)) if ph[i] != ph[i - 1]]
        t_in, t_out = t[idx[0]], t[idx[1]]
        line(fmt.format(t_in, t_out, t_out - t_in),
             f'{stem}: failsafePhase transitions at {full(t_in)} and {full(t_out)}; '
             f'duration {full(t_out - t_in)}, rounded to 0.01/0.1 s',
             artifacts=(ANALYSIS,))

    clips = []
    for stem in STEMS:
        dd = load(stem)
        n = dd['_n']
        clips.append(100.0 * float((np.abs(dd['debug[6]']) >= DEBUG_CLIP).sum()) / n)
    line(f'**{clips[0]:.1f} / {clips[1]:.1f} / {clips[2]:.1f} %** of frames',
         'yaw z3 debug-rail share per log: '
         + ', '.join(full(c) for c in clips) + '; rounded to 0.1 %',
         artifacts=(ANALYSIS,))

    h = headers(STEMS[0])
    clamp = int(float(h['pidsum_limit_yaw']) * float(h['adrcB0'].split(',')[2]))
    line(f'= {clamp:,} '.replace(',', ' ').strip(),
         f'pidsum_limit_yaw {h["pidsum_limit_yaw"]} x b0 yaw '
         f'{h["adrcB0"].split(",")[2]} = {clamp}', artifacts=(ANALYSIS,))
    line(f'between {32767 * 16:,} and'.replace(',', ' '),
         'the b9 debug rail: 32767 * 16', artifacts=(ANALYSIS,))

    d1 = load('Finished_minus_5_percent_btfl_001')
    m = motors(d1)
    hi = float(headers(STEMS[0])['motorOutput'].split(',')[1])
    rail = int((m >= hi).sum())
    pct = 100.0 * rail / (m.shape[0] * m.shape[1])
    line(f'Its {rail} rail frames ({pct:.1f} % of motor samples)',
         f'motor samples at the upper endpoint in the finished flight: {rail} '
         f'of {m.shape[0] * m.shape[1]} ({full(pct)} %)', artifacts=(ANALYSIS,))

    print('\nEverything else quoted in ANALYSIS.md appears directly in')
    print('overview.py / wobble.py output and is traced by the reverse check.')


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
        for mod in ('overview', 'wobble', 'boxes'):
            __import__(mod).main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {'15400', '2026', '029',
               '20', '40',        # the quiet-stick test thresholds, stated as method
               '10',              # "below 10 V", a stated round bound (measured 9.67/9.94)
               '1.5'}             # "about 1.5 s", stated rounding of the printed 1.49/1.48 leads
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
        if 'PAVO20_REPLY' in os.environ:
            sources[REPLY] = os.environ['PAVO20_REPLY']
        sys.exit(check(sources))

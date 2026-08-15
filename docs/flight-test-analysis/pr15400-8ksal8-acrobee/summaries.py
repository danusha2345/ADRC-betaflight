#!/usr/bin/env python3
"""Rounded summary forms quoted in the AcroBee75 prose, with derivations.

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

from common import ON, OFF, load, time_s, airmode_windows

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

    d = load(ON)
    t = time_s(d)
    wins = airmode_windows(ON, float(t[-1]))
    vb = d['vbatLatest (V)']
    durs, vstarts = [], []
    for lo, hi in wins:
        durs.append(hi - lo)
        vstarts.append(float(np.median(vb[(t >= lo) & (t < lo + 1)])))
    short = [i for i in range(len(durs)) if durs[i] < 5.0]
    long_ = [i for i in range(len(durs)) if durs[i] >= 5.0]
    line(f'activated **seven times**',
         f'{len(wins)} airmode windows in the ON log', artifacts=(ANALYSIS,))
    assert len(wins) == 7
    line(f'the three activations shorter than 5 s all started at '
         f'{min(vstarts[i] for i in short):.2f} V or above',
         f'short activations n={len(short)}, min start vbat '
         + ', '.join(f'{vstarts[i]:.4f}' for i in short), artifacts=(ANALYSIS,))
    line(f'the four longer ones ({min(durs[i] for i in long_):.1f}–'
         f'{max(durs[i] for i in long_):.1f} s) all started at '
         f'{max(vstarts[i] for i in long_):.2f} V or below',
         f'long activations n={len(long_)}: '
         + ', '.join(f'{durs[i]:.2f}s@{vstarts[i]:.2f}V' for i in long_),
         artifacts=(ANALYSIS,))

    d2 = load(OFF)
    t2 = time_s(d2)
    wins2 = airmode_windows(OFF, float(t2[-1]))
    lo2, hi2 = wins2[0]
    vb2 = float(np.median(d2['vbatLatest (V)'][(t2 >= lo2) & (t2 < lo2 + 1)]))
    line(f'went active at {lo2:.1f} s ({vb2:.2f} V, fresh pack) and stayed active for '
         f'{hi2 - lo2:.1f} s',
         f'OFF-log airmode window {full(lo2)}..{full(hi2)}, start vbat {full(vb2)}',
         artifacts=(ANALYSIS,))

    from spectra import matched_windows, psd_seg, band_rms, BAND
    data = {}
    for stem in (ON, OFF):
        dd, tt, ws = matched_windows(stem)
        g, c, pk = [], [], []
        for k, w in ws:
            f, P = psd_seg(tt[w], dd['gyroUnfilt[2]'][w])
            g.append(band_rms(f, P, *BAND))
            m = (f > 8) & (f < 400)
            pk.append(float(f[m][np.argmax(P[m])]))
            f, P = psd_seg(tt[w], dd['axisP[2]'][w] + dd['axisD[2]'][w])
            c.append(band_rms(f, P, *BAND))
        data[stem] = (g, c, pk)
    off_g = float(np.median(data[OFF][0]))
    off_c = float(np.median(data[OFF][1]))
    g, c, pk = data[ON]
    li = [i for i, p in enumerate(pk) if 45 <= p <= 55]
    oi = [i for i in range(len(pk)) if i not in li]
    lg = float(np.median([g[i] for i in li]))
    lc = float(np.median([c[i] for i in li]))
    og = float(np.median([g[i] for i in oi]))
    oc = float(np.median([c[i] for i in oi]))
    line(f'| ~50 Hz globally dominant | {len(li)} | {lg:.2f} | **{lg / off_g:.1f}×** | '
         f'{lc:.2f} | **{lc / off_c:.1f}×** |',
         f'globally-dominant ON windows vs OFF medians {full(off_g)}/{full(off_c)}',
         artifacts=(ANALYSIS,))
    line(f'| higher-frequency dominant | {len(oi)} | {og:.2f} | {og / off_g:.2f}× | {oc:.2f} | {oc / off_c:.2f}× |',
         'the higher-frequency-dominant ON windows, same derivation', artifacts=(ANALYSIS,))
    line(f'**{lg / off_g:.1f}× (gyro) / {lc / off_c:.1f}× (command)**',
         'the dominant-window ratios in the form the reply uses', artifacts=(REPLY,))
    line(f'({og / off_g:.2f}×/{oc / off_c:.2f}×)',
         'the other-window ratios in the form the reply uses', artifacts=(REPLY,))
    pg = float(np.median(g))
    pc = float(np.median(c))
    line(f'2.2×/2.7×, fall between the subset medians',
         f'pooled ON medians {full(pg)}/{full(pc)} over OFF -> '
         f'{full(pg / off_g)}/{full(pc / off_c)}, rounded to 0.1',
         artifacts=(ANALYSIS,))

    print('\nEvery other AcroBee-derived number appears directly in overview.py /')
    print('attempts.py / spectra.py output and is traced by the reverse check.')
    print('Cross-campaign quotes (Air65 bench range, Pavo20 yaw line) are')
    print('external, listed in ALLOWED with their sources, and NOT validated')
    print('by this checker.')


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
        for mod in ('overview', 'attempts', 'spectra'):
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
               '5', '10',      # "shorter than 5 s" split and the 10-s window, stated as method
               '6.5',          # "6.5 minutes", quoted from the tester
               '580',          # the tester's pack name, quoted
               '47.9', '54.2', '80', '120',  # Air65 bench range, quoted from
                                             # pr15400-8ksal8-propsoff2/ANALYSIS.md
               '48.75',        # Pavo20 yaw line, quoted from pr15400-8ksal8-b0sweep/ANALYSIS.md
               '45', '55'}     # the line-present peak classification band, stated as method
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
        if 'ACROBEE_REPLY' in os.environ:
            sources[REPLY] = os.environ['ACROBEE_REPLY']
        sys.exit(check(sources))

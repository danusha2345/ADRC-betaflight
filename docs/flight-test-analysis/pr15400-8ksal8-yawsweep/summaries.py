#!/usr/bin/env python3
"""Rounded summary forms quoted in the yaw-sweep prose, with derivations.

Same guard as the neighbouring campaigns; a guard, not a proof (token-level;
blind spots documented in pr15400-8ksal8-propsoff2/summaries.py and the
unit/context-binding lesson in pr15400-8ksal8-b0calc/summaries.py).
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

ANALYSIS, REPLY = 'ANALYSIS.md', 'DRAFT_reply.md'
PHRASES = []


def line(phrase, derivation, artifacts=(ANALYSIS,), counts=None):
    # counts: optional {artifact: exact occurrence count}; artifacts without an
    # entry are checked for >= 1 occurrence. Pin counts for phrases that appear
    # more than once so a partial mutation cannot hide behind a sibling.
    PHRASES.append((phrase, tuple(artifacts), counts or {}))
    print(f'  "{phrase}"')
    print(f'      from: {derivation}')


def main():
    print('# Summary phrases with derivations\n')
    import analysis
    hds = {s: analysis.headers(s) for s in analysis.STEMS}
    M = {s: analysis.metrics(s) for s in analysis.STEMS}

    wcs = analysis.GROUPS[0][1]
    wcwo = analysis.GROUPS[1][1]

    lo = min(M[s]['pk_hz'] for s in wcs)
    hi = max(M[s]['pk_hz'] for s in wcs)
    line(f'in a {lo:.1f}–{hi:.1f} Hz range', 'min/max band-peak over the wc sweep (wo = 80)',
         artifacts=(ANALYSIS,))
    line(f'stays at {lo:.1f}–{hi:.1f} Hz', 'the same range, reply form',
         artifacts=(REPLY,))
    line(', '.join(f'wo={hds[s]["adrcWO"].split(",")[2]} → {M[s]["pk_hz"]:.2f} Hz'
                   for s in wcwo),
         'band-peak per cell of the wc = wo sweep', artifacts=(ANALYSIS, REPLY))
    a50, b50 = 'Air65_yaw_wc_50_', 'Air65_yaw_wc_wo_50_'
    line(f'wo 80 → {M[a50]["pk_hz"]:.2f} Hz vs wo 50 → {M[b50]["pk_hz"]:.2f} Hz',
         'the same-link-rate wc=50 contrast', artifacts=(ANALYSIS, REPLY))

    ra, rb = 'Air65_yaw_wc_80_', 'Air65_yaw_wc_wo_80_'
    line(f'{M[ra]["pk_hz"]:.2f} vs {M[rb]["pk_hz"]:.2f} Hz, prominence '
         f'{M[ra]["prom"]:.1f} vs {M[rb]["prom"]:.1f}, band RMS '
         f'{M[ra]["band"]:.2f} vs {M[rb]["band"]:.2f} deg/s',
         'the repeated 80/80 cell (matching wc/wo/b0 tune; headers differ in rx_smoothed/vbatref)',
         artifacts=(ANALYSIS, REPLY))

    s5, q5 = 'Air65_yaw_wc_wo_50_', 'Air65_yaw_wc_wo_50_adjusted_bo_'
    line(f'RMS {M[s5]["band"]:.2f} → {M[q5]["band"]:.2f} deg/s, prominence '
         f'{M[s5]["prom"]:.1f} → {M[q5]["prom"]:.1f}',
         'band change at wc=wo=50 when yaw b0 drops 2340 -> 878',
         artifacts=(ANALYSIS, REPLY))
    line(f'the flight completes ({M[q5]["dur"]:.1f} s)',
         'duration of the wc=wo=50 / b0y=878 flight', artifacts=(ANALYSIS,))

    s6, q6 = 'Air65_yaw_wc_wo_60_', 'Air65_yaw_wc_wo_60_adjusted_bo_'
    line(f'component at {M[q6]["pk_hz"]:.2f} Hz (prominence {M[q6]["prom"]:.1f}, '
         f'band RMS {M[q6]["band"]:.2f} deg/s',
         'peak/prominence/band RMS of the wc=wo=60 / b0y=878 flight',
         artifacts=(ANALYSIS,))
    line(f'sustained {M[q6]["pk_hz"]:.2f} Hz yaw component (band RMS '
         f'{M[q6]["band"]:.2f} deg/s',
         'the same peak and band RMS, reply form', artifacts=(REPLY,))
    line(f'yaw error median {M[q6]["med_y"]:.1f} deg/s vs {M[s6]["med_y"]:.1f} stock',
         'yaw medians, adjusted vs stock b0 at wc=wo=60', artifacts=(ANALYSIS,))
    line(f'yaw median {M[q6]["med_y"]:.0f} deg/s vs {M[s6]["med_y"]:.0f} stock',
         'the same medians, reply form', artifacts=(REPLY,))
    line(f'ends after {M[q6]["dur"]:.1f} s; the vbat floor is {M[q6]["vmin"]:.2f} V '
         f'(reached at {M[q6]["t_vmin"]:.1f} s) and the final vbat sample is '
         f'{M[q6]["vend"]:.2f} V',
         'duration, whole-log vbat minimum with its timestamp, and last vbat sample',
         artifacts=(ANALYSIS,))
    line(f'ends after {M[q6]["dur"]:.1f} s — vbat floor {M[q6]["vmin"]:.2f} V early in '
         f'the flight, final sample {M[q6]["vend"]:.2f} V',
         'the same three values, reply form', artifacts=(REPLY,))
    line(f'crosses link-rate clusters ({int(hds[s6]["rc_smoothing_rx_smoothed"])} vs '
         f'{int(hds[q6]["rc_smoothing_rx_smoothed"])} Hz)',
         'rx_smoothed of the stock vs adjusted wc=wo=60 cells', artifacts=(ANALYSIS,))
    line(f'at ~{int(hds[s6]["rc_smoothing_rx_smoothed"])} Hz link rate and the '
         f'adjusted one at ~{int(hds[q6]["rc_smoothing_rx_smoothed"])} Hz',
         'the same two link rates, reply form', artifacts=(REPLY,))

    sl = 'Air65_lower_RP_raise_Y_'
    line(f'peak at {M[sl]["pk_hz"]:.2f} Hz with prominence {M[sl]["prom"]:.1f} and '
         f'band RMS {M[sl]["band"]:.2f} deg/s',
         'peak/prominence/band RMS of the 88/88 cell', artifacts=(ANALYSIS,))
    line(f'({M[sl]["pk_hz"]:.2f} Hz, prominence {M[sl]["prom"]:.1f}, band RMS '
         f'{M[sl]["band"]:.2f} deg/s)',
         'the same three numbers, reply form', artifacts=(REPLY,))
    line(f'{M[sl]["med_y"]:.1f} deg/s against {M[rb]["med_y"]:.1f} deg/s',
         'yaw medians, 88/88 vs the 80/80 cell of the wc=wo sweep',
         artifacts=(ANALYSIS,))
    line(f'yaw median {M[sl]["med_y"]:.0f} vs {M[rb]["med_y"]:.0f} deg/s',
         'the same medians, reply form', artifacts=(REPLY,))

    wcs_vals = sorted(int(hds[s]['adrcWC'].split(',')[2]) for s in wcs)
    line(f'for every `wc` in {wcs_vals[0]}–{wcs_vals[-1]}',
         'the wc range actually flown in the wc sweep', artifacts=(ANALYSIS, REPLY))
    for s_ in analysis.STEMS:
        import gzip as _g, os as _o
        blob = _g.open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)),
                                    f'{s_}.bbl.gz'), 'rb').read()
        assert blob.count(b'H Product') == 1, s_
    line('One flight per cell', 'asserted: each .bbl carries exactly one log session',
         artifacts=(ANALYSIS,))
    line('one flight per cell', 'the same assertion, reply form', artifacts=(REPLY,),
         counts={REPLY: 2})

    full = [x for x in analysis.STEMS if M[x]['dur'] >= 30.0]
    top = max(full, key=lambda x: M[x]['band'])
    assert top == sl
    line(f'the largest band RMS among the {len(full)} logs with duration ≥ 30 s',
         'computed over the >=30 s subset; the maximum belongs to the 88/88 cell',
         artifacts=(ANALYSIS,))
    line(f'largest band RMS among your {len(full)} logs of ≥ 30 s',
         'the same superlative, reply form', artifacts=(REPLY,))
    line(f'wc {hds[sl]["adrcWC"].split(",")[0]} / wo {hds[sl]["adrcWO"].split(",")[0]}',
         'roll/pitch tune of the raised-yaw cell', artifacts=(ANALYSIS, REPLY))
    line(f'headers not fully identical — rx_smoothed '
         f'{int(hds[ra]["rc_smoothing_rx_smoothed"])} vs '
         f'{int(hds[rb]["rc_smoothing_rx_smoothed"])}, vbatref '
         f'{int(hds[ra]["vbatref"])} vs {int(hds[rb]["vbatref"])}',
         'the header keys that differ inside the repeated 80/80 cell, with the '
         'non-identity statement bound into the phrase',
         artifacts=(ANALYSIS,))
    lo_wo = min(M[x]['pk_hz'] for x in wcwo)
    hi_wo = max(M[x]['pk_hz'] for x in wcwo)
    line(f'({lo_wo:.1f}–{hi_wo:.1f} Hz)', 'peak span of the wc=wo sweep',
         artifacts=(ANALYSIS,))
    line(f'peak at {M[b50]["pk_hz"]:.2f} → {M[q5]["pk_hz"]:.2f} Hz in the 50-cell',
         'band peak, stock vs adjusted b0 at wc=wo=50', artifacts=(REPLY,))
    line(f'peak at {M[s6]["pk_hz"]:.2f} → {M[q6]["pk_hz"]:.2f} Hz in the 60-cell',
         'band peak, stock vs adjusted b0 at wc=wo=60', artifacts=(REPLY,))

    rates = sorted({int(hds[s]['rc_smoothing_rx_smoothed']) for s in analysis.STEMS})
    lo_r = [r for r in rates if r < 250]
    hi_r = [r for r in rates if r >= 250]
    line(f'at ~{lo_r[0]} Hz and ~{hi_r[0]}–{hi_r[-1]} Hz',
         'the two link-rate clusters', artifacts=(ANALYSIS,))
    line(f'~{lo_r[0]} Hz in some cells, ~{hi_r[0]}–{hi_r[-1]} Hz in others',
         'the same clusters, reply form', artifacts=(REPLY,))
    vmins = [M[s]['vmin'] for s in analysis.STEMS]
    line(f'{min(vmins):.2f}–{max(vmins):.2f} V', 'span of per-cell vbat minima',
         artifacts=(ANALYSIS,))
    b0y = {hds[s]['adrcB0'].split(',')[2] for s in analysis.GROUPS[2][1]}
    b0y_stock = {hds[s]['adrcB0'].split(',')[2] for s in wcs}
    assert b0y == {'878'} and b0y_stock == {'2340'}
    line('yaw b0 lowered 2340 → 878', 'yaw b0 header values, stock vs adjusted cells',
         artifacts=(ANALYSIS,))
    line('redistribution (2340 → 878)', 'the same values, reply form',
         artifacts=(REPLY,))
    line(f'`adrc_gyro_lpf_hz = {hds[wcs[0]]["adrc_gyro_lpf_hz"]}`',
         'the ADRC observer input PT2 cutoff, identical in all 11 headers',
         artifacts=(ANALYSIS,))

    print('\nRemaining numbers are traced by the reverse token check (global token')
    print('pool, no unit/context binding - the weaker guarantee documented in the')
    print('b0calc campaign; unit-bearing claims above are bound as exact phrases).')


def check(sources):
    blobs = {}
    for key, path in sources.items():
        try:
            blobs[key] = ' '.join(open(path).read().split())
        except OSError as exc:
            print(f'  cannot read {path}: {exc}')
            return 1
    bad = 0
    # heuristic guard, not proof: flags causal verbs unless negated within the
    # same sentence; the phrase/count/reverse checks remain the primary gate
    causal = re.compile(r'\b(prove[sdn]?|caus(?:e[sd]?|ing)|demonstrat\w*'
                        r'|establishe[sd]|confirm(?:s|ed|ing)?|driv(?:es?|en|ing)|drove'
                        r'|produc(?:es?|ed|ing)|responsible for|leads? to|led to'
                        r'|results? in)\b', re.I)
    negated = re.compile(r"\b(no|not|nothing|never|nor|cannot)\b|n't", re.I)
    for name, blob in blobs.items():
        hits = []
        for m in causal.finditer(blob):
            sent_start = max(blob.rfind(ch, 0, m.start()) for ch in '.!?')
            if not negated.search(blob[sent_start + 1:m.start()]):
                hits.append(m.group(0))
        if hits:
            bad += len(hits)
            print(f'  CAUSAL-LANGUAGE in {name}: {", ".join(hits)} - forbidden '
                  'outside same-sentence negation; reword or extend the guard '
                  'consciously')
    print('\n# Forward\n')
    for phrase, artifacts, counts in PHRASES:
        norm = ' '.join(phrase.split())
        for want in artifacts:
            if want not in blobs:
                bad += 1
                print(f'  ABSENT  [{want}]: {phrase}')
                continue
            blob = blobs[want]
            if norm not in blob:
                bad += 1
                print(f'  MISSING [{want}] {phrase}')
                continue
            if want in counts and blob.count(norm) != counts[want]:
                bad += 1
                print(f'  COUNT   [{want}] {phrase}: {blob.count(norm)} != {counts[want]}')
                continue
            family = re.escape(norm)
            family = re.sub(r'\\?\d+(?:\\?\.\d+)?', r'\\d+(?:\\.\\d+)?', family)
            registered = {' '.join(ph.split()) for ph, _, _ in PHRASES}
            variants = {mm for mm in re.findall(family, blob)
                        if mm != norm and mm not in registered}
            if variants:
                bad += len(variants)
                print(f'  VARIANT [{want}] {phrase}  <- ' + ', '.join(sorted(variants)))
            else:
                print(f'  ok      [{want}] {phrase}')
    print('\n# Reverse\n')
    corpus = io.StringIO()
    with contextlib.redirect_stdout(corpus):
        __import__('analysis').main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {'15400', '2026',
               '5337016044'}   # the source comment id; every other quoted number
                               # is computed above or printed by analysis.py
    for name, blob in blobs.items():
        prose = re.sub(r'\d{4}-\d{2}-\d{2}', '', blob)  # inline code is traced like prose
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
        if 'YAWSWEEP_REPLY' in os.environ:
            sources[REPLY] = os.environ['YAWSWEEP_REPLY']
        sys.exit(check(sources))

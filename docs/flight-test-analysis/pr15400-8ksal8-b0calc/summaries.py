#!/usr/bin/env python3
"""Rounded summary forms quoted in the b0-calc prose, with derivations.

Same guard as the neighbouring campaigns; a guard, not a proof (token-level;
blind spots documented in pr15400-8ksal8-propsoff2/summaries.py).
"""
import contextlib
import io
import os
import re
import sys

import numpy as np

ANALYSIS, REPLY = 'ANALYSIS.md', 'DRAFT_reply.md'
PHRASES = []


def line(phrase, derivation, artifacts=(ANALYSIS,)):
    PHRASES.append((phrase, tuple(artifacts)))
    print(f'  "{phrase}"')
    print(f'      from: {derivation}')


def main():
    print('# Summary phrases with derivations\n')
    import analysis
    import csv
    rows = list(csv.DictReader(open(analysis.ensure_csv()), skipinitialspace=True))

    def col(n):
        k = next(kk for kk in rows[0] if kk.strip() == n)
        return np.array([float(r[k]) for r in rows])

    t = (col('time (us)') - col('time (us)')[0]) / 1e6
    med, p90 = [], []
    for ax in range(3):
        e = np.abs(col(f'setpoint[{ax}]') - col(f'gyroADC[{ax}]'))
        med.append(float(np.median(e)))
        p90.append(float(np.percentile(e, 90)))
    line(f'medians {"/".join(f"{v:.0f}" for v in med)} deg/s '
         f'(p90 {"/".join(f"{v:.0f}" for v in p90)}) over {t[-1]:.1f} s',
         'whole-flight per-axis error stats and log duration', artifacts=(ANALYSIS, REPLY))
    line(f'one {t[-1]:.1f} s acro flight', 'log duration, ANALYSIS intro form',
         artifacts=(ANALYSIS,))
    line(f'the log continues to {t[-1]:.1f} s', 'log duration, punch-section form',
         artifacts=(ANALYSIS,))

    from scipy.signal import welch, coherence
    lo = float(t[-1]) / 2 - 30
    w = (t >= lo) & (t < lo + 60)
    e = col('setpoint[2]')[w] - col('gyroADC[2]')[w]
    sp2 = col('setpoint[2]')[w]
    ts = t[w]
    fs = (len(ts) - 1) / (ts[-1] - ts[0])
    tu = np.arange(ts[0], ts[-1], 1 / fs)
    eu = np.interp(tu, ts, e)
    su = np.interp(tu, ts, sp2)
    f, P = welch(eu - eu.mean(), fs=fs, nperseg=2048)
    fseek = (f > 0) & (f < 400)
    pk = float(f[fseek][np.argmax(P[fseek])])
    fc, C = coherence(su - su.mean(), eu - eu.mean(), fs=fs, nperseg=2048)
    ci = int(np.argmin(np.abs(fc - pk)))
    b = float(np.sqrt(P[(f >= 30) & (f < 80)].sum() * (f[1] - f[0])))
    line(f'spectrum maximum sits at **{pk:.2f} Hz**',
         'cruise-window yaw error spectrum, f > 0', artifacts=(ANALYSIS,))
    line(f'setpoint–error coherence there is {C[ci]:.2f}',
         'coherence at the spectrum-maximum bin', artifacts=(ANALYSIS,))
    line(f'holds {b:.2f} deg/s in the same window',
         '30-80 band RMS', artifacts=(ANALYSIS,))
    line(f'(spectrum maximum {pk:.2f} Hz)',
         'the same maximum, reply form', artifacts=(REPLY,))
    line(f'coherence {C[ci]:.2f}',
         'the same coherence, reply form', artifacts=(REPLY,))
    # external-source exact phrases (mutation-hardening): the tester's own
    # axis-weight numbers must appear verbatim where quoted
    line('the 50/30/20 split is equivalent to roll-relative 100/60/40',
         "arithmetic restated from the tester's comment 5322423074; the split "
         'and ratios are his numbers, the 100/60/40 equivalence is 50:30:20 '
         'normalised to roll', artifacts=(REPLY,))
    line('100 / 75–85 / 40–50', "the tester's corrected ratios, quoted verbatim",
         artifacts=(REPLY,))

    hi_end = 2047.0
    import analysis as _a
    hd0 = _a.headers()
    hi_end = float(hd0['motorOutput'].split(',')[1])
    m = np.vstack([col(f'motor[{i}]') for i in range(4)])
    rail = m >= hi_end
    n_rail = int(rail.sum())
    seg = lambda a, b: 100 * rail[:, (t >= a) & (t < b)].sum() / n_rail
    line(f'{seg(0, 150):.1f} % before 150 s, {seg(160, 168.5):.1f} % in 160–168.5 s, '
         f'{seg(168.5, 171.5):.1f} % in the 168.5–171.5 s punch window',
         'per-motor rail-cell distribution over flight segments', artifacts=(ANALYSIS,))
    thr = col('rcCommand[3]')
    late = t >= 168.5
    t_thr = float(t[late][np.argmax(thr[late] >= 2000)])
    t_rail_ = float(t[late][np.argmax(rail[:, late].any(axis=0))])
    line(f'throttle first reaches 2000 at {t_thr:.2f} s', 'first throttle>=2000 sample, t>=168.5',
         artifacts=(ANALYSIS, REPLY))
    line(f'the rail at {t_rail_:.2f} s', 'first per-motor rail sample, t>=168.5',
         artifacts=(ANALYSIS, REPLY))
    g167 = np.vstack([col(f'gyroADC[{i}]') for i in range(3)])
    w167 = (t >= 166.5) & (t < 168.5)
    line(f'gyro peaks ≤ {float(np.abs(g167[:, w167]).max()):.0f} deg/s',
         'max |gyro| over 166.5-168.5 s, the earlier full-throttle excursion',
         artifacts=(ANALYSIS,))

    # provenance: flown b0 vs the comment's worked-example b0 (external numbers,
    # quoted from comment 5322423074)
    b0_flown = [float(x) for x in hd0['adrcB0'].split(',')]
    b0_example = [5945.0, 3567.0, 2378.0]
    pct = 100 * float(np.mean([1 - f / e for f, e in zip(b0_flown, b0_example)]))
    line(f"sits about {pct:.1f} % below the comment's worked-example b0 (5945/3567/2378)",
         'mean per-axis shortfall of flown adrcB0 vs the worked example in comment 5322423074',
         artifacts=(ANALYSIS,))
    line(f"sits about {pct:.1f} % below the comment's worked example 5945/3567/2378",
         'the same shortfall, reply form', artifacts=(REPLY,))

    # unit-bearing claims whose bare tokens also occur elsewhere in the corpus:
    # bind them as exact phrases so a cross-claim substitution cannot pass
    vb = col('vbatLatest (V)')
    amps = col('amperageLatest (A)')
    line(f'it peaks at {float((vb * amps).max()):.2f} W here',
         'peak of vbat*amperage, pack electrical proxy', artifacts=(REPLY,))
    line(f'vbat bottoms at {vb.min():.2f} V', 'whole-flight vbat minimum',
         artifacts=(REPLY,))
    line(f'vbat bottoming at {vb.min():.2f} V', 'the same minimum, ANALYSIS form',
         artifacts=(ANALYSIS,))
    tumble = (t >= 169.5) & (t < 170.5)
    pkt = [float(np.abs(g167[i][tumble]).max()) for i in range(3)]
    line(f'gyro peaks {pkt[0]:.0f}/{pkt[1]:.0f}/{pkt[2]:.0f} deg/s',
         'per-axis |gyro| maxima over the 169.5-170.5 s tumble slices',
         artifacts=(ANALYSIS,))
    line(f'gyro peaks of {pkt[0]:.0f}/{pkt[1]:.0f}/{pkt[2]:.0f} deg/s',
         'the same maxima, reply form', artifacts=(REPLY,))
    after = (t >= 170.5) & (t < 171.0)
    pka = [float(np.abs(g167[i][after]).max()) for i in range(3)]
    line(f'back to {pka[0]:.0f}/{pka[1]:.0f}/{pka[2]:.0f} deg/s',
         'per-axis |gyro| maxima in the 170.5 s slice', artifacts=(ANALYSIS, REPLY))

    import gzip
    hd = analysis.headers()
    wc = [float(x) for x in hd['adrcWC'].split(',')]
    wo = [float(x) for x in hd['adrcWO'].split(',')]
    line(f'`wo/wc = {wo[2]:.0f}/{wc[2]:.0f} ≈ {wo[2]/wc[2]:.2f}`',
         'yaw observer margin from the header', artifacts=(ANALYSIS, REPLY))
    line(f'while roll/pitch sit at {wo[0]/wc[0]:.2f}',
         'roll/pitch observer margin', artifacts=(ANALYSIS,))
    line(f'against {wo[0]/wc[0]:.2f} on roll/pitch',
         'the same roll/pitch margin, reply form', artifacts=(REPLY,))

    print('\nRemaining numbers are traced by the reverse token check, which is a')
    print('weaker guarantee: it draws on one global token pool with no unit or')
    print('context binding, so a number that occurs in any registered claim would')
    print('be accepted anywhere. Unit-bearing claims above are therefore bound as')
    print('exact phrases. The formula and K are quoted from the tester\'s comment')
    print('and are not derived or validated here.')


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
                print(f'  ABSENT  [{want}]: {phrase}')
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
                print(f'  VARIANT [{want}] {phrase}  <- ' + ', '.join(sorted(variants)))
            else:
                print(f'  ok      [{want}] {phrase}')
    print('\n# Reverse\n')
    corpus = io.StringIO()
    with contextlib.redirect_stdout(corpus):
        __import__('analysis').main()
    haystack = corpus.getvalue() + ' ' + ' '.join(p for p, _ in PHRASES)
    token = re.compile(r'(?<![\w.])\d+(?:\.\d+)?')
    known = set(token.findall(haystack))
    UNITS = r'(?:\s*(?:%|Hz|A|V|ms|s\b|deg/s|frames|\u00d7))'
    measured = re.compile(
        r'(?<![\w.])\d+\.\d+(?![\w])'
        r'|(?<![\w.])\d{3,}(?![\w.])'
        r'|(?<![\w.])\d{1,2}(?=' + UNITS + r')')
    ALLOWED = {'15400', '2026',
               '5322423074',   # the source comment id; the tester's axis-weight
                               # numbers are registered as exact forward phrases
                               # above, NOT allowlisted
               '0.68'}         # yaw wo/wc of the b0sweep2 oldtune cells (130/190),
                               # quoted from that campaign's published headers
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
        if 'B0CALC_REPLY' in os.environ:
            sources[REPLY] = os.environ['B0CALC_REPLY']
        sys.exit(check(sources))

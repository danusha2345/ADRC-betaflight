#!/usr/bin/env python3
"""Where the yaw motion lives with the filter chain in and out of the loop.

Matched comparison: 10-s windows (sliding inside each airmode activation
with a 5-s step, so adjacent windows overlap and are NOT independent
samples) restricted to (a) median pack voltage in 7.6-8.2 V and (b) the
BOXAIRMODE box active, in both flights - like pack state, like mixer
authority. Each window's start time and vbat are printed. Still two
different flights on different inputs; every number below is an
observation, not a controlled contrast, and no formal-sample inference is
made from the window counts.

Also measured: the filters-OFF micro-oscillation (error content near the
motor band, attribution loose), and whether the ON flight's ~50 Hz yaw
line is present in the command path.
"""
import numpy as np
from scipy.signal import welch

from common import LOGS, ON, OFF, load, time_s, airmode_windows, headers

VB_LO, VB_HI = 7.6, 8.2
WIN_S = 10
BAND = (30.0, 80.0)


def psd_seg(t, x):
    fs = (len(t) - 1) / (t[-1] - t[0])
    tu = np.arange(t[0], t[-1], 1.0 / fs)
    xu = np.interp(tu, t, x)
    f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(2048, len(xu)))
    return f, P


def band_rms(f, P, lo, hi):
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(P[m].sum() * (f[1] - f[0])))


def matched_windows(stem):
    """Windows slide INSIDE each airmode activation (the ON flight's
    activations are shorter than any fixed grid), step WIN_S/2."""
    d = load(stem)
    t = time_s(d)
    vb = d['vbatLatest (V)']
    wins = airmode_windows(stem, float(t[-1]))
    out = []
    for lo, hi in wins:
        k = lo
        while k + WIN_S <= hi:
            w = (t >= k) & (t < k + WIN_S)
            if w.sum() >= 2000 and VB_LO <= np.median(vb[w]) <= VB_HI:
                out.append((k, w))
            k += WIN_S / 2
    return d, t, out


def main():
    print('# Yaw spectra, matched windows\n')
    print(f'Windows: {WIN_S} s, BOXAIRMODE active throughout, median vbat in '
          f'{VB_LO}-{VB_HI} V.\n')
    results = {}
    for label, stem in LOGS:
        d, t, wins = matched_windows(stem)
        rows = {'gyroUnfilt yaw': [], 'yaw err': [], 'yaw P+D': []}
        peaks, inband, proms = [], [], []
        for k, w in wins:
            ts = t[w]
            series = {
                'gyroUnfilt yaw': d['gyroUnfilt[2]'][w],
                'yaw err': d['setpoint[2]'][w] - d['gyroADC[2]'][w],
                'yaw P+D': d['axisP[2]'][w] + d['axisD[2]'][w],
            }
            for nm, x in series.items():
                f, P = psd_seg(ts, x)
                rows[nm].append(band_rms(f, P, *BAND))
            f, P = psd_seg(ts, d['gyroUnfilt[2]'][w])
            m = (f > 8) & (f < 400)
            peaks.append(float(f[m][np.argmax(P[m])]))
            mb = (f >= BAND[0]) & (f < BAND[1])
            fb, Pb = f[mb], P[mb]
            inb = float(fb[np.argmax(Pb)])
            sel = (fb >= 45) & (fb <= 55)
            prom = float(Pb[sel].max() / np.median(Pb[~sel])) if (~sel).any() else float('inf')
            inband.append(inb)
            proms.append(prom)
        results[label] = (rows, peaks, len(wins))
        print(f'  {stem} - {len(wins)} matched window(s) (overlapping, one flight):')
        print('     window starts: ' + ', '.join(f'{k:.1f}s' for k, w in wins))
        print('     window vbat medians: '
              + ', '.join(f'{np.median(d["vbatLatest (V)"][w]):.2f}' for k, w in wins))
        for nm, vals in rows.items():
            print(f'     {nm:14s} {BAND[0]:.0f}-{BAND[1]:.0f} Hz RMS: median '
                  f'{np.median(vals):7.2f}  (per-window: '
                  + ', '.join(f'{v:.1f}' for v in vals) + ')')
        print(f'     gyroUnfilt peak (8-400 Hz) per window: '
              + ', '.join(f'{p:.0f}' for p in peaks) + ' Hz')
        print('     30-80 Hz band maximum per window: '
              + ', '.join(f'{v:.1f}' for v in inband) + ' Hz')
        print('     45-55 Hz prominence per window (peak PSD in 45-55 over median')
        print('     PSD of the remaining 30-80 band): '
              + ', '.join(f'{v:.0f}x' for v in proms))
        results[label] = results[label] + (inband, proms)
        print()

    on_rows, on_peaks = results['filters ON'][0], results['filters ON'][1]
    on_inband = results['filters ON'][3]
    off_rows = results['filters OFF'][0]
    off_inband = results['filters OFF'][3]
    off_g = float(np.median(off_rows['gyroUnfilt yaw']))
    off_c = float(np.median(off_rows['yaw P+D']))
    dom_ix = [i for i, p in enumerate(on_peaks) if 45 <= p <= 55]
    hf_ix = [i for i in range(len(on_peaks)) if i not in dom_ix]
    lg = float(np.median([on_rows['gyroUnfilt yaw'][i] for i in dom_ix]))
    lc = float(np.median([on_rows['yaw P+D'][i] for i in dom_ix]))
    og = float(np.median([on_rows['gyroUnfilt yaw'][i] for i in hf_ix]))
    oc = float(np.median([on_rows['yaw P+D'][i] for i in hf_ix]))
    on_g = float(np.median(on_rows['gyroUnfilt yaw']))
    on_c = float(np.median(on_rows['yaw P+D']))
    n5055 = sum(1 for v in on_inband if 45 <= v <= 55)
    off_n5055 = sum(1 for v in off_inband if 45 <= v <= 55)
    print('  Presence vs dominance, kept separate. EVERY ON window has its')
    print(f'  30-80 Hz band maximum at 45-55 Hz ({n5055} of {len(on_peaks)}; prominences')
    print('  printed above), so no presence/absence claim is made from the')
    print('  global-peak split below - it separates windows where the ~50 Hz')
    print(f'  component dominates the whole 8-400 Hz spectrum from windows where')
    print(f'  a higher-frequency component does. ({off_n5055} of '
          f'{len(off_inband)} OFF windows also')
    print('  put their in-band maximum at 45-55 Hz - the per-window RMS values')
    print('  printed above are the comparison; no adjective substitutes for them.)')
    print(f'    ~50 Hz globally dominant ON windows (n={len(dom_ix)}): gyro '
          f'{lg:.2f} = {lg / off_g:.1f}x OFF median,')
    print(f'      command {lc:.2f} = {lc / off_c:.1f}x OFF median;')
    print(f'    higher-frequency-dominant ON windows (n={len(hf_ix)}): gyro {og:.2f} = '
          f'{og / off_g:.2f}x, command {oc:.2f} = {oc / off_c:.2f}x;')
    print(f'    pooled ON medians (fall between the subset medians; for')
    print(f'    completeness): gyro {on_g:.2f} = {on_g / off_g:.1f}x, '
          f'command {on_c:.2f} = {on_c / off_c:.1f}x.')
    print('  The band is the same ~50 Hz the Air65 bench corpus pinned across')
    print('  wc 80-120 - here at yaw wc = 50, wo = 80, a different craft and')
    print('  tune. What this pair supports is an ASSOCIATION between the filter-')
    print('  chain state and the measured 30-80 Hz amplitude at a matching')
    print('  intended profile; two non-randomised flights do not establish a')
    print('  causal edge, and magnitude vs phase effects of the chain are not')
    print('  separable here (common.py).')

    print('\nThe filters-OFF micro-oscillation: cruise-window error spectrum')
    print('peaks vs the folded rotor fundamental (eRPM median over the window,')
    print('aliased against the saved-stream rate):')
    for label, stem in LOGS:
        d = load(stem)
        t = time_s(d)
        lo = float(t[-1]) / 2 - 30
        w = (t >= lo) & (t < lo + 60)
        poles = float(headers(stem).get('motor_poles', '12'))
        rot = float(np.median(np.vstack([d[f'eRPM[{i}]'] for i in range(4)])[:, w])
                    * 100.0 / (poles / 2.0) / 60.0)
        fs = (int(w.sum()) - 1) / (t[w][-1] - t[w][0])
        fold = rot % fs
        fold = fs - fold if fold > fs / 2 else fold
        for ax, nm in ((0, 'roll'), (2, 'yaw')):
            e = d[f'setpoint[{ax}]'][w] - d[f'gyroADC[{ax}]'][w]
            f, P = psd_seg(t[w], e)
            m = (f > 5) & (f < 0.48 * fs)
            pk = float(f[m][np.argmax(P[m])])
            print(f'  {stem[:28]:28s} {nm:5s} err peak {pk:5.0f} Hz '
                  f'(rotor 1x ~{rot:.0f} Hz -> aliased ~{fold:.0f} Hz at fs {fs:.0f})')
    print('\n  With the chain off, the OFF flight\'s dominant error content sits in')
    print('  the high hundreds of Hz - the yaw peak lands near the folded rotor')
    print('  fundamental, the roll peak below it; a per-motor order analysis was')
    print('  not attempted, so the attribution stays loose: high-frequency motor-')
    print('  band content passing into the loop unfiltered, which is the visible')
    print('  micro-oscillation in the traces. What the log cannot decide: the')
    print('  long-term costs of flying it (motor heating, wear); the tester')
    print('  reports motors coming back cool on this craft.')


if __name__ == '__main__':
    main()

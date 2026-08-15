#!/usr/bin/env python3
"""Per-configuration yaw metrics inside the airmode segments.

One segment per configuration (the arm's single BOXAIRMODE activation,
taken from the numeric mode mask). For each: yaw 30-80 Hz band RMS of the
unfiltered gyro and of the command (P+D), the 30-80 band's peak frequency,
the 45-55 Hz prominence (peak PSD in 45-55 over the median PSD of the
remaining 30-80 band), motor-rail samples inside the segment, and the
segment's vbat range - the segments sit at different pack states and
different lengths, so the table is a set of seven single observations, not
a controlled comparison. Pilot input differs per arm and is uncontrolled.

The LP1+LP2+RPM segment ends with the arm within seconds of the flip
(vbat sagging hard); its values are censored by whatever ended the arm and
must not be ranked against the full-length segments.
"""
import numpy as np
from scipy.signal import welch

from common import LOGS, headers, load, motors, time_s, airmode_windows

BAND = (30.0, 80.0)
TRIM_S = 0.3          # skip the first fraction of a second after the flip


def seg_metrics(stem):
    d = load(stem)
    t = time_s(d)
    wins = airmode_windows(stem, float(t[-1]))
    lo, hi = wins[0]
    lo += TRIM_S
    w = (t >= lo) & (t < hi)
    ts = t[w]
    fs = (len(ts) - 1) / (ts[-1] - ts[0])

    def psd(x):
        tu = np.arange(ts[0], ts[-1], 1.0 / fs)
        xu = np.interp(tu, ts, x)
        f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(2048, len(xu)))
        return f, P

    def brms(f, P):
        m = (f >= BAND[0]) & (f < BAND[1])
        return float(np.sqrt(P[m].sum() * (f[1] - f[0])))

    f, P = psd(d['gyroUnfilt[2]'][w])
    g = brms(f, P)
    mb = (f >= BAND[0]) & (f < BAND[1])
    fb, Pb = f[mb], P[mb]
    inb = float(fb[np.argmax(Pb)])
    sel = (fb >= 45) & (fb <= 55)
    prom = float(Pb[sel].max() / np.median(Pb[~sel]))
    f2, P2 = psd(d['axisP[2]'][w] + d['axisD[2]'][w])
    c = brms(f2, P2)
    hi_end = float(headers(stem)['motorOutput'].split(',')[1])
    rail = int((motors(d)[:, w] >= hi_end).sum())
    vb = d['vbatLatest (V)'][w]
    return (lo, hi, hi - lo, float(vb.min()), float(vb.max()), g, c, inb, prom, rail)


def main():
    print('# The ladder, inside the airmode segments\n')
    print(f'(first {TRIM_S} s after each flip trimmed; one segment per config)\n')
    print(f'  {"config":14s} {"segment":>13s} {"dur":>5s} {"vbat":>11s} '
          f'{"yaw 30-80 gyro":>14s} {"cmd P+D":>8s} {"band pk":>8s} {"45-55 prom":>10s} {"rail":>5s}')
    rows = {}
    for label, stem in LOGS:
        lo, hi, dur, v0, v1, g, c, inb, prom, rail = seg_metrics(stem)
        rows[label] = (g, c, inb, prom, rail, dur)
        cens = ' *' if label == 'LP1+LP2+RPM' else ''
        print(f'  {label:14s} {lo:5.1f}-{hi:6.1f}s {dur:4.1f}s {v0:5.2f}-{v1:5.2f} '
              f'{g:14.2f} {c:8.1f} {inb:8.1f} {prom:9.0f}x {rail:5d}{cens}')
    print(f'\n  * LP1+LP2+RPM: the segment ends with the arm after '
          f'{rows["LP1+LP2+RPM"][5]:.1f} s (post-trim) with')
    print('    the pack sagging hard - censored, not rankable against the others.')

    print('\nReadings, all within single-observation limits (the prominence is a')
    print('spectral-shape descriptor with no validated threshold - no binary')
    print('presence/absence claims are made from it):')
    off = rows['off']
    print(f'  - the all-off segment\'s 45-55 Hz prominence is {off[3]:.0f}x (band peak')
    print(f'    {off[2]:.1f} Hz); the six on-config segments show prominences of')
    print('    ' + ', '.join(f'{rows[l][3]:.0f}x' for l, _ in LOGS if l != 'off') + ' (ladder order) -')
    print('    a large descriptor difference, directionally consistent with the')
    print('    tester\'s "individually, all do something to some degree".')
    print(f'  - the largest full-length segment values are in a combination cell,')
    print(f'    LP1+RPM (gyro {rows["LP1+RPM"][0]:.2f}, command {rows["LP1+RPM"][1]:.1f}, '
          f'prominence {rows["LP1+RPM"][3]:.0f}x,')
    print(f'    {rows["LP1+RPM"][4]} rail samples in the segment), and its pack sat lower than')
    print('    the single-stage segments. Directionally consistent with his')
    print('    "combined ... multiplies"; with one arm per cell and the LP1+LP2')
    print('    cell not flown, no interaction is estimated.')
    print(f'  - the LP1-only segment shows a larger 30-80 Hz RMS than the LP2-only')
    print(f'    segment: gyro {rows["LP1"][0]:.2f} vs {rows["LP2"][0]:.2f}, '
          f'prominence {rows["LP1"][3]:.0f}x vs {rows["LP2"][3]:.0f}x -')
    print('    one segment each, and the LP2 arm ran on a different measured RC')
    print('    link rate (overview.py prints the per-arm values).')
    print(f'  - the RPM-only arm jointly shows whole-log error medians of 4/4/5')
    print(f'    deg/s (overview.py; those mix pre-airmode hover with the segment)')
    print(f'    and a segment 30-80 Hz gyro RMS of {rows["RPM"][0]:.2f} deg/s with zero rail')
    print('    samples. Stated as the joint observation on one arm - not a')
    print('    ranking and not a buzz-removal proof. One arm per cell;')
    print('    conditions and input uncontrolled.')


if __name__ == '__main__':
    main()

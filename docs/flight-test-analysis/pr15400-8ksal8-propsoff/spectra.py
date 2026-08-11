#!/usr/bin/env python3
"""Where the props-off motion actually is: which axis, and in which band.

A single "gyro amplitude" number hides the answer here. Split per axis and per
band, and two things separate that a pooled figure does not:

  - the props-off motion is almost entirely YAW, in a band around 50 Hz;
  - the 18-26 Hz roll/pitch oscillation that ran the craft to the motor rail
    WITH props fitted is essentially absent here.

Band edges are fixed in advance rather than fitted to the data: 0-8 Hz is
handling and bench motion, 8-30 Hz covers the props-on runaway, 30-80 Hz covers
what dominates here, 80-400 Hz is the rest up to the usable limit of a
decimated log.
"""
import numpy as np
from scipy.signal import welch

from common import (GROUPS, load, time_s, gyro, fs_nominal, resample_uniform,
                    rotor_hz_per_motor, alias_of)

BANDS = [('0-8', 0.0, 8.0), ('8-30', 8.0, 30.0), ('30-80', 30.0, 80.0),
         ('80-400', 80.0, 400.0)]
NPERSEG = 2048
AXES = [(0, 'roll'), (1, 'pitch'), (2, 'yaw')]


def psd(d, ax):
    """PSD of one axis on an explicitly resampled uniform grid."""
    t = time_s(d)
    fs = fs_nominal(d)
    x = gyro(d, filtered=False)[ax]
    tu, xu = resample_uniform(t, x, fs)
    f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(NPERSEG, len(xu)))
    return f, P, fs


def band_rms(f, P, lo, hi):
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(P[m].sum() * (f[1] - f[0])))


def main():
    print('# Where the motion is\n')
    print(f'Welch, nperseg={NPERSEG}, on gyroUnfilt resampled to a uniform grid.')
    print('Values are RMS in deg/s inside each band, median over the four arms.\n')

    head = f'  {"group":30s} {"axis":6s}' + ''.join(f'{b[0] + " Hz":>10s}' for b in BANDS) + f'{"peak Hz":>9s}'
    print(head)
    table = {}
    for label, ctrl, air, sub, stems in GROUPS:
        for ax, axname in AXES:
            rows, peaks = [], []
            for stem in [f'{sub}_{s}' for s in stems]:
                f, P, fs = psd(load(stem), ax)
                rows.append([band_rms(f, P, lo, hi) for _, lo, hi in BANDS])
                m = (f > 8) & (f < 400)
                peaks.append(float(f[m][np.argmax(P[m])]))
            med = np.median(np.array(rows), axis=0)
            table[(label, axname)] = med
            print(f'  {label:30s} {axname:6s}'
                  + ''.join(f'{v:10.2f}' for v in med) + f'{np.median(peaks):9.1f}')
        print()

    print('The comparison that matters, yaw in the 30-80 Hz band:\n')
    for label, *_ in GROUPS:
        print(f'  {label:30s} {table[(label, "yaw")][2]:8.2f} deg/s RMS')
    a_on = table[('ADRC, Airmode feature on', 'yaw')][2]
    a_off = table[('ADRC, Airmode feature off', 'yaw')][2]
    c_on = table[('CLASSIC, Airmode feature on', 'yaw')][2]
    c_off = table[('CLASSIC, Airmode feature off', 'yaw')][2]
    print(f'\n  ADRC over CLASSIC: {a_on / c_on:.1f}x with the Airmode feature on, '
          f'{a_off / c_off:.1f}x with it off.')
    print('  Read that against the uncontrolled profile differences printed by')
    print('  provenance.py - in particular the CLASSIC profile has NO yaw D at all.')

    print('\nAnd the band the props-on runaway lived in, 8-30 Hz on roll and pitch,')
    print('measured with THE SAME estimator on both corpora (an earlier draft compared')
    print('a filtered-gyro peak against a band RMS, which are not the same quantity):\n')
    for label, *_ in GROUPS:
        r = table[(label, 'roll')][1]
        pp = table[(label, 'pitch')][1]
        print(f'  {label:30s} roll {r:6.2f}, pitch {pp:6.2f} deg/s RMS')
    print()
    import os
    arming = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'pr15400-8ksal8-arming')
    # A separate decode cache is essential here: the stem b9_Airmode_on_ADRC_btfl_002
    # exists in BOTH corpora, and a shared _decoded/ would silently serve the
    # props-off log in place of the props-on one (it did, in an earlier run).
    arming_cache = os.path.join(arming, '_decoded')
    prop_on_vals = []
    for stem in ('b8_Airmode_on_ADRC_btfl_001', 'b9_Airmode_on_ADRC_btfl_002'):
        d = load(stem, workdir=arming_cache, basedir=arming)
        t = time_s(d)
        fs = fs_nominal(d)
        vals = []
        for ax in (0, 1):
            x = gyro(d, filtered=False)[ax]
            tu, xu = resample_uniform(t, x, fs)
            f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(NPERSEG, len(xu)))
            vals.append(band_rms(f, P, 8.0, 30.0))
        prop_on_vals += vals
        print(f'  props-on {stem:32s} roll {vals[0]:6.1f}, pitch {vals[1]:6.1f} deg/s RMS')
    worst = max(table[(label, ax)][1] for label, *_ in GROUPS for ax in ('roll', 'pitch'))
    ratios = [v / worst for v in prop_on_vals]
    print(f'\n  On the same metric the props-on events are {min(ratios):.0f}\u2013{max(ratios):.0f}\u00d7 the'
          f' worst props-off group median')
    print(f'  ({", ".join(f"{r:.2f}" for r in ratios)} against {worst:.5f}). arms.py has the')
    print('  motor and rail counts.')

    print('\nIs the yaw line a rotor order? Per motor, with aliases folded against the')
    print('real sample rate - a pooled all-motor median is NOT a valid test, and an')
    print('earlier version of this script used one and wrongly ruled a rotor order out.\n')
    print(f'  {"log":34s} {"motor rates Hz":>26s} {"yaw peak":>9s}  nearest 1x order (aliased)')
    for label, ctrl, air, sub, stems in GROUPS:
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            fs = fs_nominal(d)
            rates = rotor_hz_per_motor(d, stem)
            f, P, _ = psd(d, 2)
            m = (f > 8) & (f < 400)
            peak = float(f[m][np.argmax(P[m])])
            folded = [alias_of(r, fs) for r in rates]
            best = min(range(4), key=lambda i: abs(folded[i] - peak))
            print(f'  {stem:34s} {"/".join(f"{r:.0f}" for r in rates):>26s} '
                  f'{peak:9.1f}  motor {best + 1}: {rates[best]:.1f} -> '
                  f'{folded[best]:.1f} Hz (|d| = {abs(folded[best] - peak):.1f})')
    print('\n  The medians above collapse time. Folding EVERY saved frame\'s per-motor')
    print('  rate against that arm\'s average frame rate - itself an approximation,')
    print('  since the frame intervals are irregular with gaps up to ~30 ms - the')
    print('  time-varying 1x does brush the yaw line in every ADRC arm:\n')
    print(f'  {"log":34s} {"min |1x-peak|":>14s} {"frames within 2 Hz":>19s}')
    from common import headers as _hdrs, ERPM_SCALE
    for label, ctrl, air, sub, stems in GROUPS:
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            fs = fs_nominal(d)
            poles = float(_hdrs(stem).get('motor_poles', '12'))
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
            print(f'  {stem:34s} {dmin.min():13.2f}Hz {int((dmin < 2).sum()):8d} '
                  f'({100.0 * float((dmin < 2).mean()):.2f}%)')
    print('\n  So the defensible statements are these. Per-motor MEDIAN 1x orders')
    print('  reproduce the CLASSIC near-coincidence, and no ADRC per-motor MEDIAN 1x,')
    print('  folded at the arm-average frame rate, is closer than 92.1 Hz to the line.')
    print('  The shaft rates of the four ADRC feature-ON arms (457-611 Hz) all exceed')
    print('  the ~402 Hz Nyquist of the saved stream; the feature-off arms (146-171 Hz)')
    print('  do not. And because the time-varying 1x crosses the line briefly in every')
    print('  ADRC arm, this corpus does NOT rule out a 1x contribution - nor establish')
    print('  one. Separating that needs an order tracker on the real timestamps')
    print('  (integrate motor phase from eRPM(t), estimate 1x amplitude/coherence),')
    print('  not a comparison of medians.')


if __name__ == '__main__':
    main()

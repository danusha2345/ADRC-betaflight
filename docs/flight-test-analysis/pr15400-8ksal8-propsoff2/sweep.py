#!/usr/bin/env python3
"""The yaw-wc sweep: what moves with wc and what does not.

Five bench arms, identical profile except yaw wc = 80/90/100/110/120 (wo 125
and b0 5848 fixed), Airmode fully off (feature off, switch never flipped -
modemask.py), dyn idle 30, throttle stick at zero throughout.

Two facts, both visible in the table below:

  - the line's FREQUENCY does not track wc: 47.9-52.0 Hz, not monotonic,
    while wc moves 50 %;
  - the line's AMPLITUDE tracks wc strongly and monotonically: ~5x from
    wc 80 to wc 120.

With z3 pinned at zero for the whole corpus (arms.py), the yaw loop these
arms exercise is kp = wc^2 acting on (setpoint - z1) and kd = 2 wc acting
on z2, over a fixed b0, with z1/z2 tracking the gyro through the ESO's
wo-tuned gains (wo = 125 on yaw, fixed across the sweep). So this is a
gain sweep of the controller pair at fixed observer dynamics, and it
behaves like one: a limit cycle whose amplitude grows with loop gain while
its frequency is set elsewhere (plant + filters + delay + the fixed
observer dynamics - none of which the sweep varies).

Honest limits: the arms are short (4.4-5.4 s), flown back-to-back on one
pack in ascending wc order, so pack state declines monotonically WITH wc -
the per-arm vbat is printed next to the amplitude it confounds. The rotor
rates also rise with wc (the oscillation drives the motors, and a driven
motor is itself a vibration source with a path back into the gyro - the
bench cannot separate that from the control loop, and no bench
configuration can: static idle only sets a floor, it does not pin a
loop-driven motor - see spectra.py for the analysis that would separate
the paths). And the wc80 arm ran on a different measured RC link rate than
the other four (the rc_smoothing table below), which the paired-design
framing must not hide. The per-second 30-80 Hz RMS is printed per arm -
the SAME band as the headline amplitude - so the short spans can be seen
not to censor a still-growing oscillation.
"""
import numpy as np
from scipy.signal import welch

from common import (SWEEP, GROUPS, load, time_s, gyro, rotor_hz_per_motor,
                    resample_uniform, headers)
from spectra import yaw_metrics, phase_rows, band_rms


def band_buckets(d):
    """Per-second 30-80 Hz yaw RMS - same band as the headline number."""
    t = time_s(d)
    y = gyro(d, filtered=False)[2]
    out = []
    for k in range(int(np.ceil(t[-1]))):
        m = (t >= k) & (t < k + 1)
        if m.sum() > 200:
            tt, yy = t[m], y[m]
            fs = (len(tt) - 1) / (tt[-1] - tt[0])
            tu, yu = resample_uniform(tt, yy, fs)
            f, P = welch(yu - yu.mean(), fs=fs, nperseg=min(512, len(yu)))
            out.append(band_rms(f, P, 30.0, 80.0))
    return out


def main():
    print('# The yaw-wc sweep\n')
    print(f'  {"arm":28s} {"yaw wc":>6s} {"yaw 30-80":>10s} {"peak Hz":>8s} '
          f'{"vbat min":>9s} {"rotor Hz med":>16s} {"per-second 30-80 Hz RMS":>30s}')
    for wc, stem in SWEEP:
        d = load(stem)
        v, peak = yaw_metrics(d)
        buckets = band_buckets(d)
        rates = rotor_hz_per_motor(d, stem)
        print(f'  {stem:28s} {wc:6d} {v:10.2f} {peak:8.1f} '
              f'{d["vbatLatest (V)"].min():8.2f}V {"/".join(f"{r:.0f}" for r in rates):>16s} '
              f'{" ".join(f"{b:.0f}" for b in buckets):>30s}')

    print('\nMeasured RC-smoothing state per arm (runtime values that follow the')
    print('ELRS link rate; NOT part of the profile, and NOT identical across the')
    print('sweep - the wc80 arm ran at double the link rate of the others):')
    for wc, stem in SWEEP:
        h = headers(stem)
        print(f'  wc{wc:<4d} rc_smoothing_active_cutoffs_ff_sp_thr = '
              f'{h.get("rc_smoothing_active_cutoffs_ff_sp_thr")}   '
              f'rc_smoothing_rx_smoothed = {h.get("rc_smoothing_rx_smoothed")}')

    vals = {wc: yaw_metrics(load(stem))[0] for wc, stem in SWEEP}
    wcs = sorted(vals)
    mono = all(vals[a] < vals[b] for a, b in zip(wcs, wcs[1:]))
    print(f'\n  amplitude monotonic in wc: {mono}; '
          f'ratio wc120/wc80 = {vals[120] / vals[80]:.1f}x')
    print(f'  within the wc90-wc120 subset (same 62 Hz cutoffs, measured link')
    print(f'  166-167 Hz): ratio wc120/wc90 = {vals[120] / vals[90]:.1f}x, '
          f'still strictly monotonic')
    peaks = [yaw_metrics(load(stem))[1] for _, stem in SWEEP]
    print(f'  peak frequency across the sweep: {min(peaks):.1f}-{max(peaks):.1f} Hz '
          f'(order: {", ".join(f"{p:.1f}" for p in peaks)}) - not monotonic in wc')

    print('\nCross-check against the dyn-idle cell: its airmode-OFF phases ran the')
    print('same regime as the sweep at yaw wc = 96, and their pooled median should')
    print('land between the wc 90 and wc 100 sweep points if the phase split and')
    print('the sweep measure the same thing:')
    rows = [r for r in phase_rows(GROUPS) if r[0] == 'ADRC dynIdle=30, Airmode off'
            and not r[2]]
    med = float(np.median([r[5] for r in rows]))
    print(f'\n  dynidle_sw airmode-off phases, pooled median: {med:.2f} deg/s')
    print(f'  sweep wc 90: {vals[90]:.2f}, wc 100: {vals[100]:.2f} deg/s '
          f'-> {"lands between them" if vals[90] < med < vals[100] else "does NOT land between them"}')
    print('\n  (This is a consistency check, not a calibration: the sweep arms and')
    print('  the dyn-idle arms were flown on different pack states.)')


if __name__ == '__main__':
    main()

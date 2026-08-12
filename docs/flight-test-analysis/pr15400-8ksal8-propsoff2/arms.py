#!/usr/bin/env python3
"""Per-arm basics: spans, motors, rotor rates, and the ADRC-side state.

Two facts here carry the interpretation of everything downstream:

  - in every ADRC arm the liftoff gate stayed shut (debug[7] < 0 throughout)
    and the logged z3 is exactly zero on all three axes for the whole arm
    (which bounds the runtime |z3| at half the log scale, i.e. <= 8, since
    the channel stores lrintf(z3/16)). axisI - which ADRC reports as -z3/b0 -
    is identically zero too. So the disturbance channel never enters the
    loop, and what oscillates is carried by the P and D terms (yaw F is
    negligible in these arms - the count and max are printed below; the
    firmware still sums F and S after the ADRC P/I/D). NB the P and D
    terms act on the OBSERVER states, not the raw gyro: P =
    kp*(vRef - z1)/b0 and D = -kd*z2/b0 (adrc.c), and z1/z2 keep tracking
    the measured rate through the wo-tuned ESO gains even with the gate
    shut. "PD-only" here means "no z3", not "no observer".
  - the motors never touch the upper endpoint, so none of this is the
    props-on runaway; it is a bounded oscillation.
"""
import numpy as np

from common import (GROUPS, SWEEP, LOGS, headers, load, motors, time_s,
                    fs_nominal, rotor_hz_per_motor, DEBUG_CLIP)


def all_stems():
    for g, stem, ctrl, air in LOGS:
        yield stem, ctrl
    for wc, stem in SWEEP:
        yield stem, 'ADRC'


def main():
    print('# Per-arm basics\n')
    hdr = (f'  {"log":30s} {"span":>6s} {"fs":>7s} {"motor med":>10s} {"motor max":>10s} '
           f'{"rail":>5s} {"vbat min":>9s} {"rotor Hz (per motor)":>22s}')
    print(hdr)
    for stem, ctrl in all_stems():
        d = load(stem)
        t = time_s(d)
        m = motors(d)
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        rates = rotor_hz_per_motor(d, stem)
        print(f'  {stem:30s} {t[-1]:5.1f}s {fs_nominal(d):6.1f} {np.median(m):10.0f} '
              f'{m.max():10.0f} {int((m >= hi).sum()):5d} '
              f'{d["vbatLatest (V)"].min():8.2f}V {"/".join(f"{r:.0f}" for r in rates):>22s}')

    print('\n  fs is the average saved-frame rate (reporting only; the grid is not')
    print('  uniform). rotor rates are medians over the arm - the dyn-idle ADRC')
    print('  arms sit far above the 50 Hz shaft rate that dyn_idle_min_rpm = 30')
    print('  (3000 rpm) would hold, because the oscillation itself drives them.')

    print('\nADRC-side state, whole arm (13 ADRC logs):')
    print(f'  {"log":30s} {"gate":>10s} {"z3 R/P/Y nonzero frames":>25s} '
          f'{"axisI nonzero":>14s} {"yaw axisF nz / max|F|":>21s}')
    for stem, ctrl in all_stems():
        if ctrl != 'ADRC':
            continue
        d = load(stem)
        gate_open = int((d['debug[7]'] > 0).sum())
        z3nz = [int((d[f'debug[{i}]'] != 0).sum()) for i in (2, 5, 6)]
        inz = int(sum((d[f'axisI[{ax}]'] != 0).sum() for ax in range(3)))
        fnz = int((d['axisF[2]'] != 0).sum())
        fmax = float(np.abs(d['axisF[2]']).max())
        print(f'  {stem:30s} {"OPEN " + str(gate_open) if gate_open else "shut":>10s} '
              f'{"/".join(str(v) for v in z3nz):>25s} {inz:14d} '
              f'{fnz:10d} / {fmax:5.0f}')
    print('\n  "shut" = debug[7] (sign carries the liftoff gate) never positive.')
    print('  z3 channels are debug[2]/[5]/[6] = lrintf(z3/16); an all-zero channel')
    print('  bounds runtime |z3| <= 8 for the whole arm. axisI is reported as')
    print('  -z3/b0, and its being identically zero is the same fact seen through')
    print('  the second window. The z3 debug rail (|value| = ' + str(DEBUG_CLIP) + ') is never')
    print('  approached anywhere in this corpus.')


if __name__ == '__main__':
    main()

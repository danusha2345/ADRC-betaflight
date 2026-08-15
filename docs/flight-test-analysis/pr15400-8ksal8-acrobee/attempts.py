#!/usr/bin/env python3
"""The seven airmode activations of the filters-ON flight, and the end of it.

The tester's report: "on a fresh bat with filters on, Airmode would turn the
quad into a flyaway. It wasn't until around mid pack I could fly with
Airmode on." The mode mask plus battery voltage let that be read directly
off the log: seven activations, each with its duration, the pack voltage at
its start, and what the craft did inside it. The OFF flight is the control:
one activation from 10 s to the end of the pack.

"Flyaway" is the tester's word; the mask records only that the early
activations were short and started at higher pack voltage - consistent
with his reported bail-outs, but intent is his account, not a log field.
Whether an uninterrupted early-pack activation would have diverged is not
knowable from a short one.
"""
import numpy as np

from common import ON, OFF, load, motors, time_s, headers, airmode_windows


def main():
    print('# Airmode activations, filters-ON flight\n')
    d = load(ON)
    t = time_s(d)
    m = motors(d)
    hi_end = float(headers(ON)['motorOutput'].split(',')[1])
    wins = airmode_windows(ON, float(t[-1]))
    print(f'  {"start":>7s} {"dur":>6s} {"vbat@start":>10s} {"peak|gyro| R/P/Y":>20s} '
          f'{"rail":>6s} {"yaw errRMS":>10s}')
    durs, vstarts, yerrs = [], [], []
    for lo, hi in wins:
        w = (t >= lo) & (t < hi)
        vb = float(np.median(d['vbatLatest (V)'][(t >= lo) & (t < lo + 1)]))
        pk = [float(np.abs(d[f'gyroADC[{ax}]'][w]).max()) for ax in range(3)]
        rail = int((m[:, w] >= hi_end).sum())
        yerr = d['setpoint[2]'][w] - d['gyroADC[2]'][w]
        yrms = float(np.sqrt(np.mean(yerr ** 2)))
        print(f'  {lo:6.1f}s {hi - lo:5.1f}s {vb:9.2f}V '
              f'{"/".join(f"{p:.0f}" for p in pk):>20s} {rail:6d} '
              f'{yrms:10.1f}')
        durs.append(hi - lo)
        vstarts.append(vb)
        yerrs.append(yrms)
    short = [i for i in range(len(durs)) if durs[i] < 5.0]
    long_ = [i for i in range(len(durs)) if durs[i] >= 5.0]
    print(f'\n  The pattern the tester described, as recorded: the {len(short)} activations')
    print(f'  shorter than 5 s all started at {min(vstarts[i] for i in short):.2f} V or above')
    print(f'  (consistent with the reported bail-outs - intent is the tester\'s')
    print(f'  account, not a log field); the {len(long_)} longer ones '
          f'({min(durs[i] for i in long_):.1f}-{max(durs[i] for i in long_):.1f} s) all')
    print(f'  started at {max(vstarts[i] for i in long_):.2f} V or below.')
    print(f'  Across the first six chronological activations the yaw error RMS')
    print(f'  decreases ({yerrs[0]:.1f} -> {yerrs[5]:.1f}) while start voltage generally')
    print(f'  decreases - the variables co-vary (with pilot input and duration')
    print(f'  uncontrolled) and no voltage effect is identified. The seventh')
    print(f'  window contains the terminal high-rate event and breaks the')
    print(f'  ordering ({yerrs[6]:.1f}) - the full')
    print('  sequence is in the table, nothing is excluded silently. Duration vs')
    print('  start voltage is consistent with the report; not a controlled')
    print('  voltage experiment (pack voltage, elapsed time and pilot caution')
    print('  all fall together).')

    print('\nThe control: airmode in the filters-OFF flight')
    d2 = load(OFF)
    t2 = time_s(d2)
    wins2 = airmode_windows(OFF, float(t2[-1]))
    for lo, hi in wins2:
        vb = float(np.median(d2['vbatLatest (V)'][(t2 >= lo) & (t2 < lo + 1)]))
        print(f'  {lo:6.1f}-{hi:6.1f}s ({hi - lo:5.1f}s), started at {vb:.2f} V - the whole')
    print('  usable pack, including the fresh-pack region where the ON flight\'s')
    print('  activations stayed short.')

    print('\nThe end of the filters-ON flight (last four 2-s slices):')
    for lo in np.arange(max(0, t[-1] - 8), t[-1] - 1, 2):
        w = (t >= lo) & (t < lo + 2)
        pk = [float(np.abs(d[f'gyroADC[{ax}]'][w]).max()) for ax in range(3)]
        thr = d['rcCommand[3]'][w]
        print(f'  {lo:6.1f}s gyro peak {"/".join(f"{p:.0f}" for p in pk):>18s} '
              f'throttle {thr.min():.0f}-{thr.max():.0f} motors max {m[:, w].max():.0f} '
              f'vbat min {d["vbatLatest (V)"][w].min():.2f} V')
    print('\n  The final slice peaks above 2000 deg/s on all three axes with motors')
    print('  at the rail and the pack sagging to its minimum - a terminal')
    print('  high-rate event of unknown type (a tumble, crash, catch or hard')
    print('  landing are all consistent with it). It falls INSIDE the last,')
    print('  longest airmode activation, at the very end of a deeply sagged')
    print('  pack; one terminal event in one flight supports no conclusion')
    print('  about the tune.')


if __name__ == '__main__':
    main()

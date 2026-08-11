#!/usr/bin/env python3
"""Per-arm behaviour across the sixteen props-off logs.

The question this answers is narrow and is the whole point of taking the props
off: does the arm-time runaway seen with props fitted still occur? Motor
saturation is the criterion, because that is what the props-on event reached
within 200 ms.
"""
import numpy as np

from common import (GROUPS, headers, load, time_s, gyro, motors, gate_open_state,
                    z3_logged, clipped_frames)


def upper(stem):
    return float(headers(stem)['motorOutput'].split(',')[1])


def main():
    print('# Per-arm behaviour\n')
    print('"rail" counts frames with any motor at that log\'s own upper endpoint;')
    print('the endpoint is 2047 in every log here, but the lower one is not shared -')
    print('see provenance.py. Gyro figures are max over the three axes per frame.\n')
    print(f'  {"log":34s} {"span":>7s} {"gyro med":>9s} {"gyro max":>9s} '
          f'{"rail":>6s} {"Imax":>7s} {"gate":>6s} {"z3!=0":>6s}')
    per_group = {}
    for label, ctrl, air, sub, stems in GROUPS:
        rows = []
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            t = time_s(d)
            peak = np.abs(gyro(d)).max(axis=0)
            m = motors(d)
            rail = int((m.max(axis=0) >= upper(stem)).sum())
            if headers(stem)['debug_mode'] == '102':
                gate = 'open' if gate_open_state(d).any() else 'shut'
                z3 = z3_logged(d)
                nz = int(np.sum((z3['R'] != 0) | (z3['P'] != 0) | (z3['Y'] != 0)))
                nzs = str(nz)
            else:
                gate, nz, nzs = '-', -1, '-'
            print(f'  {stem:34s} {t[-1]:6.2f}s {np.median(peak):9.1f} {peak.max():9.0f} '
                  f'{rail:6d} {d["amperageLatest (A)"].max():6.2f}A {gate:>6s} {nzs:>6s}')
            rows.append((t[-1], np.median(peak), peak.max(), rail,
                         d['amperageLatest (A)'].max()))
        per_group[label] = np.array(rows)
        print()

    print('Group medians over four arms each:\n')
    print(f'  {"group":30s} {"span":>7s} {"gyro med":>9s} {"gyro max":>9s} '
          f'{"rail":>6s} {"Imax":>7s}')
    for label, *_ in GROUPS:
        r = per_group[label]
        print(f'  {label:30s} {np.median(r[:, 0]):6.2f}s {np.median(r[:, 1]):9.1f} '
              f'{np.median(r[:, 2]):9.0f} {np.median(r[:, 3]):6.0f} '
              f'{np.median(r[:, 4]):6.2f}A')

    total_rail = int(sum(per_group[l][:, 3].sum() for l, *_ in GROUPS))
    print(f'\n  Frames at the motor rail across all sixteen arms: {total_rail}.')
    print('  With props fitted, two arms of five reached it, at 176.480 and 182.802 ms.')

    print('\nPeak-current frame of each ADRC arm - setpoints and motor commands.')
    print('This is what "the control path working, not a static idle floor" rests on:')
    for label, ctrl, air, sub, stems in GROUPS:
        if ctrl != 'ADRC':
            continue
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            k = int(np.argmax(d['amperageLatest (A)']))
            sp = [d[f'setpoint[{i}]'][k] for i in range(3)]
            mo = [int(d[f'motor[{i}]'][k]) for i in range(4)]
            print(f'  {stem}: {d["amperageLatest (A)"][k]:.2f} A, setpoints '
                  f'{sp[0]:.0f}/{sp[1]:.0f}/{sp[2]:.0f}, motors '
                  f'{mo[0]}/{mo[1]}/{mo[2]}/{mo[3]}')

    print('\nThe gate and the disturbance estimate in the eight ADRC arms:')
    for label, ctrl, air, sub, stems in GROUPS:
        if ctrl != 'ADRC':
            continue
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            print(f'  {stem}: gate open in {int(gate_open_state(d).sum())}/{d["_n"]} '
                  f'frames, debug-channel clips {clipped_frames(d)}')
    print('\n  All eight arms here are b9, where the growth inhibit is keyed on the gate')
    print('  alone, so with the gate shut in every saved frame the internal z3 is exactly')
    print('  zero by the source state machine - no assumption about unlogged intervals is')
    print('  needed. That does NOT retroactively cover the b8 log in the props-on set:')
    print('  there the inhibit also required throttleAtIdle and the first 167.5 ms are')
    print('  unrecorded, so its z3 claim keeps its original proviso.')


if __name__ == '__main__':
    main()

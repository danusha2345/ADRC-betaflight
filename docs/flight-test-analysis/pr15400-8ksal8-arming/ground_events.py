#!/usr/bin/env python3
"""The four ground logs: what separates the two runaways from the two quiet arms.

Deliberately reports distribution statistics rather than single-sample maxima -
a lone peak frame is not an amplitude, and a lone peak frame is not evidence
that one control term dominates.
"""
import numpy as np

from common import (load, time_s, gyro, motors, z3_logged, clipped_frames,
                    gate_open_state, acc_1g)

GROUND = ['b8_Airmode_on_ADRC_btfl_001', 'b9_Airmode_on_ADRC_btfl_002',
          'b9_Airmode_on_PID_btfl_004', 'b9_Airmode_switch_PID_btfl_005']
AXES = 'RPY'


def onset(t, peak, level):
    idx = np.where(peak > level)[0]
    return t[idx[0]] * 1e3 if idx.size else None


def main():
    print('# Ground logs\n')
    print('Amplitude of the body-rate excursion. "sustained" = last 200 ms of the log,')
    print('which for 001/002 is well inside the developed oscillation.\n')
    hdr = (f'{"log":34s} {"onset>20":>9s} {"onset>100":>10s} '
           f'{"sust.med":>9s} {"sust.RMS":>9s} {"sust.max":>9s} {"1-frame max":>12s}')
    print(hdr)
    for stem in GROUND:
        d = load(stem)
        t = time_s(d)
        peak = np.abs(gyro(d)).max(axis=0)
        sust = t > t[-1] - 0.200
        o20, o100 = onset(t, peak, 20), onset(t, peak, 100)
        print(f'{stem:34s} '
              f'{(f"{o20:.1f} ms" if o20 else "never"):>9s} '
              f'{(f"{o100:.1f} ms" if o100 else "never"):>10s} '
              f'{np.median(peak[sust]):9.1f} {np.sqrt(np.mean(peak[sust]**2)):9.1f} '
              f'{peak[sust].max():9.0f} {peak.max():12.0f}')
    print('\nUnits: deg/s, max over the three axes of the filtered gyro, per frame.')

    print('\nMotor saturation (motorOutput range is 158..2047).')
    print('"first at rail" is the first frame with any motor at 2047 - a different and')
    print('later event than the first excursion above 100 deg/s printed above.\n')
    print(f'{"log":34s} {"frames":>7s} {"any at 2047":>13s} {"first at rail":>14s} '
          f'{"vs >100":>9s} {"at 158":>8s} {"max current":>12s}')
    for stem in GROUND:
        d = load(stem)
        t = time_s(d)
        m = motors(d)
        railed = m.max(axis=0) >= 2047
        first = f'{t[np.argmax(railed)]*1e3:.3f} ms' if railed.any() else 'never'
        peak = np.abs(gyro(d)).max(axis=0)
        o100 = onset(t, peak, 100)
        delta = (f'{t[np.argmax(railed)]*1e3 - o100:+.1f}'
                 if railed.any() and o100 is not None else '-')
        print(f'{stem:34s} {d["_n"]:7d} '
              f'{int(railed.sum()):6d} ({100*railed.mean():5.1f}%) {first:>14s} '
              f'{delta:>9s} {int((m.min(axis=0) <= 158).sum()):8d} '
              f'{d["amperageLatest (A)"].max():10.2f} A')

    print('\nPack, and what it does during the event (1S; sag compensation is off, so')
    print('motorOutputRange does not move and these numbers do not distort the rest):\n')
    print(f'{"log":34s} {"vbat first":>11s} {"vbat last":>10s} {"vbat min":>9s} {"vbat max":>9s}')
    for stem in GROUND:
        v = load(stem)['vbatLatest (V)']
        print(f'{stem:34s} {v[0]:10.2f}V {v[-1]:9.2f}V {v.min():8.2f}V {v.max():8.2f}V')
    print('\nThe mean of the four motor outputs is NOT commanded collective: in a saturated')
    print('differential mix it rises with the spread alone. Commanded collective is')
    print('setpoint[3], which is 0 in every frame of all four logs.')

    print('\nGate and disturbance estimate:\n')
    for stem in GROUND:
        d = load(stem)
        open_frames = int(gate_open_state(d).sum())
        z3 = z3_logged(d)
        nz = {k: int(np.sum(v != 0)) for k, v in z3.items()}
        print(f'  {stem}: gate open in {open_frames}/{d["_n"]} frames; '
              f'non-zero logged z3 frames R/P/Y = {nz["R"]}/{nz["P"]}/{nz["Y"]}; '
              f'debug-channel clips {clipped_frames(d)}')
    print('\n  A logged zero bounds |z3| <= 8 only: the field is lrintf(z3/16), and lrintf')
    print('  follows the current floating-point rounding mode (round-to-nearest,')
    print('  ties-to-even by default) rather than rounding halves away from zero, which')
    print('  is lroundf. That z3 is *exactly* zero is a source argument:')
    print('  on b9 the growth inhibit is keyed on !liftoff alone, the gate is closed in')
    print('  every saved frame, and nothing closes a gate mid-epoch except a reset that')
    print('  also zeroes z3 - so the b9 logs need no further assumption. On b8 the inhibit')
    print('  additionally requires throttleAtIdle, which the unlogged first 167.5 ms cannot')
    print('  confirm, so 001 keeps that proviso. See ANALYSIS.md section 5.')

    print('\nD versus P, aggregated over the first 100 ms and over the whole log.')
    print('This is the term-dominance test. If it separated runaway from quiet arms it')
    print('would be a signature; the point of printing all four logs is that it does not.\n')
    print(f'{"log":34s} {"window":>10s} ' + ' '.join(f'{"D/P " + a:>8s}' for a in AXES))
    for stem in GROUND:
        d = load(stem)
        t = time_s(d)
        for label, mask in (('0-100 ms', t < 0.100), ('whole log', np.ones_like(t, bool))):
            ratios = []
            for ax in range(3):
                P = d[f'axisP[{ax}]'][mask]
                D = d[f'axisD[{ax}]'][mask]
                rp = np.sqrt(np.mean(P ** 2))
                ratios.append(np.sqrt(np.mean(D ** 2)) / rp if rp > 0 else float('nan'))
            print(f'{stem:34s} {label:>10s} ' + ' '.join(f'{r:8.2f}' for r in ratios))
    print('\nRatios are RMS(D)/RMS(P) over the window, per axis, from the logged axisD/axisP.')
    print('axisD[2] (yaw) is only present because b8/b9 log it unconditionally under ADRC.')

    print('\nStarting conditions, first 100 ms (the arms are close but not identical):\n')
    print(f'{"log":34s} {"|acc|":>7s} {"acc sd":>7s} {"mean motor":>11s} {"mean A":>8s} {"gyro RMS":>9s}')
    for stem in GROUND:
        d = load(stem)
        t = time_s(d)
        m = t < 0.100
        acc = np.vstack([d[f'accSmooth[{i}]'] for i in range(3)]) / acc_1g(stem)
        mag = np.linalg.norm(acc, axis=0)
        peak = np.abs(gyro(d)).max(axis=0)
        print(f'{stem:34s} {mag[m].mean():6.3f}g {mag[m].std():7.4f} '
              f'{motors(d)[:, m].mean():11.1f} {d["amperageLatest (A)"][m].mean():7.3f} '
              f'{np.sqrt(np.mean(peak[m]**2)):9.1f}')
    print('\nacc is normalised by the header acc_1G. Nothing here separates the outcomes,')
    print('but "close" is not "identical", and contact preload, prop phase and the')
    print('unlogged 165-172 ms before the first frame are not measured at all.')


if __name__ == '__main__':
    main()

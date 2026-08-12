#!/usr/bin/env python3
"""What the three Pavo20 logs recorded: provenance, tune metrics, rescue.

The craft: Pavo20 Pro II, F405, 8k gyro / 4k PID (looptime 125, denom 2),
3S, b9 firmware 919116fed. Tune from the header (identical in all three
logs): wc 109/109/128, wo 143/143/153, b0 4988/3206/12307.
"""
import numpy as np

from common import (STEMS, headers, load, motors, time_s, fs_nominal,
                    sha256_gz, text_column, DEBUG_CLIP)

SHOW = ['Firmware revision', 'Craft name', 'pid_type', 'adrcWC', 'adrcWO',
        'adrcB0', 'motor_idle', 'dyn_idle_min_rpm', 'looptime',
        'pid_process_denom', 'P interval', 'debug_mode', 'vbatref',
        'pidsum_limit', 'pidsum_limit_yaw', 'deadband', 'yaw_deadband',
        'thr_hover']
PER_ARM = {'Firmware date', 'Log start datetime', 'vbatref',
           'rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed'}


def main():
    print('# Pavo20 Pro II overview\n')
    print('SHA-256 of the decompressed .bbl:')
    for stem in STEMS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    h0 = headers(STEMS[0])
    print(f'\nHeader ({STEMS[0]}):')
    for k in SHOW:
        if k in h0:
            print(f'  {k}: {h0[k]}')

    print('\nEvery header key that differs between the three logs (union of keys,')
    print('per-arm measurement keys excluded) - note the ADRC tune does NOT')
    print('differ, so the "wobble" log is on the same numbers as the other two;')
    print('what changed between it and the finished flight is RC deadbands and')
    print('the hover-throttle estimate:')
    all_h = [headers(s) for s in STEMS]
    for k in sorted(set().union(*[set(h) for h in all_h])):
        if k in PER_ARM:
            continue
        vals = [h.get(k) for h in all_h]
        if len(set(vals)) > 1:
            print(f'  {k}: ' + ' / '.join(str(v) for v in vals))

    print('\nPer-flight basics and tracking error (|setpoint - gyroADC|, whole')
    print('flight - these logs are real flying, so the medians include stick')
    print('input; the wobble log\'s elevated roll/pitch numbers coincide with')
    print('logged level-loop setpoint activity, whose direction ANGLE mode makes')
    print('inseparable - see wobble.py):')
    print(f'\n  {"log":38s} {"span":>7s} {"fs":>6s} {"rail":>6s} {"vbat min":>9s} '
          f'{"err med R/P/Y":>15s} {"err p90 R/P/Y":>15s}')
    for stem in STEMS:
        d = load(stem)
        t = time_s(d)
        m = motors(d)
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        med, p90 = [], []
        for ax in range(3):
            e = np.abs(d[f'setpoint[{ax}]'] - d[f'gyroADC[{ax}]'])
            med.append(np.median(e))
            p90.append(np.percentile(e, 90))
        print(f'  {stem:38s} {t[-1]:6.1f}s {fs_nominal(d):5.0f} '
              f'{int((m >= hi).sum()):6d} {d["vbatLatest (V)"].min():8.2f}V '
              f'{"/".join(f"{v:.0f}" for v in med):>15s} '
              f'{"/".join(f"{v:.0f}" for v in p90):>15s}')

    print('\nGPS rescues, from the recorded failsafe phase (6 =')
    print('FAILSAFE_GPS_RESCUE, failsafe.h) - one in each of the two acro+Airmode')
    print('flights, both following BOXFAILSAFE box activity (activation about')
    print('1.5 s before each phase-6 entry - boxes.py prints the exact pairs;')
    print('BOXGPSRESCUE never appears in the mask):')
    for stem in ('Return_to_home_btfl_002', 'Finished_minus_5_percent_btfl_001'):
        d = load(stem)
        t = time_s(d)
        ph = text_column(stem, 'failsafePhase')
        print(f'  == {stem}')
        prev = None
        marks = []
        for i, v in enumerate(ph):
            if v != prev:
                print(f'     t={t[i]:7.2f}s  failsafePhase = {v}')
                if v == '6':
                    marks.append(t[i])
                elif prev == '6':
                    marks.append(t[i])
                prev = v
        if len(marks) >= 2:
            print(f'     rescue duration {marks[1] - marks[0]:.1f} s')
    print('  The RTH-log rescue never puts a motor at the upper endpoint (rail')
    print('  column above). The finished-flight rescue does, briefly - wobble.py')
    print('  places all four of that log\'s oscillation-like windows inside or at')
    print('  the exit of this rescue.')

    print('\nThe yaw z3 debug channel saturates its int16 telemetry rail in all')
    print('three logs (the controller clamp is far higher and is not implicated;')
    print('this is the ADRC-029 logging limitation, fixed for b10 by the')
    print('adrc_z3_log_scale header line - these are b9 logs):')
    for stem in STEMS:
        d = load(stem)
        n = d['_n']
        clip = {k: int((np.abs(d[f'debug[{i}]']) >= DEBUG_CLIP).sum())
                for k, i in (('R', 2), ('P', 5), ('Y', 6))}
        print(f'  {stem:38s} R/P/Y railed frames {clip["R"]}/{clip["P"]}/{clip["Y"]} '
              f'of {n} ({100.0 * clip["Y"] / n:.1f}% on yaw)')
    print('  With b0 yaw = ' + headers(STEMS[0])['adrcB0'].split(',')[2] + ' the yaw clamp is pidsum_limit_yaw * b0 = '
          + str(int(float(headers(STEMS[0])['pidsum_limit_yaw'])
                    * float(headers(STEMS[0])['adrcB0'].split(',')[2])))
          + ',')
    print('  while the b9 debug rail is 32767 * 16 = ' + str(32767 * 16) + ' - everything between')
    print('  those two values is invisible in a b9 log.')


if __name__ == '__main__':
    main()

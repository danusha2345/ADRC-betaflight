#!/usr/bin/env python3
"""What the seven ladder logs recorded: provenance, the 3-key matrix, basics.

Each log is one short test arm with one BOXAIRMODE activation on a
fresh-ish pack. The seven configurations cover seven of the eight cells of
the {LP1, LP2, RPM} on/off factorial (LP1+LP2 without RPM was not flown).
One arm per configuration - nothing here is a repeated measurement.
"""
import numpy as np

from common import (LOGS, STEMS, headers, load, motors, time_s, sha256_gz,
                    airmode_windows, DEBUG_CLIP)

SHOW = ['Firmware revision', 'Craft name', 'pid_type', 'adrcWC', 'adrcWO',
        'adrcB0', 'adrc_hover_throttle', 'adrc_liftoff_throttle',
        'motor_idle', 'dyn_idle_min_rpm', 'dyn_notch_count', 'yaw_lowpass_hz',
        'dterm_lpf1_dyn_hz', 'dterm_lpf2_static_hz',
        'looptime', 'pid_process_denom', 'P interval', 'debug_mode', 'features']
PER_ARM = {'Firmware date', 'Log start datetime', 'vbatref',
           'rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed'}
VARY = ('gyro_lpf1_dyn_hz', 'gyro_lpf2_static_hz', 'rpm_filter_harmonics')


def main():
    print('# AcroBee75 filter ladder - overview\n')
    print('SHA-256 of the decompressed .bbl:')
    for stem in STEMS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    h0 = headers(STEMS[0])
    print(f'\nShared header ({STEMS[0]}; identical in all seven on every key')
    print('outside the three ladder keys and the per-arm measurement keys -')
    print('checked below):')
    for k in SHOW:
        if k in h0:
            print(f'  {k}: {h0[k]}')

    all_h = {s: headers(s) for s in STEMS}
    extra = []
    for k in sorted(set().union(*[set(h) for h in all_h.values()])):
        if k in PER_ARM or k in VARY:
            continue
        vals = [all_h[s].get(k) for s in STEMS]
        if len(set(vals)) > 1:
            extra.append((k, vals))
    if extra:
        print('\nUNEXPECTED extra differing keys:')
        for k, vals in extra:
            print(f'  {k}: ' + ' / '.join(str(v) for v in vals))
    else:
        print('\nOutside the three ladder keys, the union of header keys is')
        print('identical across all seven logs (per-arm measurement keys aside).')
    print('\nMeasured RC-smoothing state per arm (runtime values following the')
    print('ELRS link rate - real filter coefficients derive from them, so an arm')
    print('with a different link is NOT runtime-identical to its siblings even')
    print('though sticks-path relevance is bounded by the flying itself):')
    for label, stem in LOGS:
        h = all_h[stem]
        print(f'  {label:14s} cutoffs {h.get("rc_smoothing_active_cutoffs_ff_sp_thr")}, '
              f'rx {h.get("rc_smoothing_rx_smoothed")} Hz')

    print('\nThe ladder matrix (from the headers):')
    print(f'  {"config":14s} {"gyro_lpf1_dyn_hz":>17s} {"gyro_lpf2_static_hz":>20s} '
          f'{"rpm_filter_harmonics":>21s}')
    for label, stem in LOGS:
        h = all_h[stem]
        print(f'  {label:14s} {h[VARY[0]]:>17s} {h[VARY[1]]:>20s} {h[VARY[2]]:>21s}')

    print('\nPer-arm basics (whole log) and the airmode activation:')
    print(f'  {"config":14s} {"span":>6s} {"vbat":>11s} {"rail":>5s} '
          f'{"err med R/P/Y":>14s} {"airmode window":>16s} {"vbat@air":>9s}')
    for label, stem in LOGS:
        d = load(stem)
        t = time_s(d)
        m = motors(d)
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        med = [float(np.median(np.abs(d[f'setpoint[{ax}]'] - d[f'gyroADC[{ax}]'])))
               for ax in range(3)]
        wins = airmode_windows(stem, float(t[-1]))
        lo, hi_t = wins[0] if wins else (float('nan'), float('nan'))
        vb_air = float(np.median(d['vbatLatest (V)'][(t >= lo) & (t < lo + 1)])) if wins else float('nan')
        print(f'  {label:14s} {t[-1]:5.1f}s '
              f'{d["vbatLatest (V)"].min():5.2f}-{d["vbatLatest (V)"].max():5.2f} '
              f'{int((m >= hi).sum()):5d} {"/".join(f"{v:.0f}" for v in med):>14s} '
              f'{lo:6.1f}-{hi_t:6.1f}s {vb_air:8.2f}V')
    print('\n  Whole-log medians mix pre-airmode hover and the airmode segment;')
    print('  ladder.py restricts everything to the airmode segments. The')
    print('  LP1+LP2+RPM arm is the shortest and its airmode segment lasts only')
    print('  a few seconds before the arm ends - its numbers are censored by')
    print('  whatever ended it, and ladder.py flags that.')

    print('\nz3 debug-rail frames (b9 int16 telemetry rail; ADRC-029 context):')
    for label, stem in LOGS:
        d = load(stem)
        clip = {k: int((np.abs(d[f'debug[{i}]']) >= DEBUG_CLIP).sum())
                for k, i in (('R', 2), ('P', 5), ('Y', 6))}
        gate = d['debug[7]']
        print(f'  {label:14s} R/P/Y {clip["R"]}/{clip["P"]}/{clip["Y"]} of {d["_n"]}, '
              f'gate open {100 * (gate > 0).mean():.1f}%')


if __name__ == '__main__':
    main()

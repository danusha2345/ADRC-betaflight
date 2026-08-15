#!/usr/bin/env python3
"""What the two AcroBee75 logs recorded: provenance, the filter diff, the
airmode timeline, and per-log basics.

The tester's experiment: same craft, same ADRC tune, one flight with his
filter set on and one with it off. The value of the pair is that the gyro
filter chain sits inside the ADRC loop (common.py docstring has the code
path), so this is - up to the usual two-different-flights caveats - a
filter-chain ON/OFF experiment on a real craft (magnitude and phase both
change; the two are not separable here).
"""
import numpy as np

from common import (LOGS, STEMS, ON, OFF, headers, load, motors, time_s,
                    sha256_gz, mask_transitions, airmode_windows, DEBUG_CLIP,
                    AIR_BIT)

SHOW = ['Firmware revision', 'Craft name', 'pid_type', 'adrcWC', 'adrcWO',
        'adrcB0', 'adrc_hover_throttle', 'adrc_liftoff_throttle',
        'motor_idle', 'dyn_idle_min_rpm', 'dyn_notch_min_hz', 'dyn_notch_max_hz',
        'looptime', 'pid_process_denom',
        'P interval', 'debug_mode', 'vbat_sag_compensation', 'features']
PER_ARM = {'Firmware date', 'Log start datetime', 'vbatref',
           'rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed'}


def main():
    print('# AcroBee75 filters experiment - overview\n')
    print('SHA-256 of the decompressed .bbl:')
    for stem in STEMS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    h0 = headers(ON)
    print(f'\nShared header ({ON}):')
    for k in SHOW:
        if k in h0:
            print(f'  {k}: {h0[k]}')

    print('\nEvery header key that differs between the two logs (union of keys,')
    print('per-arm measurement keys excluded) - the experiment variable:')
    ha, hb = headers(ON), headers(OFF)
    for k in sorted(set(ha) | set(hb)):
        if k in PER_ARM:
            continue
        if ha.get(k) != hb.get(k):
            print(f'  {k}: {ha.get(k)} -> {hb.get(k)}')
    print('  (ON -> OFF. Loop-relevant for ADRC: the gyro chain -')
    print('  gyro_lpf2_static_hz, dyn_notch_count, rpm_filter_harmonics. The')
    print('  dterm_* keys shape a classic D that ADRC overwrites, and')
    print('  yaw_lowpass_hz filters the classic yaw P before the ADRC overwrite -')
    print('  neither enters the nominal ADRC P/I/D output (the filtered gyro')
    print('  delta still feeds the crash-detection side path, whose enablement')
    print('  these headers do not record); see ANALYSIS.md for the code path.)')

    print('\nPer-log basics (whole log; both are real flights with stick input):')
    print(f'\n  {"log":30s} {"span":>7s} {"vbat":>11s} {"rail":>6s} '
          f'{"err med R/P/Y":>14s} {"err p90 R/P/Y":>14s} {"err max R/P/Y":>15s}')
    for label, stem in LOGS:
        d = load(stem)
        t = time_s(d)
        m = motors(d)
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        med, p90, mx = [], [], []
        for ax in range(3):
            e = np.abs(d[f'setpoint[{ax}]'] - d[f'gyroADC[{ax}]'])
            med.append(np.median(e))
            p90.append(np.percentile(e, 90))
            mx.append(e.max())
        rail = int((m >= hi).sum())
        rate = rail / float(t[-1])
        share = 100.0 * rail / (m.shape[0] * m.shape[1])
        print(f'  {stem:30s} {t[-1]:6.1f}s '
              f'{d["vbatLatest (V)"].min():5.2f}-{d["vbatLatest (V)"].max():5.2f} '
              f'{rail:6d} {"/".join(f"{v:.0f}" for v in med):>14s} '
              f'{"/".join(f"{v:.0f}" for v in p90):>14s} {"/".join(f"{v:.0f}" for v in mx):>15s}')
        print(f'  {"":30s} rail normalized: {rate:.2f} samples/s = {share:.4f} % of motor samples')
    print('\n  The OFF log\'s higher whole-log medians co-occur with the visible')
    print('  micro-oscillation the tester described (a central cruise window in')
    print('  spectra.py places its dominant error content in the high hundreds')
    print('  of Hz, near the motor band; the medians themselves are not')
    print('  frequency-decomposed). Its lower')
    print('  maxima: note the ON log\'s three error maxima all belong to the one')
    print('  terminal event attempts.py describes, so the maxima row compares a')
    print('  flight with such an event against one without, not two steady')
    print('  regimes.')

    print('\nBOXAIRMODE timeline (numeric mode mask; the feature bit is off in')
    print('both logs, so the box IS the airmode state):')
    for label, stem in LOGS:
        d = load(stem)
        span = float(time_s(d)[-1])
        wins = airmode_windows(stem, span)
        txt = ';  '.join(f'{lo:6.1f}-{hi:6.1f}s ({hi - lo:5.1f}s)' for lo, hi in wins)
        print(f'  {stem}:')
        print(f'     {txt if txt else "never active"}')
    print('\n  ON log: seven activations, from 2.3 s (consistent with the reported')
    print('  bail-outs) to a 60 s final one -')
    print('  attempts.py measures each. OFF log: one activation covering')
    print('  essentially the whole flight.')

    print('\nz3 debug-rail frames (b9 int16 telemetry rail; ADRC-029 context):')
    for label, stem in LOGS:
        d = load(stem)
        clip = {k: int((np.abs(d[f'debug[{i}]']) >= DEBUG_CLIP).sum())
                for k, i in (('R', 2), ('P', 5), ('Y', 6))}
        gate = d['debug[7]']
        print(f'  {stem:30s} R/P/Y {clip["R"]}/{clip["P"]}/{clip["Y"]} of {d["_n"]}, '
              f'gate open {100 * (gate > 0).mean():.1f}%')


if __name__ == '__main__':
    main()

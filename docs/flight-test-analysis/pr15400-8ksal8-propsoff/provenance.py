#!/usr/bin/env python3
"""What each of the sixteen props-off logs actually recorded, and what differs
between the four groups besides the controller.

The previous set from this reporter was labelled for a comparison it did not
contain, so the controller is checked from the header and from the runtime
evidence rather than from the filename. The groups here are genuinely
different controllers - and the profiles differ in several other ways too,
which is the more important thing this script prints.
"""
import numpy as np

from common import GROUPS, LOGS, headers, load, sha256_gz, time_s, fs_nominal, text_column

KEYS = ['Firmware revision', 'Board information', 'Craft name', 'pid_type', 'debug_mode',
        'motorOutput', 'motor_idle', 'motor_poles', 'dyn_idle_min_rpm',
        'rollPID', 'pitchPID', 'yawPID',
        'adrcWC', 'adrcWO', 'adrcB0', 'features', 'pid_at_min_throttle',
        'airmode_activate_throttle', 'vbat_sag_compensation', 'looptime', 'P interval']


def main():
    print('# Provenance\n')
    print('SHA-256 of the decompressed .bbl:')
    for _, stem, _, _ in LOGS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    print('\nOne representative header per group (all four arms in a group agree;')
    print('the agreement is checked below):\n')
    reps = {}
    for label, ctrl, air, sub, stems in GROUPS:
        stem = f'{sub}_{stems[0]}'
        h = headers(stem)
        reps[label] = h
        print(f'  == {label}')
        for k in KEYS:
            if k in h:
                print(f'     {k}: {h[k]}')
        print()

    print('Within-group agreement, checked over the UNION of all header keys (an')
    print('earlier version checked a hand-picked list, which is not a check):')
    for label, ctrl, air, sub, stems in GROUPS:
        all_h = [headers(f'{sub}_{stem}') for stem in stems]
        varying = {}
        for k in set().union(*[set(h) for h in all_h]):
            if k in ('Firmware date', 'Log start datetime'):
                continue
            vals = [h.get(k) for h in all_h]
            if len(set(vals)) > 1:
                varying[k] = vals
        if varying:
            print(f'  {label}: all keys identical EXCEPT ' + '; '.join(
                f'{k} = {v}' for k, v in sorted(varying.items())))
        else:
            print(f'  {label}: identical on every header key')
    print('  (vbatref is the pre-arm voltage snapshot and legitimately differs per')
    print('  arm; the rc_smoothing_* keys are runtime-measured cutoffs.)')

    print('\nControllers, from the header and from runtime evidence:')
    for _, stem, ctrl, _ in LOGS:
        h = headers(stem)
        d = load(stem)
        has_d2 = 'axisD[2]' in d
        # The observer-channel test only means anything when the debug mode is
        # DEBUG_ADRC (102); under any other mode those channels carry something
        # else entirely and their variation says nothing about the controller.
        if h['debug_mode'] == '102':
            live = len(np.unique(d['debug[1]'])) > 5
            obs = f'ADRC observer channel varying {live}'
        else:
            obs = 'observer channels n/a (debug_mode is not DEBUG_ADRC)'
        print(f'  {stem}: pid_type {h["pid_type"]} ({ctrl}), debug_mode {h["debug_mode"]}, '
              f'axisD[2] logged {has_d2}, {obs}')

    print('\nHEADER DIFF between one representative arm of each controller. Not "full":')
    print('it is one arm per side, the Field I/P table rows are elided (they differ only')
    print('through axisD[2], stated explicitly), and the per-arm-variable keys (vbatref,')
    print('rc_smoothing_*) are listed separately above and below:\n')
    ha = headers(f'{GROUPS[0][3]}_{GROUPS[0][4][0]}')
    hc = headers(f'{GROUPS[2][3]}_{GROUPS[2][4][0]}')
    skip = {'Firmware revision', 'Firmware date', 'Log start datetime', 'vbatref'}
    # The Field I/P lines differ only because axisD[2] is present under ADRC and
    # absent under CLASSIC; that is already stated explicitly, so the raw field
    # tables are elided from the diff for readability.
    for k in sorted(set(ha) | set(hc)):
        if k in skip or k.startswith('Field ') or ha.get(k) == hc.get(k):
            continue
        print(f'  {k}: ADRC {ha.get(k, "-")}  |  CLASSIC {hc.get(k, "-")}')
    print('  (vbatref differs per arm and is listed with the voltages below.)')

    print('\nWHAT DIFFERS AND IS JUDGED MATERIAL. At least these; a four-way comparison')
    print('is only worth what it holds constant, and none of these is held constant:\n')
    a = reps['ADRC, Airmode feature on']
    c = reps['CLASSIC, Airmode feature on']
    print(f'  1. motor output range: ADRC {a["motorOutput"]} vs CLASSIC {c["motorOutput"]},')
    print(f'     with the same motor_idle {a["motor_idle"]}. mixer_init.c:360-362 sets')
    print('     motorOutputLow to DSHOT_MIN_THROTTLE when dynamic idle is active, so the')
    print('     CLASSIC runs had dynamic idle enabled and the ADRC runs did not.')
    print(f'  2. yaw D: CLASSIC yawPID {c["yawPID"]} - the D term is ZERO. Under ADRC the')
    print('     D-equivalent is always present (kd = 2*wc). Any yaw difference below is')
    print('     therefore "a D term on yaw against none", not only "ADRC against PID".')
    print(f'     Directly: dyn_idle_min_rpm is {a.get("dyn_idle_min_rpm", "?")} in the ADRC')
    print(f'     runs and {c.get("dyn_idle_min_rpm", "?")} in the CLASSIC runs.')
    print(f'  3. the gains themselves: CLASSIC {c["rollPID"]}/{c["pitchPID"]}/{c["yawPID"]}')
    print(f'     against ADRC wc {a["adrcWC"]}, wo {a["adrcWO"]}, b0 {a["adrcB0"]}.')
    print('  4. the pack: the ADRC arms start lower and sag further.')

    print('\nMeasured idle: rotor frequency and motor command per group.')
    print('This quantifies difference 1 - the motors are not spinning at the same rate.\n')
    from common import rotor_hz, motors
    print(f'  {"group":30s} {"rotor Hz":>9s} {"motor median":>13s} {"current max":>12s}')
    for label, ctrl, air, sub, stems in GROUPS:
        rot, mot, amp = [], [], []
        for stem in [f'{sub}_{s}' for s in stems]:
            d = load(stem)
            rot.append(rotor_hz(d, stem))
            mot.append(float(np.median(motors(d))))
            amp.append(float(d['amperageLatest (A)'].max()))
        print(f'  {label:30s} {np.median(rot):9.0f} {np.median(mot):13.0f} '
              f'{np.median(amp):11.2f} A')

    print('\nPer-arm vbatref (the header voltage snapshot taken as logging starts):')
    for label, ctrl, air, sub, stems in GROUPS:
        vr = [float(headers(f'{sub}_{stem}')['vbatref']) / 100.0 for stem in stems]
        print(f'  {label:30s} ' + ', '.join(f'{v:.2f}' for v in vr) + ' V')

    print('\nSpan, throttle and pack voltage per arm. Props are off, so nothing here')
    print('should leave the ground; the voltages quantify material difference 4.')
    for _, stem, _, _ in LOGS:
        d = load(stem)
        v = d['vbatLatest (V)']
        print(f'  {stem}: {time_s(d)[-1]:6.2f} s, {d["_n"]:6d} frames, '
              f'{fs_nominal(d):6.1f} Hz, rcCommand[3] '
              f'{d["rcCommand[3]"].min():.0f}..{d["rcCommand[3]"].max():.0f}, '
              f'setpoint[3] {d["setpoint[3]"].min():.0f}..{d["setpoint[3]"].max():.0f}, '
              f'vbat {v[0]:.2f} -> {v[-1]:.2f} V')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""What the twenty-one logs actually recorded, and the paired design.

The value of this corpus is that each of its three runs changes the one
intended profile variable against a cell that already exists in the first
props-off corpus (../pr15400-8ksal8-propsoff, same firmware, same craft,
same bench protocol) - plus, for the CLASSIC run, the simplified_pids_mode
flip needed to set yaw D at all. That is checked here programmatically over
the UNION of all header keys, not asserted from memory. And profile-level
is NOT "everything else equal": the runtime-measured RC-smoothing state
follows the ELRS link rate and differs between arms (printed below), and
pack state differs between groups. Both belong in every comparison's
caveats.
"""
import numpy as np

from common import (GROUPS, SWEEP, LOGS, OLD, headers, load, motors, time_s,
                    sha256_gz)

FEATURE_AIRMODE_BIT = 22          # config/feature.h: FEATURE_AIRMODE = 1 << 22

# Keys that differ between arms of one configuration. The first three are
# timestamps and the pre-arm voltage snapshot. The two rc_smoothing_* keys
# are NOT mere metadata: they are the runtime-measured RC filter cutoffs and
# smoothed RX rate, which follow the ELRS link rate - the firmware derives
# real filter coefficients from them (rc.c). They are excluded from the
# identity checks because they legitimately vary per arm with the link, but
# they are PRINTED per arm below and belong in every "only one variable
# changed" caveat. An earlier version of this script hid them entirely,
# which made the paired-design claim stronger than the data.
PER_ARM = {'Firmware date', 'Log start datetime', 'vbatref',
           'rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed'}
RC_KEYS = ('rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed')

SHOW = ['Firmware revision', 'Craft name', 'pid_type', 'debug_mode',
        'adrcWC', 'adrcWO', 'adrcB0', 'rollPID', 'pitchPID', 'yawPID',
        'motor_idle', 'dyn_idle_min_rpm', 'motor_poles', 'features',
        'looptime', 'pid_process_denom', 'P interval',
        'pidsum_limit', 'pidsum_limit_yaw',
        'adrc_liftoff_throttle', 'adrc_hover_throttle']

# The old-corpus cell each new group pairs against (first stem is enough for
# the diff; within-group agreement is checked separately in both corpora).
PAIRING = [
    ('CLASSIC yawD=26, Airmode on',  'classicYD_on_btfl_001', 'b9_Airmode_on_PID_btfl_021'),
    ('CLASSIC yawD=26, Airmode off', 'classicYD_sw_btfl_005', 'b9_Airmode_switch_PID_btfl_025'),
    ('ADRC dynIdle=30, Airmode on',  'dynidle_on_btfl_009',   'b9_Airmode_on_ADRC_btfl_001'),
    ('ADRC dynIdle=30, Airmode off', 'dynidle_sw_btfl_013',   'b9_Airmode_switch_ADRC_btfl_005'),
]


def group_stems():
    for label, ctrl, air, sub, stems in GROUPS:
        yield label, [f'{sub}_{s}' for s in stems]
    yield 'yaw wc sweep', [s for _, s in SWEEP]


def agreement(label, stems, ignore=()):
    all_h = [headers(s) for s in stems]
    varying = {}
    for k in set().union(*[set(h) for h in all_h]):
        if k in PER_ARM or k in ignore:
            continue
        vals = [h.get(k) for h in all_h]
        if len(set(vals)) > 1:
            varying[k] = vals
    if varying:
        print(f'  {label}: identical EXCEPT ' + '; '.join(
            f'{k} = {v}' for k, v in sorted(varying.items())))
    else:
        print(f'  {label}: identical on every header key (union of keys, minus')
        print('      the per-arm measurement keys listed in PER_ARM)')


def main():
    print('# Provenance\n')
    print('SHA-256 of the decompressed .bbl:')
    for _, stem, _, _ in LOGS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')
    for _, stem in SWEEP:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    print('\nOne representative header per group:\n')
    for label, stems in group_stems():
        h = headers(stems[0])
        print(f'  == {label}  ({stems[0]})')
        for k in SHOW:
            if k in h:
                print(f'     {k}: {h[k]}')
        feat = int(h.get('features', '0'))
        print(f'     FEATURE_AIRMODE (bit {FEATURE_AIRMODE_BIT}): '
              f'{"ON" if feat & (1 << FEATURE_AIRMODE_BIT) else "off"}')
        print()

    print('Within-group agreement, over the UNION of all header keys:')
    for label, stems in group_stems():
        ignore = ('adrcWC', 'yawPID') if label == 'yaw wc sweep' else ()
        agreement(label, stems, ignore)
    print('  (the sweep is checked ignoring adrcWC/yawPID, which are its variable;')
    print('   those five values are printed above by sweep.py and in the header dump)')

    print('\nThe paired design against the first props-off corpus - every header')
    print('key that differs between the new cell and its old counterpart:')
    for label, new_stem, old_stem in PAIRING:
        hn, ho = headers(new_stem), headers(old_stem, basedir=OLD)
        diffs = {}
        for k in set(hn) | set(ho):
            if k in PER_ARM:
                continue
            if hn.get(k) != ho.get(k):
                diffs[k] = (ho.get(k), hn.get(k))
        print(f'  {label}:')
        for k, (o, n) in sorted(diffs.items()):
            print(f'     {k}: {o} -> {n}')

    print('\nControllers, from the header and from runtime evidence:')
    for label, stems in group_stems():
        for stem in stems:
            h = headers(stem)
            d = load(stem)
            pid_type = h.get('pid_type')
            gate = d['debug[7]']
            z3_active = any(np.any(d[f'debug[{i}]'] != 0) for i in (2, 5, 6))
            note = (f'debug[7] (ADRC gate/b0-scale channel) in '
                    f'[{gate.min():.0f}, {gate.max():.0f}]'
                    if pid_type == '1' else
                    f'debug_mode {h.get("debug_mode")} (not DEBUG_ADRC)')
            print(f'  {stem:30s} pid_type {pid_type} '
                  f'({"ADRC" if pid_type == "1" else "CLASSIC"}); {note}'
                  + ('' if pid_type != '1' else
                     f'; z3 channels {"active" if z3_active else "all-zero"}'))

    print('\nEvery arm is a stick-down bench arm, and none railed a motor:')
    railed = 0
    for label, stems in group_stems():
        for stem in stems:
            d = load(stem)
            hi = float(headers(stem)['motorOutput'].split(',')[1])
            thr_max = float(d['rcCommand[3]'].max())
            r = int((motors(d) >= hi).sum())
            railed += r
            assert thr_max == 1000.0, (stem, thr_max)
    print(f'  rcCommand[3] max is exactly 1000 in all 21 logs (asserted, not shown),')
    print(f'  and the total count of motor samples at the upper endpoint is {railed}.')

    print('\nMeasured RC-smoothing state per arm (runtime values following the')
    print('ELRS link rate; the filters derived from them are real, so any arm')
    print('where they differ is NOT identical to its pair in runtime terms -')
    print('sticks were untouched in every arm here, which bounds their influence')
    print('but does not erase it):')
    for label, stems in group_stems():
        vals = {s: tuple(headers(s).get(k) for k in RC_KEYS) for s in stems}
        uniq = set(vals.values())
        if len(uniq) == 1:
            v = next(iter(uniq))
            print(f'  {label:32s} all arms: cutoffs {v[0]}, rx {v[1]} Hz')
        else:
            print(f'  {label}:')
            for s in stems:
                print(f'     {s:30s} cutoffs {vals[s][0]}, rx {vals[s][1]} Hz')

    print('\nBattery state per group (vbatLatest min-max over the group, V) - the')
    print('groups were flown on different pack states, which is an uncontrolled')
    print('difference in every between-group comparison:')
    for label, stems in group_stems():
        vmin = min(float(load(s)['vbatLatest (V)'].min()) for s in stems)
        vmax = max(float(load(s)['vbatLatest (V)'].max()) for s in stems)
        print(f'  {label:32s} {vmin:.2f} - {vmax:.2f} V')
    print('  Within the sweep the pack declines monotonically in wc order (the')
    print('  arms were flown in ascending wc order on one pack); sweep.py prints')
    print('  the per-arm values next to the amplitudes they confound.')


if __name__ == '__main__':
    main()

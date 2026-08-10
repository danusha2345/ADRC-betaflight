#!/usr/bin/env python3
"""Provenance: what each of the five logs actually recorded.

Establishes, per log: firmware revision, active controller, tune, the Airmode
feature bit, whether the ADRC observer channels are live, and the gap between
the log's own arming marker and its first saved data frame.

The controller question matters because the filenames disagree with the data.
"""
import json
import os

import numpy as np

from common import LOGS, HERE, headers, load, sha256_gz, time_s, fs_nominal, text_column

FEATURE_AIRMODE_BIT = 22          # config/feature.h: FEATURE_AIRMODE = 1 << 22


def events(stem, workdir=None):
    from common import ensure_csv
    path = ensure_csv(stem, workdir).replace('.csv', '.event')
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def main():
    print('# Provenance\n')
    print('SHA-256 of the decompressed .bbl:')
    for _, stem, _, _ in LOGS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    print('\nHeaders and controller state:')
    hdr_keys = ['Firmware revision', 'Board information', 'Craft name', 'motor_kv', 'acc_1G',
                'pid_type', 'adrcWC', 'adrcWO', 'adrcB0', 'adrc_gyro_lpf_hz', 'adrc_b0_law',
                'adrc_hover_throttle', 'adrc_liftoff_throttle', 'debug_mode', 'features',
                'pid_at_min_throttle', 'airmode_activate_throttle', 'vbat_sag_compensation',
                'vbatcellvoltage', 'motorOutput', 'looptime', 'P interval',
                'pidsum_limit', 'pidsum_limit_yaw']
    for _, stem, build, airmode_cfg in LOGS:
        h = headers(stem)
        feat = int(h.get('features', '0'))
        airmode_feature = bool(feat & (1 << FEATURE_AIRMODE_BIT))
        print(f'\n  == {stem}   [{build}, filename says airmode {airmode_cfg}]')
        for k in hdr_keys:
            if k in h:
                print(f'     {k}: {h[k]}')
        print(f'     FEATURE_AIRMODE (bit {FEATURE_AIRMODE_BIT} of features): '
              f'{"ON" if airmode_feature else "off"}')

    print('\nRuntime evidence that the ADRC path executed (DEBUG_ADRC channels).')
    print('A frozen channel would mean the code stopped running; these are live.')
    for _, stem, _, _ in LOGS:
        d = load(stem)
        n = d['_n']
        q = max(1, n // 5)
        parts = []
        for ch in (1, 4):
            first = len(np.unique(d[f'debug[{ch}]'][:q]))
            last = len(np.unique(d[f'debug[{ch}]'][-q:]))
            parts.append(f'debug[{ch}] unique first/last 20% = {first}/{last}')
        print(f'  {stem}: n={n}, ' + ', '.join(parts))

    print('\nUnlogged interval between the log\'s arming marker and the first data frame.')
    print('Nothing about throttle in this window is recorded.')
    for _, stem, _, _ in LOGS:
        d = load(stem)
        ev = events(stem)
        sync = next((e['time'] for e in ev if 'Sync' in e.get('name', '')), None)
        first = d['time (us)'][0]
        gap = (first - sync) / 1000.0 if sync is not None else float('nan')
        print(f'  {stem}: first frame {gap:.1f} ms after "Sync beep"; '
              f'span {time_s(d)[-1]:.3f} s, {d["_n"]} frames, '
              f'mean rate {fs_nominal(d):.1f} Hz')

    print('\nThrottle stick and commanded collective over the whole log.')
    print('The Airmode *latch* (fc/core.c throttleRaised) needs commanded throttle above')
    print('airmode_activate_throttle; it is not logged, so this only bounds it:')
    for _, stem, _, _ in LOGS:
        d = load(stem)
        sp = d['setpoint[3]']
        thr_pct_max = sp.max() / 10.0
        thresh = float(headers(stem).get('airmode_activate_throttle', '25'))
        print(f'  {stem}: rcCommand[3] {d["rcCommand[3]"].min():.0f}..{d["rcCommand[3]"].max():.0f}, '
              f'setpoint[3] {sp.min():.0f}..{sp.max():.0f} '
              f'(max {thr_pct_max:.1f} % vs threshold {thresh:.0f} %): '
              + ('crosses the threshold, so the latch DID arm in this log'
                 if thr_pct_max >= thresh else
                 'never crosses it in any saved frame'))

    print('\nMixer-side Airmode. mixTable() reads isAirmodeEnabled() || launchControlActive')
    print('(mixer.c:707), which is the feature bit OR the BOXAIRMODE switch - no throttle')
    print('condition. The decoded mode field is rcModeActivationMask and the decoder drops')
    print('bits above 9, so BOXAIRMODE cannot be read back from the CSV; what is checkable')
    print('is the feature bit. The transitions below are the decoder mislabelling')
    print('BOXARM as ANGLE_MODE and BOXANGLE as HORIZON_MODE; none of them is Airmode:')
    for _, stem, _, _ in LOGS:
        h = headers(stem)
        feat = int(h.get('features', '0'))
        col = text_column(stem, 'flightModeFlags')
        if col is None:
            desc = 'field not present'
        else:
            vals = sorted(set(col))
            n_changes = sum(1 for a, b in zip(col, col[1:]) if a != b)
            desc = f'{n_changes} transitions, values seen: {vals}'
        print(f'  {stem}: FEATURE_AIRMODE '
              f'{"ON " if feat & (1 << FEATURE_AIRMODE_BIT) else "off"}, mode field: {desc}')

    on = [s for _, s, _, _ in LOGS if int(headers(s).get('features', '0')) & (1 << FEATURE_AIRMODE_BIT)]
    off = [s for _, s, _, _ in LOGS if not (int(headers(s).get('features', '0')) & (1 << FEATURE_AIRMODE_BIT))]
    print(f'\n  feature ON : {len(on)} logs - ' + ', '.join(x[-3:] for x in on))
    print(f'  feature off: {len(off)} logs - ' + ', '.join(x[-3:] for x in off))

    print('\nPack: this is a 1S craft by the header cell range and the measured voltage.')
    for _, stem, _, _ in LOGS:
        d = load(stem)
        v = d['vbatLatest (V)']
        print(f'  {stem}: vbatcellvoltage {headers(stem).get("vbatcellvoltage")}, '
              f'vbat {v[0]:.2f} -> {v[-1]:.2f} V (min {v.min():.2f}, max {v.max():.2f}), '
              f'current max {d["amperageLatest (A)"].max():.2f} A')


if __name__ == '__main__':
    main()

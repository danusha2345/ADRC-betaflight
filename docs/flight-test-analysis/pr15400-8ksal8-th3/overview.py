#!/usr/bin/env python3
"""What the six TH3 logs recorded: provenance, per-pack metrics, b0 scaling.

The tester's experiment: one craft flown on 2s, 3s and 4s packs with wc/wo
fixed (110/110/120 over wo 150) and b0 rescaled per pack by his watt-hour
rule. b0 was not the only thing that moved between packs: angle_limit and
the dterm filter settings changed too (the header-diff section below reads
each), and pack, day and stick input co-vary with all of it. The flight logs let two things be measured: how the tune
tracked on each pack, and how his b0 multipliers compare with the measured
pack-voltage ratios. The "wobble" logs are his ANGLE-mode stick-rocking
test (the same procedure as on the Pavo20 - and the same instrument caveat:
in ANGLE mode the logged setpoint is the self-level loop's output, so its
error numbers measure a different control chain than the acro flights).
"""
import numpy as np

from common import (LOGS, STEMS, headers, load, motors, time_s, sha256_gz,
                    mask_transitions, DEBUG_CLIP)

SHOW = ['Firmware revision', 'Craft name', 'pid_type', 'adrcWC', 'adrcWO',
        'adrcB0', 'adrc_hover_throttle', 'adrc_liftoff_throttle',
        'motor_idle', 'dyn_idle_min_rpm', 'looptime',
        'pid_process_denom', 'P interval', 'debug_mode', 'vbatref',
        'pidsum_limit', 'pidsum_limit_yaw']
PER_ARM = {'Firmware date', 'Log start datetime', 'vbatref',
           'rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed'}
AIR_BIT = 1 << 24


def main():
    print('# TH3 Freestyle overview\n')
    print('SHA-256 of the decompressed .bbl:')
    for stem in STEMS:
        print(f'  {stem}.bbl  {sha256_gz(stem)}')

    h0 = headers(STEMS[0])
    print(f'\nHeader ({STEMS[0]}):')
    for k in SHOW:
        if k in h0:
            print(f'  {k}: {h0[k]}')

    print('\nEvery header key that differs between the six logs (union of keys,')
    print('per-arm measurement keys excluded):')
    all_h = [headers(s) for s in STEMS]
    for k in sorted(set().union(*[set(h) for h in all_h])):
        if k in PER_ARM:
            continue
        vals = [h.get(k) for h in all_h]
        if len(set(vals)) > 1:
            print(f'  {k}: ' + ' / '.join(str(v) for v in vals))
    print('  Reading the diff. adrcB0 is the intended variable and each pack\'s')
    print('  flight/wobble pair shares its value. angle_limit differs (40 on 2s,')
    print('  60 on 3s/4s) and DOES shape the ANGLE-mode wobble logs\' setpoint')
    print('  (pid.c builds the ANGLE target from it) - a real confound for the')
    print('  wobble rows. The dterm_* keys differ too but do NOT touch the ADRC')
    print('  D path on this firmware: classic D is filtered through the dterm')
    print('  chain and then overwritten by applyAdrcControl(), whose D is')
    print('  -kd*z2/b0 from the observer\'s own dedicated gyro filter (pid.c,')
    print('  adrc.c). The rollPID/pitchPID/yawPID lines are the legacy display')
    print('  of the ADRC numbers, not extra changes. The per-pack comparison is')
    print('  still not single-variable for the plain reason that pack, day and')
    print('  stick input all change together with b0.')

    print('\nMode masks (numeric, --unit-flags raw): every "flight" log is acro')
    print('with the BOXAIRMODE box going active seconds after arming; every')
    print('"wobble" log is ANGLE mode throughout, airmode never active:')
    for pack, role, stem in LOGS:
        tr = mask_transitions(stem)
        txt = ';  '.join(f'{t:7.3f}s -> {v}' + (' (+AIR)' if v & AIR_BIT else '')
                         for t, v in tr[:5])
        print(f'  {stem:38s} {txt}')

    print('\nPer-flight basics and tracking error (|setpoint - gyroADC|, whole')
    print('log; the wobble rows are ANGLE-mode stick-rocking tests and are not')
    print('comparable to the acro flight rows - see the docstring):')
    print(f'\n  {"log":38s} {"span":>7s} {"vbat":>12s} {"rail":>6s} '
          f'{"err med R/P/Y":>14s} {"err p90 R/P/Y":>14s}')
    for pack, role, stem in LOGS:
        d = load(stem)
        t = time_s(d)
        m = motors(d)
        hi = float(headers(stem)['motorOutput'].split(',')[1])
        med, p90 = [], []
        for ax in range(3):
            e = np.abs(d[f'setpoint[{ax}]'] - d[f'gyroADC[{ax}]'])
            med.append(np.median(e))
            p90.append(np.percentile(e, 90))
        print(f'  {stem:38s} {t[-1]:6.1f}s '
              f'{d["vbatLatest (V)"].min():5.2f}-{d["vbatLatest (V)"].max():5.2f} '
              f'{int((m >= hi).sum()):6d} {"/".join(f"{v:.0f}" for v in med):>14s} '
              f'{"/".join(f"{v:.0f}" for v in p90):>14s}')

    print('\nThe b0 multipliers vs the measured pack voltage (flight logs, median')
    print('vbatLatest; roll b0 shown, all axes share each multiplier):')
    packs = {}
    for pack, role, stem in LOGS:
        if role != 'flight':
            continue
        h = headers(stem)
        d = load(stem)
        b0r = float(h['adrcB0'].split(',')[0])
        packs[pack] = (b0r, float(np.median(d['vbatLatest (V)'])))
        print(f'  {pack}: b0 roll {b0r:.0f}, vbat median {packs[pack][1]:.2f} V')
    for a, b in (('2s', '3s'), ('3s', '4s')):
        rb = packs[b][0] / packs[a][0]
        rv = packs[b][1] / packs[a][1]
        print(f'  {b}/{a}: b0 ratio {rb:.3f}, measured voltage ratio {rv:.3f} '
              f'(voltage step {100 * (rv / rb - 1):.1f} % above the b0 step)')
    rb_full = packs['4s'][0] / packs['2s'][0]
    rv_full = packs['4s'][1] / packs['2s'][1]
    print(f'  full range 4s/2s: b0 {rb_full:.3f}, voltage {rv_full:.3f} '
          f'(voltage-proportional endpoint {100 * (rv_full / rb_full - 1):.1f} % '
          f'above the configured b0 scale)')
    print('\n  The watt-hour-derived multipliers sit below the measured voltage')
    print('  ratios in both steps and cumulatively. All three configurations')
    print('  flew with similar rounded tracking metrics (table above) - three')
    print('  different flights on three different packs, so this is an observed')
    print('  coincidence of metrics, not a controlled test of the scaling rule')
    print('  or of what absorbed the difference. (Thrust-per-command is also')
    print('  not exactly proportional to voltage, so the voltage ratio is not')
    print('  a ground truth either.)')

    rail = 32767 * 16
    ratios = []
    rows = []
    for pack, role, stem in LOGS:
        d = load(stem)
        n = d['_n']
        clip = {k: 100.0 * float((np.abs(d[f'debug[{i}]']) >= DEBUG_CLIP).sum()) / n
                for k, i in (('R', 2), ('P', 5), ('Y', 6))}
        h = headers(stem)
        clamp = int(float(h['pidsum_limit_yaw']) * float(h['adrcB0'].split(',')[2]))
        ratios.append(clamp / rail)
        rows.append((stem, clip, clamp))
    print('\nYaw z3 debug-rail share per log (the b9 int16 telemetry rail at')
    print(f'32767*16 = {rail}; with these yaw b0 values the controller clamp')
    print(f'pidsum_limit_yaw * b0 is {min(ratios):.1f}-{max(ratios):.1f}x higher - '
          f'the ADRC-029 case again):')
    for stem, clip, clamp in rows:
        print(f'  {stem:38s} R/P/Y {clip["R"]:4.1f}/{clip["P"]:4.1f}/{clip["Y"]:4.1f} % '
              f'(yaw clamp {clamp})')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""The yaw line under each removed confound, measured phase-aware.

The first props-off corpus left the ADRC-vs-CLASSIC yaw gap (a line near
50 Hz, 7.1x/6.4x in the 30-80 Hz band) confounded three ways: the CLASSIC
profile had no yaw D at all, the ADRC cells ran without dynamic idle while
CLASSIC ran with it, and the pack state differed. This corpus removes the
first two one at a time and adds a yaw-wc sweep. This script measures:

  1. whole-arm group tables with the same estimator as the first corpus
     (Welch nperseg 2048 on gyroUnfilt resampled to a uniform grid), so the
     published numbers stay comparable;
  2. the same quantity per BOXAIRMODE phase - modemask.py recovers the switch
     state the decoder discards, and the switch cells of BOTH corpora turn
     out to contain a mid-arm airmode-on phase, so their whole-arm medians
     mix two authority regimes (x0.5 vs x1.0 at zero throttle,
     applyMixerAdjustment);
  3. the paired old-vs-new comparisons per matched cell;
  4. the rotor-order alias checks per motor - the mechanical 1x in detail,
     then the same time-varying folding for orders 2x-12x;
  5. whether the line is in the command path (it is: the yaw P+D spectrum
     peaks at the gyro line in every ADRC arm - with logged I = 0 and
     negligible yaw F those two terms are the whole logged ADRC P/I/D
     contribution; they act on the ESO's z1/z2 states, not the raw gyro -
     see arms.py. Presence, not direction: signals inside one closed loop
     share the limit-cycle frequency whatever set it).
"""
import numpy as np
from scipy.signal import welch

from common import (GROUPS, SWEEP, LOGS, OLD, load, time_s, gyro, fs_nominal,
                    resample_uniform, rotor_hz_per_motor, alias_of, headers,
                    ERPM_SCALE)
from modemask import get_phases

BANDS = [('0-8', 0.0, 8.0), ('8-30', 8.0, 30.0), ('30-80', 30.0, 80.0),
         ('80-400', 80.0, 400.0)]
NPERSEG = 2048
MIN_PHASE_S = 1.5

OLD_GROUPS = [
    ('ADRC dynIdle=0, Airmode on',  'ADRC',    'on',  'b9_Airmode_on_ADRC',
     ['btfl_001', 'btfl_002', 'btfl_003', 'btfl_004']),
    ('ADRC dynIdle=0, Airmode off', 'ADRC',    'off', 'b9_Airmode_switch_ADRC',
     ['btfl_005', 'btfl_006', 'btfl_007', 'btfl_008']),
    ('CLASSIC yawD=0, Airmode on',  'CLASSIC', 'on',  'b9_Airmode_on_PID',
     ['btfl_021', 'btfl_022', 'btfl_023', 'btfl_024']),
    ('CLASSIC yawD=0, Airmode off', 'CLASSIC', 'off', 'b9_Airmode_switch_PID',
     ['btfl_025', 'btfl_026', 'btfl_027', 'btfl_028']),
]


def series_psd(t, x, fs):
    tu, xu = resample_uniform(t, x, fs)
    f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(NPERSEG, len(xu)))
    return f, P


def psd(d, ax, t_lo=None, t_hi=None):
    """PSD of one gyroUnfilt axis, optionally restricted to a time window."""
    t = time_s(d)
    x = gyro(d, filtered=False)[ax]
    if t_lo is not None:
        m = (t >= t_lo) & (t < t_hi)
        t, x = t[m], x[m]
    fs = (len(t) - 1) / (t[-1] - t[0])
    f, P = series_psd(t, x, fs)
    return f, P, fs


def band_rms(f, P, lo, hi):
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(P[m].sum() * (f[1] - f[0])))


def yaw_metrics(d, t_lo=None, t_hi=None):
    f, P, fs = psd(d, 2, t_lo, t_hi)
    m = (f > 8) & (f < 400)
    return band_rms(f, P, 30.0, 80.0), float(f[m][np.argmax(P[m])])


def group_table(groups, basedir=None):
    """{label: (median yaw 30-80 RMS, [per-arm values], [peaks])}, whole-arm."""
    out = {}
    for label, ctrl, air, sub, stems in groups:
        vals, pks = [], []
        for s in stems:
            d = load(f'{sub}_{s}', basedir=basedir)
            v, p = yaw_metrics(d)
            vals.append(v)
            pks.append(p)
        out[label] = (float(np.median(vals)), vals, pks)
    return out


def phase_rows(groups, basedir=None):
    """[(label, stem, phase_air, t_lo, t_hi, yaw30_80, peak)] for switch cells."""
    rows = []
    for label, ctrl, air, sub, stems in groups:
        if air != 'off':
            continue
        for s in stems:
            stem = f'{sub}_{s}'
            d = load(stem, basedir=basedir)
            span = float(time_s(d)[-1])
            for t_lo, t_hi, is_air in get_phases(stem, span, basedir=basedir):
                if t_hi - t_lo < MIN_PHASE_S:
                    continue
                v, p = yaw_metrics(d, t_lo, t_hi)
                rows.append((label, stem, is_air, t_lo, t_hi, v, p))
    return rows


def main():
    print('# The yaw line, phase-aware\n')

    print('Whole-arm group medians, yaw, gyroUnfilt (same estimator as the first')
    print('corpus so the numbers are directly comparable):\n')
    new_t = group_table(GROUPS)
    old_t = group_table(OLD_GROUPS, basedir=OLD)
    print(f'  {"group":34s} {"yaw 30-80":>10s} {"per-arm":>34s} {"peak Hz":>18s}')
    for label, ctrl, air, sub, stems in OLD_GROUPS + GROUPS:
        med, vals, pks = (old_t if label in old_t else new_t)[label]
        print(f'  {label:34s} {med:10.2f} {"/".join(f"{v:.1f}" for v in vals):>34s} '
              f'{"/".join(f"{p:.0f}" for p in pks):>18s}')

    print('\nBut the whole-arm number is a phase mixture for every "Airmode off"')
    print('cell in BOTH corpora: modemask.py recovers the BOXAIRMODE box state,')
    print('and it went active for a mid-arm stretch every time (the mask proves')
    print('the box state, not who or what flipped it). Per phase:\n')
    print(f'  {"cell / phase":44s} {"n":>3s} {"yaw 30-80 median":>17s} {"peaks Hz":>22s}')
    for groups, basedir in ((OLD_GROUPS, OLD), (GROUPS, None)):
        rows = phase_rows(groups, basedir=basedir)
        for label in dict.fromkeys(r[0] for r in rows):
            for is_air in (False, True):
                sel = [r for r in rows if r[0] == label and r[2] == is_air]
                if not sel:
                    continue
                med = float(np.median([r[5] for r in sel]))
                pks = '/'.join(f'{r[6]:.0f}' for r in sel)
                tag = 'switch ON ' if is_air else 'switch off'
                print(f'  {label + ", " + tag:44s} {len(sel):3d} {med:17.2f} {pks:>22s}')
    print(f'\n  (phases shorter than {MIN_PHASE_S} s are dropped; each row pools the')
    print('  arms of one cell, n = number of contributing phases)')

    print('\nPaired comparisons (the one-variable changes):\n')
    c_on_old, c_on_new = old_t['CLASSIC yawD=0, Airmode on'][0], new_t['CLASSIC yawD=26, Airmode on'][0]
    a_on_old, a_on_new = old_t['ADRC dynIdle=0, Airmode on'][0], new_t['ADRC dynIdle=30, Airmode on'][0]
    print(f'  yaw D 0 -> 26 (CLASSIC, feature-on cells):   {c_on_old:6.2f} -> {c_on_new:6.2f} deg/s '
          f'({c_on_new / c_on_old:.2f}x)')
    print(f'  dyn idle 0 -> 30 (ADRC, feature-on cells):   {a_on_old:6.2f} -> {a_on_new:6.2f} deg/s '
          f'({a_on_new / a_on_old:.2f}x)')
    print(f'\n  ADRC over CLASSIC, both confounds removed, feature-on: '
          f'{a_on_new / c_on_new:.1f}x (was {a_on_old / c_on_old:.1f}x)')
    print('  The feature-on cells are the clean comparison: one homogeneous')
    print('  authority regime per arm. Pack state still differs between groups')
    print('  (provenance.py prints it), so the small movements are not')
    print('  attributable; the surviving 5-6x gap and the unmoved ~53 Hz peak are')
    print('  the findings.')

    print('\nIs the ADRC line a rotor order? Median 1x per motor, aliased against')
    print('the saved-stream rate, plus the time-varying check (folding EVERY')
    print('frame\'s per-motor rate; the arm-average frame rate is an approximation')
    print('with irregular frames, so treat small percentages as indicative).')
    print('The table tests the mechanical 1x; higher orders follow below it.\n')
    print(f'  {"log":30s} {"yaw peak":>9s} {"median 1x aliased":>22s} '
          f'{"min|med.1x-peak|":>17s} {"min|1x-peak|":>13s} {"frames<2Hz":>11s}')
    stems_all = ([(f'{sub}_{s}', ctrl) for _, ctrl, _, sub, ss in GROUPS for s in ss]
                 + [(s, 'ADRC') for _, s in SWEEP])
    agg = {'ADRC': {'rot': [], 'med_dist': [], 'pct': [], 'peaks': []},
           'CLASSIC': {'rot': [], 'med_dist': [], 'pct': [], 'peaks': []}}
    for stem, ctrl in stems_all:
        d = load(stem)
        fs = fs_nominal(d)
        v, peak = yaw_metrics(d)
        rates = rotor_hz_per_motor(d, stem)
        folded = [alias_of(r, fs) for r in rates]
        med_dist = min(abs(x - peak) for x in folded)
        poles = float(headers(stem).get('motor_poles', '12'))
        dmin = None
        for i in range(4):
            r = d[f'eRPM[{i}]'] * ERPM_SCALE / (poles / 2.0) / 60.0
            fold = r % fs
            fold = np.where(fold > fs / 2.0, fs - fold, fold)
            dd = np.abs(fold - peak)
            dmin = dd if dmin is None else np.minimum(dmin, dd)
        pct = 100 * float((dmin < 2).mean())
        a = agg[ctrl]
        a['rot'] += rates
        a['med_dist'].append(med_dist)
        a['pct'].append(pct)
        a['peaks'].append(peak)
        print(f'  {stem:30s} {peak:9.1f} {"/".join(f"{x:.0f}" for x in folded):>22s} '
              f'{med_dist:16.1f} {dmin.min():12.2f} {int((dmin < 2).sum()):5d} ({pct:4.1f}%)')
    A, C = agg['ADRC'], agg['CLASSIC']
    print(f'\n  Reading the 1x table. The ADRC line frequency spans only '
          f'{min(A["peaks"]):.1f}-{max(A["peaks"]):.1f} Hz while the per-motor')
    print(f'  median rotor rates span {min(A["rot"]):.0f}-{max(A["rot"]):.0f} Hz - '
          f'a 1x order cannot be stationary')
    print(f'  across that. The nearest aliased median 1x sits '
          f'{min(A["med_dist"]):.1f}-{max(A["med_dist"]):.1f} Hz from the line')
    print('  per arm (closest in the wc80/wc90 sweep arms, where dyn idle holds')
    print('  the rotors near 60-70 Hz). The time-varying 1x dwells within 2 Hz of')
    print(f'  the line for {min(A["pct"]):.1f}-{max(A["pct"]):.1f} % of frames per ADRC arm '
          f'(the two largest are the')
    print('  wc80/wc90 arms), so a small 1x contribution inside those two arms is')
    print('  not excluded - but it cannot carry the group result. In the CLASSIC')
    print(f'  cells the situation is reversed: the {min(C["peaks"]):.0f}-{max(C["peaks"]):.0f} Hz '
          f'peak lies inside their')
    print(f'  {min(C["rot"]):.0f}-{max(C["rot"]):.0f} Hz rotor-median span with the nearest '
          f'aliased median 1x only')
    print(f'  {min(C["med_dist"]):.1f}-{max(C["med_dist"]):.1f} Hz away and '
          f'{min(C["pct"]):.1f}-{max(C["pct"]):.1f} % time-varying dwell - consistent with')
    print('  rotor vibration through the D path (a control-loop contribution is')
    print('  not excluded by proximity alone). Either way the CLASSIC rows are a')
    print('  conservative (high) baseline for the ADRC-over-CLASSIC ratios above.')

    print('\nHigher rotor orders in the ADRC cells - the same time-varying folding')
    print('for k x the mechanical rate (6x is the electrical fundamental of these')
    print('12-pole motors). Worst dwell within 2 Hz of the line, per order, over')
    print('the 13 ADRC arms:\n')
    ORDERS = (1, 2, 3, 4, 5, 6, 12)
    worst = {}
    for k in ORDERS:
        worst[k] = ('', 0.0)
        for stem, ctrl in stems_all:
            if ctrl != 'ADRC':
                continue
            d = load(stem)
            fs = fs_nominal(d)
            v, peak = yaw_metrics(d)
            poles = float(headers(stem).get('motor_poles', '12'))
            dmin = None
            for i in range(4):
                r = k * d[f'eRPM[{i}]'] * ERPM_SCALE / (poles / 2.0) / 60.0
                fold = r % fs
                fold = np.where(fold > fs / 2.0, fs - fold, fold)
                dd = np.abs(fold - peak)
                dmin = dd if dmin is None else np.minimum(dmin, dd)
            pct = 100 * float((dmin < 2).mean())
            if pct > worst[k][1]:
                worst[k] = (stem, pct)
        print(f'  {k:2d}x: worst dwell {worst[k][1]:5.1f} %  ({worst[k][0]})')
    print('\n  So the broad claim "not a rotor order" is NOT available: while the')
    print('  1x is excluded as the carrier of the group result, individual higher')
    print('  orders spend up to ~12 % of some arms within 2 Hz of the line, and')
    print('  the rotor rates themselves rise with wc (an oscillation-driven motor')
    print('  is also a vibration source feeding back into the gyro - the bench')
    print('  cannot separate that path from the control loop). No bench')
    print('  configuration pins the rotor speed while the loop drives the motors')
    print('  - the first corpus\'s dyn-idle-OFF arms still ran their rotors at')
    print('  146-611 Hz. Separating the paths needs analysis, not configuration:')
    print('  an order tracker on integrated motor phase from eRPM(t), measuring')
    print('  how much of the line is coherent with the motors.')

    print('\nIs the line in the command path? Yaw P+D spectrum peak vs the gyro')
    print('peak. With z3 pinned at zero these two terms are the whole logged ADRC')
    print('P/I/D contribution (arms.py: axisI = -z3/b0 identically zero, yaw axisF')
    print('negligible - a handful of frames at -1). NB two signals inside one')
    print('closed loop are expected to share a limit-cycle frequency; this shows')
    print('the line lives in the command path, it does not establish which')
    print('element of the loop sets it:\n')
    for stem, ctrl in stems_all:
        if ctrl != 'ADRC':
            continue
        d = load(stem)
        t = time_s(d)
        fs = fs_nominal(d)
        s = d['axisP[2]'] + d['axisD[2]']
        f, P = series_psd(t, s, fs)
        m = (f > 8) & (f < 400)
        cmd_peak = float(f[m][np.argmax(P[m])])
        v, gyro_peak = yaw_metrics(d)
        flag = 'match' if abs(cmd_peak - gyro_peak) < 1.0 else f'DIFFERS by {abs(cmd_peak - gyro_peak):.1f} Hz'
        print(f'  {stem:30s} command {cmd_peak:6.1f} Hz, gyro {gyro_peak:6.1f} Hz  ({flag})')


if __name__ == '__main__':
    main()

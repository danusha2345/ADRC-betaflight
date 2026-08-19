#!/usr/bin/env python3
"""Yaw wc / wc=wo / b0-redistribution sweeps: 11 flights, one grid.

Flights by @8ksal8 on the Air65 R (PR #15400 comment id 5337016044), all on
b9 firmware with the main Betaflight gyro/dterm stages disabled and the ADRC
observer's own input PT2 at adrc_gyro_lpf_hz = 185. Four groups:
yaw wc sweep 50-80 at fixed yaw wo = 80; matching yaw wc = wo sweep 50-80;
two flights with yaw b0 lowered 2340 -> 878 and roll/pitch b0 raised so the
three-axis sum stays the same (his description); one flight with yaw wc = wo
raised to 88 and roll/pitch lowered. One flight per cell - every number is a
single observation; the tester reports flying the same track each time (his
report, not a log fact).
"""
import csv
import glob
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np
from scipy.signal import welch

HERE = os.path.dirname(os.path.abspath(__file__))

GROUPS = [
    ('wc sweep, yaw wo = 80',
     ['Air65_yaw_wc_50_', 'Air65_yaw_wc_60_', 'Air65_yaw_wc_70_', 'Air65_yaw_wc_80_']),
    ('wc = wo sweep',
     ['Air65_yaw_wc_wo_50_', 'Air65_yaw_wc_wo_60_', 'Air65_yaw_wc_wo_70_',
      'Air65_yaw_wc_wo_80_']),
    ('wc = wo with yaw b0 878 (sum-preserving redistribution)',
     ['Air65_yaw_wc_wo_50_adjusted_bo_', 'Air65_yaw_wc_wo_60_adjusted_bo_']),
    ('roll/pitch lowered, yaw raised',
     ['Air65_lower_RP_raise_Y_']),
]
STEMS = [s for _, ss in GROUPS for s in ss]

# keys we require identical across all 11 headers; the script also prints the
# full union diff below, so nothing outside this list can differ silently
SHARED_KEYS = (
    'Firmware revision', 'Craft name', 'pid_type', 'looptime',
    'adrc_gyro_lpf_hz', 'adrc_hover_throttle', 'dyn_idle_min_rpm',
    'gyro_lpf1_static_hz', 'gyro_lpf1_dyn_hz', 'gyro_lpf2_static_hz',
    'gyro_notch_hz', 'gyro_notch_cutoff', 'dyn_notch_count',
    'rpm_filter_harmonics', 'yaw_lowpass_hz',
    'dterm_lpf1_static_hz', 'dterm_lpf1_dyn_hz', 'dterm_lpf2_static_hz',
    'dterm_notch_hz', 'dterm_notch_cutoff', 'simplified_gyro_filter',
    'rc_smoothing', 'rates', 'rc_rates', 'rates_type',
    'vbat_sag_compensation', 'features', 'debug_mode', 'motorOutput',
)


def decoder():
    p = os.environ.get('BLACKBOX_DECODE')
    if p:
        return p
    from shutil import which
    p = which('blackbox_decode')
    if p:
        return p
    sys.exit('set BLACKBOX_DECODE')


def headers(stem):
    out = {}
    with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fh:
        blob = fh.read()
    for line in blob.split(b'\n'):
        if not line.startswith(b'H '):
            break
        if b':' in line:
            k, _, v = line[2:].partition(b':')
            out[k.decode('ascii', 'replace')] = v.decode('ascii', 'replace').strip()
    return out


def ensure_csv(stem):
    workdir = os.path.join(HERE, '_decoded')
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(path):
        return path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fi, \
                open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', bbl], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def metrics(stem):
    rows = list(csv.DictReader(open(ensure_csv(stem)), skipinitialspace=True))

    def col(n):
        k = next(kk for kk in rows[0] if kk.strip() == n)
        return np.array([float(r[k]) for r in rows])

    t = (col('time (us)') - col('time (us)')[0]) / 1e6
    vb = col('vbatLatest (V)')
    m = np.vstack([col(f'motor[{i}]') for i in range(4)])
    out = {'dur': float(t[-1]), 'vmin': float(vb.min()), 'vmax': float(vb.max()),
           'vend': float(vb[-1]), 't_vmin': float(t[int(np.argmin(vb))]),
           'rail': int((m >= 2047).sum()),
           'gate': float(100 * (col('debug[7]') > 0).mean())}
    for ax, nm in ((0, 'r'), (1, 'p'), (2, 'y')):
        e = np.abs(col(f'setpoint[{ax}]') - col(f'gyroADC[{ax}]'))
        out[f'med_{nm}'] = float(np.median(e))
        out[f'p90_{nm}'] = float(np.percentile(e, 90))
    ey = col('setpoint[2]') - col('gyroADC[2]')
    w = (t >= 3) & (t <= t[-1] - 3)
    ts, e = t[w], ey[w]
    fs = (len(ts) - 1) / (ts[-1] - ts[0])
    tu = np.arange(ts[0], ts[-1], 1 / fs)
    eu = np.interp(tu, ts, e)
    f, P = welch(eu - eu.mean(), fs=fs, nperseg=4096)
    band = (f >= 30) & (f < 80)
    out['pk_hz'] = float(f[band][np.argmax(P[band])])
    out['prom'] = float(P[band].max() / np.median(P[band]))
    out['band'] = float(np.sqrt(P[band].sum() * (f[1] - f[0])))
    out['_t'] = t
    out['_ey'] = ey
    out['_thr'] = col('rcCommand[3]')
    return out


def main():
    print('# yaw sweeps: 11 flights\n')
    print('SHA-256 of each decompressed .bbl:')
    for stem in STEMS:
        h = hashlib.sha256()
        with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                h.update(chunk)
        print(f'  {h.hexdigest()}  {stem}')

    hds = {s: headers(s) for s in STEMS}
    print('\nHeader consistency across all 11 logs:')
    diffs = []
    for k in SHARED_KEYS:
        vals = {hds[s].get(k) for s in STEMS}
        if len(vals) != 1:
            diffs.append(k)
            print(f'  DIFFERS {k}: ' + '; '.join(f'{s}={hds[s].get(k)}' for s in STEMS))
    all_keys = sorted(set().union(*(hds[s].keys() for s in STEMS)))
    union_diff = [k for k in all_keys
                  if len({hds[s].get(k) for s in STEMS}) != 1]
    print('  Keys differing anywhere in the full header union: '
          + ', '.join(union_diff))
    print('  (adrcWC/adrcWO/adrcB0 are the swept tune; rollPID/pitchPID/yawPID')
    print('  are their legacy mirrors; rc_smoothing_* is the link-rate confound')
    print('  below; vbatref is a per-flight battery reference. Every other header')
    print('  key is identical across all 11 logs - this is NOT a single-knob')
    print('  controlled comparison, and per-pair confounds are listed below.)')
    if not diffs:
        h0 = hds[STEMS[0]]
        print('  All keys in the required-identical list match. Shared state:')
        for k in ('Firmware revision', 'Craft name', 'adrc_gyro_lpf_hz',
                  'gyro_lpf1_static_hz', 'gyro_lpf2_static_hz', 'dyn_notch_count',
                  'rpm_filter_harmonics', 'yaw_lowpass_hz', 'dterm_lpf1_static_hz',
                  'dterm_lpf2_static_hz', 'dyn_idle_min_rpm', 'looptime',
                  'vbat_sag_compensation', 'debug_mode'):
            print(f'    {k}: {h0.get(k)}')
        print('  (main profile gyro/dterm chain out of the loop; the ADRC observer')
        print("  input PT2 at adrc_gyro_lpf_hz remains active - same reading as the")
        print('  b0calc campaign.)')
    print('\nRx link rate is NOT constant across cells - the same rc_smoothing')
    print('confound the acrobee2 campaign hit. Per cell:')
    for stem in STEMS:
        print(f'  {stem:34s} rx_smoothed={hds[stem].get("rc_smoothing_rx_smoothed"):>4s} '
              f'active_cutoffs={hds[stem].get("rc_smoothing_active_cutoffs_ff_sp_thr")}')
    print('Cells cluster at ~166 Hz and ~332-339 Hz. Link-rate-matched contrasts')
    print('(matched in THIS confound only - battery, inputs and conditions stay')
    print('uncontrolled): the wc=50 pair (wo 80 vs 50, both 166 Hz), the wc=wo')
    print('50/60/70 run (all 166 Hz), and the 80/80 repeated cell (332 vs 333 Hz).')
    print('The wc=60 and wc=70 same-wc pairs cross clusters, and so does the')
    print('stock-vs-adjusted b0 pair at wc=wo=60 (166 vs 333 Hz).')

    print('\nPer-cell grid (one flight per cell; errors deg/s; yaw-error spectrum')
    print('over the interior span [3 s, end-3 s], Welch nperseg 4096, band 30-80 Hz;')
    print('"prom" = band max PSD / band median PSD - a descriptor, no validated')
    print('threshold; "rail" = per-motor samples at motorOutput hi end):\n')
    M = {}
    hdr = (f'{"cell":34s} {"wc":>3s} {"wo":>3s} {"b0y":>4s} {"dur":>6s} {"vbat":>9s} '
           f'{"gate%":>5s} {"rail":>5s} {"yaw med/p90":>11s} {"pkHz":>6s} '
           f'{"prom":>8s} {"band":>6s}')
    print(hdr)
    for gname, stems in GROUPS:
        print(f'-- {gname}')
        for s in stems:
            M[s] = metrics(s)
            mm, hd = M[s], hds[s]
            wc = hd['adrcWC'].split(',')[2]
            wo = hd['adrcWO'].split(',')[2]
            b0y = hd['adrcB0'].split(',')[2]
            print(f'{s:34s} {wc:>3s} {wo:>3s} {b0y:>4s} {mm["dur"]:6.1f} '
                  f'{mm["vmin"]:4.2f}-{mm["vmax"]:4.2f} {mm["gate"]:5.1f} '
                  f'{mm["rail"]:5d} {mm["med_y"]:5.1f}/{mm["p90_y"]:5.1f} '
                  f'{mm["pk_hz"]:6.2f} {mm["prom"]:8.1f} {mm["band"]:6.2f}')
    print('\nBattery: per-cell vbat spans above; minima range '
          f'{min(M[s]["vmin"] for s in STEMS):.2f}-{max(M[s]["vmin"] for s in STEMS):.2f} V '
          'across cells, so pack state is not identical between cells.')

    print('\nWhere the 30-80 Hz yaw peak sits vs the yaw observer bandwidth wo:')
    print('  wc varies, wo fixed at 80:  ' + ', '.join(
        f'wc={hds[s]["adrcWC"].split(",")[2]} -> {M[s]["pk_hz"]:.2f} Hz'
        for s in GROUPS[0][1]))
    print('  wc = wo varies together:    ' + ', '.join(
        f'wo={hds[s]["adrcWO"].split(",")[2]} -> {M[s]["pk_hz"]:.2f} Hz'
        for s in GROUPS[1][1]))
    print('  Same-wc pairs, wo 80 vs wo = wc:')
    for a, b in zip(GROUPS[0][1], GROUPS[1][1]):
        woa = hds[a]['adrcWO'].split(',')[2]
        wob = hds[b]['adrcWO'].split(',')[2]
        print(f'    wc={hds[a]["adrcWC"].split(",")[2]}: wo={woa} -> '
              f'{M[a]["pk_hz"]:.2f} Hz vs wo={wob} -> {M[b]["pk_hz"]:.2f} Hz')
    print('  Observed association only, one flight per cell: with wo held at 80')
    print('  the peak stays in a 47.0-53.5 Hz range for every wc; when wo moves')
    print('  down with wc the peak moves down with it (to 34.43 Hz at wo = 50).')
    print('  The cleanest same-link-rate contrast is the wc=50 pair (both 166 Hz):')
    print('  wo 80 -> 47.01 Hz vs wo 50 -> 34.43 Hz with wc identical. The')
    print('  frequency follows the observer bandwidth more closely than the')
    print('  controller bandwidth in these cells. No mechanism is established,')
    print('  and the link-rate confound above applies to the cross-cluster pairs.')

    a, b = 'Air65_yaw_wc_80_', 'Air65_yaw_wc_wo_80_'
    print('\nRepeated cell - matching wc/wo/b0 tune flown in both sweeps (headers'
          '\n  not fully identical: rx_smoothed '
          f'{hds[a]["rc_smoothing_rx_smoothed"]} vs {hds[b]["rc_smoothing_rx_smoothed"]}, '
          f'vbatref {hds[a]["vbatref"]} vs {hds[b]["vbatref"]}): '
          f'{M[a]["pk_hz"]:.2f} vs {M[b]["pk_hz"]:.2f} Hz, '
          f'prominence {M[a]["prom"]:.1f} vs {M[b]["prom"]:.1f}, band RMS '
          f'{M[a]["band"]:.2f} vs {M[b]["band"]:.2f} deg/s - the only repeated cell '
          'in this 11-log set. One repeat')
    print('  shows one realised between-flight difference; it is not a variance')
    print('  estimate for the other cells.')

    print('\nYaw b0 878 cells (sum-preserving redistribution, his description):')
    for s5, s8 in (('Air65_yaw_wc_wo_50_', 'Air65_yaw_wc_wo_50_adjusted_bo_'),
                   ('Air65_yaw_wc_wo_60_', 'Air65_yaw_wc_wo_60_adjusted_bo_')):
        p = M[s5]
        q = M[s8]
        print(f'  wc=wo={hds[s5]["adrcWC"].split(",")[2]}: b0y 2340 -> 878 moves band '
              f'RMS {p["band"]:.2f} -> {q["band"]:.2f} deg/s, prominence '
              f'{p["prom"]:.1f} -> {q["prom"]:.1f}, yaw med {p["med_y"]:.1f} -> '
              f'{q["med_y"]:.1f} deg/s, duration {p["dur"]:.1f} -> {q["dur"]:.1f} s')
    s = 'Air65_yaw_wc_wo_60_adjusted_bo_'
    t, ey, thr = M[s]['_t'], M[s]['_ey'], M[s]['_thr']
    print(f'  The wc=wo=60 / b0y=878 flight is the shortest log in the set '
          f'({M[s]["dur"]:.1f} s); its vbat floor is {M[s]["vmin"]:.2f} V (reached at '
          f'{M[s]["t_vmin"]:.1f} s)')
    print(f'  and the final vbat sample is {M[s]["vend"]:.2f} V - not a sagged pack.')
    print('  Note: its stock-b0 counterpart was flown at rx_smoothed 166 vs 333 here,')
    print('  so this pair crosses link-rate clusters as well. Yaw error in 2-s slices:')
    for lo in np.arange(0, float(t[-1]), 2.0):
        w = (t >= lo) & (t < lo + 2.0)
        if w.sum() < 100:
            continue
        rms = float(np.sqrt(np.mean(ey[w] ** 2)))
        print(f'    {lo:4.0f}-{lo + 2:.0f} s yaw err RMS {rms:6.1f} deg/s, '
              f'throttle {thr[w].min():.0f}-{thr[w].max():.0f}')
    print('  A sustained large-amplitude yaw error component at the band peak')
    print(f'  ({M[s]["pk_hz"]:.2f} Hz, prominence {M[s]["prom"]:.1f}) is present '
          'through the flight; the log ends')
    print('  after 12.8 s. Why the flight ended is not recorded - observed data')
    print('  only. In ADRC terms a lower b0 scales the P/D output up (u = kp*e/b0),')
    print('  which raises small-signal loop gain; that is the direction consistent')
    print('  with a reduced oscillation margin, but one flight does not establish')
    print('  the mechanism.')

    s = 'Air65_lower_RP_raise_Y_'
    full = [x for x in STEMS if M[x]['dur'] >= 30.0]
    top = max(full, key=lambda x: M[x]['band'])
    print(f'\nThe raised-yaw cell (yaw wc = wo = 88; roll/pitch simultaneously')
    print(f'  lowered to wc {hds[s]["adrcWC"].split(",")[0]} / wo '
          f'{hds[s]["adrcWO"].split(",")[0]} from 84/140, so this is a whole-tune')
    print('  cell, not a single-knob yaw change): peak '
          f'{M[s]["pk_hz"]:.2f} Hz, prominence {M[s]["prom"]:.1f}, band RMS '
          f'{M[s]["band"]:.2f} deg/s.')
    print(f'  Among the {len(full)} logs with duration >= 30 s (the criterion for')
    print(f'  "full-length" here; the 12.8-s log is excluded), the largest band RMS')
    print(f'  is {M[top]["band"]:.2f} deg/s and belongs to this cell.'
          if top == s else f'  largest is {M[top]["band"]:.2f} ({top}).')


if __name__ == '__main__':
    main()

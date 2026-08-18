#!/usr/bin/env python3
"""The b0-formula test flight: provenance, metrics, yaw error content, punch event.

One 190-s acro flight by @8ksal8 on the Air65 R, on a tune he attributes
to his power-to-inertia b0 estimator (comment id 5322423074; the flown b0
header sits ~1.6 % below the comment's worked example, so the estimator
provenance is his report, not a log fact), with the
main Betaflight gyro/dterm filter stages disabled (the ADRC observer's own
input PT2 remains active - see the header print). One flight - every number
below is a single observation.
"""
import csv
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np
from scipy.signal import welch

HERE = os.path.dirname(os.path.abspath(__file__))
STEM = 'b0_calc_test7_yaw78_80'


def decoder():
    p = os.environ.get('BLACKBOX_DECODE')
    if p:
        return p
    from shutil import which
    p = which('blackbox_decode')
    if p:
        return p
    sys.exit('set BLACKBOX_DECODE')


def ensure_csv():
    workdir = os.path.join(HERE, '_decoded')
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, f'{STEM}.01.csv')
    if os.path.exists(path):
        return path
    bbl = os.path.join(workdir, f'{STEM}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(HERE, f'{STEM}.bbl.gz'), 'rb') as fi, open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', bbl], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def headers():
    out = {}
    with gzip.open(os.path.join(HERE, f'{STEM}.bbl.gz'), 'rb') as fh:
        blob = fh.read()
    for line in blob.split(b'\n'):
        if not line.startswith(b'H '):
            break
        if b':' in line:
            k, _, v = line[2:].partition(b':')
            out[k.decode('ascii', 'replace')] = v.decode('ascii', 'replace').strip()
    return out


def main():
    h = hashlib.sha256()
    with gzip.open(os.path.join(HERE, f'{STEM}.bbl.gz'), 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    print(f'# {STEM}\n\nSHA-256 of the decompressed .bbl: {h.hexdigest()}\n')

    hd = headers()
    print('Tune and filter state from the header:')
    for k in ('Firmware revision', 'Craft name', 'pid_type', 'adrcWC', 'adrcWO', 'adrcB0',
              'adrc_hover_throttle', 'adrc_gyro_lpf_hz', 'dyn_idle_min_rpm',
              'gyro_lpf1_static_hz', 'gyro_lpf1_dyn_hz', 'gyro_lpf2_static_hz',
              'gyro_notch_hz', 'gyro_notch_cutoff', 'dyn_notch_count',
              'rpm_filter_harmonics', 'yaw_lowpass_hz',
              'dterm_lpf1_static_hz', 'dterm_lpf1_dyn_hz', 'dterm_lpf2_static_hz',
              'dterm_notch_hz', 'dterm_notch_cutoff',
              'simplified_gyro_filter', 'features'):
        print(f'  {k}: {hd.get(k)}')
    wc = [float(x) for x in hd['adrcWC'].split(',')]
    wo = [float(x) for x in hd['adrcWO'].split(',')]
    print(f'  wo/wc per axis: ' + ', '.join(f'{o/c:.2f}' for c, o in zip(wc, wo)))
    print('  (The main Betaflight gyro/dterm stages are disabled - activation')
    print('  keys above - while the ADRC observer\'s own input PT2 remains at')
    print(f'  adrc_gyro_lpf_hz = {hd.get("adrc_gyro_lpf_hz")} Hz, so "no filtering" is not the right')
    print('  reading; "main profile chain out of the loop" is.)')

    rows = list(csv.DictReader(open(ensure_csv()), skipinitialspace=True))

    def col(n):
        k = next(kk for kk in rows[0] if kk.strip() == n)
        return np.array([float(r[k]) for r in rows])

    t = (col('time (us)') - col('time (us)')[0]) / 1e6
    m = np.vstack([col(f'motor[{i}]') for i in range(4)])
    vb = col('vbatLatest (V)')
    hi_end = float(hd['motorOutput'].split(',')[1])
    rail = m >= hi_end
    n_rail = int(rail.sum())
    print(f'\nBasics: span {t[-1]:.1f} s, vbat {vb.min():.2f}-{vb.max():.2f} V, '
          f'motor-rail samples {n_rail}')
    seg = lambda a, b: 100 * rail[:, (t >= a) & (t < b)].sum() / n_rail
    print(f'  rail samples are spread across the flight, not concentrated in the')
    print(f'  punch: {seg(0, 150):.1f} % before 150 s, {seg(160, 168.5):.1f} % in 160-168.5 s, '
          f'{seg(168.5, 171.5):.1f} % in the')
    print(f'  168.5-171.5 s punch window (per-motor rail cells)')
    for ax, nm in ((0, 'roll'), (1, 'pitch'), (2, 'yaw')):
        e = np.abs(col(f'setpoint[{ax}]') - col(f'gyroADC[{ax}]'))
        print(f'  {nm}: err med {np.median(e):.1f} p90 {np.percentile(e, 90):.1f} '
              f'max {e.max():.0f} deg/s')
    gate = col('debug[7]')
    print(f'  liftoff gate open {100 * (gate > 0).mean():.1f} % of frames')
    amps = col('amperageLatest (A)')
    print(f'  pack electrical proxy vbat*amperage: peak {float((vb * amps).max()):.2f} W')
    print('  (pack-level electrical input, not per-motor continuous mechanical')
    print('  power - stated for the formula discussion, not as its input)')

    print('\nYaw error content in a 60-s cruise window centred mid-flight:')
    lo = float(t[-1]) / 2 - 30
    w = (t >= lo) & (t < lo + 60)
    e = col('setpoint[2]')[w] - col('gyroADC[2]')[w]
    sp2 = col('setpoint[2]')[w]
    ts = t[w]
    fs = (len(ts) - 1) / (ts[-1] - ts[0])
    tu = np.arange(ts[0], ts[-1], 1 / fs)
    eu = np.interp(tu, ts, e)
    su = np.interp(tu, ts, sp2)
    f, P = welch(eu - eu.mean(), fs=fs, nperseg=2048)
    fseek = (f > 0) & (f < 400)
    pk_all = float(f[fseek][np.argmax(P[fseek])])
    print(f'  yaw error spectrum maximum (f > 0): {pk_all:.2f} Hz '
          f'(err RMS in window {np.sqrt(np.mean(eu ** 2)):.1f} deg/s)')
    fS, PS = welch(su - su.mean(), fs=fs, nperseg=2048)
    from scipy.signal import coherence
    fc, C = coherence(su - su.mean(), eu - eu.mean(), fs=fs, nperseg=2048)
    ci = int(np.argmin(np.abs(fc - pk_all)))
    print(f'  yaw setpoint PSD at that frequency is substantial and the')
    print(f'  setpoint-error coherence there is {C[ci]:.2f} - the low-frequency')
    print('  error content coincides with commanded yaw motion, so this log does')
    print('  NOT separate an autonomous "tail wag" from ordinary tracking of the')
    print('  pilot\'s yaw input; no wag attribution is made.')
    b3080 = float(np.sqrt(P[(f >= 30) & (f < 80)].sum() * (f[1] - f[0])))
    print(f'  yaw error 30-80 Hz band RMS in the same window: {b3080:.2f} deg/s -')
    print('  the band the filter campaigns tracked stays small here.')

    print('\nThe end-of-pack punch event (0.5-s slices):')
    g = [col(f'gyroADC[{i}]') for i in range(3)]
    thr = col('rcCommand[3]')
    late = t >= 168.5
    t_thr = float(t[late][np.argmax(thr[late] >= 2000)])
    t_rail = float(t[late][np.argmax(rail[:, late].any(axis=0))])
    w167 = (t >= 166.5) & (t < 168.5)
    pk167 = max(float(np.abs(g[i][w167]).max()) for i in range(3))
    print(f'  exact transitions within this window: throttle first reaches 2000 at')
    print(f'  {t_thr:.2f} s; a motor first touches the rail at {t_rail:.2f} s. (An earlier')
    print(f'  full-throttle excursion exists near 167 s with gyro peaks <= {pk167:.0f} deg/s')
    print('  in 166.5-168.5 s. The slice table below is binned: "169.0" labels a')
    print('  0.5-s slice, not an event timestamp.)')
    for lo2 in np.arange(168.5, 171.5, 0.5):
        w2 = (t >= lo2) & (t < lo2 + 0.5)
        pk = [float(np.abs(g[i][w2]).max()) for i in range(3)]
        print(f'  {lo2:6.1f}s gyro {pk[0]:5.0f}/{pk[1]:5.0f}/{pk[2]:5.0f} '
              f'throttle {thr[w2].min():.0f}-{thr[w2].max():.0f} '
              f'motors {m[:, w2].min():.0f}-{m[:, w2].max():.0f} '
              f'vbat min {vb[w2].min():.2f} V')
    after = (t >= 170.5) & (t < 171.0)
    pk = [float(np.abs(g[i][after]).max()) for i in range(3)]
    print(f'  by 170.5 s the peaks are back to {pk[0]:.0f}/{pk[1]:.0f}/{pk[2]:.0f} deg/s and')
    print(f'  the log continues to {t[-1]:.1f} s. Observed sequence only: full-throttle')
    print('  punch on a deeply sagged pack; motors at the rail; a ~0.6 s tumble')
    print('  that subsides while the throttle is still high; flight resumes. The')
    print('  ordering does not establish what triggered or ended the tumble. The')
    print('  crash_recovery / yaw_spin_recovery settings are not recorded in this')
    print('  header (the tester reports Betaflight crash recovery was off - his')
    print('  report, not a log fact), so the log shows the recovery itself, not')
    print('  which mechanism produced it.')


if __name__ == '__main__':
    main()

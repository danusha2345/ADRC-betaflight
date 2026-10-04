#!/usr/bin/env python3
"""A/B of adrc_motor_tau_ms = 0 vs the fitted tau on the same craft and tune (jmsweng, mp2, 2026-10-04).

Per log: chirp sweeps (if any) -> measured closed-loop T(f) = S_ry/S_rr and plant H = S_ry/S_ru with a
lag+delay fit; stick moves outside the chirp -> 50 % lag and peak/setpoint; calm flight -> per-segment gyro RMS;
noise -> D-term and motor high-frequency RMS; context -> throttle, battery, motor saturation.
"""
import sys, os, glob
import numpy as np
from scipy.signal import welch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_check import read_headers, load_csv
from chirp_id import etfe, fit_plant
from ab_mp1 import moves, band_rms

D = os.path.expanduser('~/storage/adrc-logs/jmsweng-20261004-mp2ab/_decoded')

def find_sweeps(t, R, dt, chirp_s):
    """{axis: [(t0, t1)]}: a sweep is a run of >= 5 consecutive seconds whose dominant setpoint frequency rises
    monotonically and passes 40 Hz; the analysis window is the chirp_s seconds ending one second after the run."""
    n = int(1.0 / dt); out = {}
    for ax in range(3):
        r = R[ax]; pf = []; sd = []; ts = []
        for s in range(0, len(r) - n, n):
            seg = r[s:s + n] - r[s:s + n].mean(); X = np.abs(np.fft.rfft(seg * np.hanning(n))); fr = np.fft.rfftfreq(n, dt)
            pf.append(fr[np.argmax(X[1:]) + 1]); sd.append(seg.std()); ts.append(t[s])
        pf, sd, ts = np.array(pf), np.array(sd), np.array(ts); runs = []; i = 1
        while i < len(pf):
            j = i
            while j + 1 < len(pf) and pf[j + 1] > pf[j] and sd[j + 1] > 3: j += 1
            if j - i >= 4 and pf[j] >= 40 and pf[i] <= 12:
                runs.append((max(t[0], ts[j] + 1.5 - chirp_s), ts[j] + 1.5)); i = j + 1
            else: i += 1
        if runs: out[ax] = runs
    return out

def analyse(path):
    h = read_headers(path.replace('.csv', '.headers.csv'))
    cols = ['time (us)'] + [f'axis{k}[{a}]' for a in range(3) for k in 'PIDF'] + [f'setpoint[{a}]' for a in range(4)] \
         + [f'gyroADC[{a}]' for a in range(3)] + [f'motor[{i}]' for i in range(4)] + ['debug[7]', 'vbatLatest (V)']
    d = load_csv(path, cols); t = d['time (us)'] * 1e-6; t -= t[0]; dt = np.median(np.diff(t)); fs = 1 / dt
    gate = d['debug[7]'] > 0; thr = d['setpoint[3]'] / 10; air = gate & (thr > 10)
    mot = np.c_[[d[f'motor[{i}]'] for i in range(4)]].T
    chirp_s = float(h.get('chirp_time_seconds', 20))
    sweeps = find_sweeps(t, [d[f'setpoint[{a}]'] for a in range(3)], dt, chirp_s)
    in_chirp = np.zeros(len(t), bool)
    for ax, runs in sweeps.items():
        for (a, b) in runs: in_chirp |= (t >= a - 1) & (t <= b + 1)
    res = dict(tau=h.get('adrc_motor_tau_ms'), dur=t[-1], fs=fs, thr=np.median(thr[air]), vbat=(np.percentile(d['vbatLatest (V)'][air], 95), np.percentile(d['vbatLatest (V)'][air], 5)),
               sat=np.mean((mot[air].max(axis=1) >= 2040)), sweeps=sweeps, mot_hf=np.mean([band_rms(mot[air & ~in_chirp, i], fs, 40, fs / 2) for i in range(4)]), axes={})
    pslim = float(h.get('pidsum_limit', 500))
    for ax, name in ((0, 'roll'), (1, 'pitch'), (2, 'yaw')):
        r = d[f'setpoint[{ax}]']; y = d[f'gyroADC[{ax}]']; P, I, Dd, F = (d[f'axis{k}[{ax}]'] for k in 'PIDF')
        A = {}
        # chirp
        if ax in sweeps:
            a, b = sweeps[ax][0]; m = (t >= a) & (t <= b)
            rr, yy = r[m] - r[m].mean(), y[m] - y[m].mean(); uu = np.clip((P + I + Dd + F)[m], -pslim, pslim); uu = uu - uu.mean()
            f, H, T, Cry, Cru = etfe(rr, uu, yy, fs, nper=2048)
            ok = (f >= 1.5) & (f <= 60) & (Cry >= 0.8)
            A['T'] = (f, T, Cry)
            if ok.sum() > 8:
                ip = np.argmax(np.abs(T[ok])); A['Tpk'] = (abs(T[ok][ip]), f[ok][ip])
                # -3 dB bandwidth: first frequency above the peak where |T| < 0.707
                above = np.where((f > f[ok][ip]) & (np.abs(T) < 0.707) & (f < 80))[0]; A['bw'] = f[above[0]] if len(above) else np.nan
                # phase lag at 5 and 10 Hz
                A['ph'] = tuple(np.degrees(np.angle(T[np.argmin(abs(f - fr))])) for fr in (5, 10))
                A['T_at'] = tuple(abs(T[np.argmin(abs(f - fr))]) for fr in (3, 5, 8, 12, 20))
                try:
                    fit = fit_plant(f, H, Cry, fmax=100.0); (b3, tau3, d3), e3 = fit['lag_delay']; A['plant'] = (b3, tau3, d3, e3)
                except Exception as ex: A['plant'] = None
        # stick moves outside chirp
        mv = [m_ for m_ in moves(r, dt) if gate[m_[0]:m_[1]].all() and not in_chirp[m_[0]:m_[1]].any()]
        rat, lag = [], []
        for (i0, i1, sg) in mv:
            w0 = max(0, i0 - int(0.05 / dt)); seg = slice(w0, i1); pr = np.max(sg * (r[seg] - r[w0])); py = np.max(sg * (y[seg] - y[w0]))
            if pr >= 120:
                rat.append(py / pr); rs = sg * (r[seg] - r[w0]); ys = sg * (y[seg] - y[w0])
                if ys.max() >= 0.5 * pr: lag.append((np.argmax(ys >= 0.5 * pr) - np.argmax(rs >= 0.5 * pr)) * dt * 1e3)
        A['moves'] = (len(rat), np.median(rat) if rat else np.nan, np.mean(np.array(rat) > 1.1) if rat else np.nan, np.median(lag) if lag else np.nan,
                      (np.percentile(rat, 25), np.percentile(rat, 75)) if rat else (np.nan, np.nan))
        # calm flight, per contiguous segment >= 0.5 s
        calm = air & ~in_chirp & (np.abs(r) < 10)
        idx = np.where(calm)[0]; segs = []
        if len(idx):
            s0 = prev = idx[0]
            for i in idx[1:]:
                if i != prev + 1:
                    if prev - s0 > int(0.5 * fs): segs.append((s0, prev))
                    s0 = i
                prev = i
            if prev - s0 > int(0.5 * fs): segs.append((s0, prev))
        rms = [np.std(y[a:b]) for a, b in segs]
        A['calm'] = (len(segs), sum(b - a for a, b in segs) * dt, np.median(rms) if rms else np.nan, np.percentile(rms, 90) if rms else np.nan)
        nc = air & ~in_chirp
        A['noise'] = (np.sqrt(np.mean(Dd[nc] ** 2)), band_rms(Dd[nc], fs, 40, fs / 2), band_rms(y[calm], fs, 40, fs / 2) if calm.sum() > 2048 else np.nan,
                      np.sqrt(np.mean((r - y)[calm] ** 2)) if calm.sum() else np.nan)
        res['axes'][name] = A
    return res

def show(label, files):
    print(f"\n################ {label}")
    R = [analyse(f) for f in files]
    for r in R:
        print(f"\n### tau = {r['tau']}: {r['dur']:.0f} s, log {r['fs']:.0f} Hz, throttle median {r['thr']:.0f} %, vbat {r['vbat'][0]:.2f} -> {r['vbat'][1]:.2f} V, a motor at max {100*r['sat']:.1f} % of airborne time, motor 40+ Hz RMS {r['mot_hf']:.1f}")
        print("    chirp sweeps: " + ("; ".join(f"axis {ax}: " + ", ".join(f"{a:.0f}-{b:.0f} s" for a, b in runs) for ax, runs in r['sweeps'].items()) or "none"))
        for name, A in r['axes'].items():
            n, pk, o10, lag, iqr = A['moves']; cs, cdur, cmed, cp90 = A['calm']; Drms, Dhf, ghf, ecalm = A['noise']
            line = f"  {name:5}: moves {n:3d} peak/sp {pk:.3f} (IQR {iqr[0]:.2f}-{iqr[1]:.2f}, >10 % over {100*o10:.0f} %), 50 % lag {lag:.1f} ms | calm {cs} segs/{cdur:.0f} s gyro RMS med {cmed:.1f} p90 {cp90:.1f}, err {ecalm:.1f} | D RMS {Drms:.1f} (40+ Hz {Dhf:.2f}), gyro 40+ Hz {ghf:.2f}"
            print(line)
            if 'Tpk' in A:
                pl = A.get('plant')
                print(f"         chirp: |T| peak {A['Tpk'][0]:.3f} at {A['Tpk'][1]:.1f} Hz, -3 dB at {A['bw']:.1f} Hz, phase at 5/10 Hz {A['ph'][0]:.0f}/{A['ph'][1]:.0f} deg, |T| at 3/5/8/12/20 Hz " + "/".join(f"{x:.2f}" for x in A['T_at'])
                      + (f" | plant: b_acc {pl[0]:.1f}, tau {pl[1]*1e3:.1f} ms, delay {pl[2]*1e3:.1f} ms (err {pl[3]:.3f})" if pl else ""))
    return R

if __name__ == '__main__':
    show('2.5 inch (wc 80 / wo 90, b0 4616/3636/5453)', [D + '/mp2_test_flights_2.5_in/tau_0.01.csv', D + '/mp2_test_flights_2.5_in/tau_22.01.csv'])
    show('5 inch (wc 80 / wo 90, b0 2529/2692/3021)', [D + '/mp2_test_flights_5_in/tau_0.01.csv', D + '/mp2_test_flights_5_in/tau_23.01.csv'])

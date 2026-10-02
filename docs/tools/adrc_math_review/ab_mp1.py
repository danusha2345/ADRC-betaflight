#!/usr/bin/env python3
"""A/B of adrc_motor_tau_ms on the same craft and tune (8ksal8, Pavo20 Pro II, mp1, 2026-10-02)."""
import sys, os, glob
import numpy as np
from scipy.signal import welch, butter, filtfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_check import read_headers, load_csv

D = os.path.expanduser('~/storage/adrc-logs/8ksal8-20261002-mp1/_decoded')

def moves(r, dt, amp=150.0, win=0.10, after=0.15):
    n_w = int(win / dt); n_a = int(after / dt); i = n_w; out = []
    while i < len(r) - n_a:
        if abs(r[i] - r[i - n_w]) >= amp:
            out.append((i - n_w, i + n_a, np.sign(r[i] - r[i - n_w]))); i += n_a
        else: i += 1
    return out

def band_rms(x, fs, f0, f1):
    f, P = welch(x - x.mean(), fs=fs, nperseg=1024)
    m = (f >= f0) & (f < f1); return np.sqrt(np.trapezoid(P[m], f[m]))

def analyse(path):
    h = read_headers(path.replace('.csv', '.headers.csv'))
    cols = ['time (us)'] + [f'axis{k}[{a}]' for a in (0, 1) for k in 'PIDF'] + [f'setpoint[{a}]' for a in (0, 1)] + ['setpoint[3]'] \
         + [f'gyroADC[{a}]' for a in (0, 1)] + [f'motor[{i}]' for i in range(4)] + ['debug[7]', 'vbatLatest (V)']
    d = load_csv(path, cols); t = d['time (us)'] * 1e-6; dt = np.median(np.diff(t)); fs = 1 / dt
    gate = d['debug[7]'] > 0; thr = d['setpoint[3]'] / 10
    air = gate & (thr > 15)
    res = dict(tau=h.get('adrc_motor_tau_ms'), dur=t[-1] - t[0], fs=fs, thr_med=np.median(thr[air]), vbat=np.median(d['vbatLatest (V)'][air]))
    for ax, name in ((0, 'roll'), (1, 'pitch')):
        r = d[f'setpoint[{ax}]']; y = d[f'gyroADC[{ax}]']
        P, I, Dd, F = (d[f'axis{k}[{ax}]'] for k in 'PIDF')
        err = r - y
        mv = [m for m in moves(r, dt) if gate[m[0]:m[1]].all()]
        ratios = []; lags = []
        for (i0, i1, sg) in mv:
            w0 = max(0, i0 - int(0.05 / dt)); seg = slice(w0, i1)
            pr = np.max(sg * (r[seg] - r[w0])); py = np.max(sg * (y[seg] - y[w0]))
            if pr >= 120:
                ratios.append(py / pr)
                # lag: time between setpoint and gyro reaching 50 % of the move
                rs = sg * (r[seg] - r[w0]); ys = sg * (y[seg] - y[w0])
                ir = np.argmax(rs >= 0.5 * pr); iy = np.argmax(ys >= 0.5 * pr)
                if ys.max() >= 0.5 * pr: lags.append((iy - ir) * dt * 1e3)
        ratios = np.array(ratios); lags = np.array(lags)
        act = air & (np.abs(r) > 50)
        calm = air & (np.abs(r) < 10)
        res[name] = dict(n=len(ratios), pk=np.median(ratios) if len(ratios) else np.nan,
                         pk_iqr=(np.percentile(ratios, 25), np.percentile(ratios, 75)) if len(ratios) else (np.nan, np.nan),
                         over10=np.mean(ratios > 1.10) if len(ratios) else np.nan, lag=np.median(lags) if len(lags) else np.nan,
                         err_act=np.sqrt(np.mean(err[act] ** 2)), err_calm=np.sqrt(np.mean(err[calm] ** 2)),
                         D_rms=np.sqrt(np.mean(Dd[air] ** 2)), P_rms=np.sqrt(np.mean(P[air] ** 2)),
                         Dhf=band_rms(Dd[air], fs, 40, fs / 2), gyro_hf=band_rms(y[calm], fs, 40, fs / 2),
                         gyro_lf_calm=band_rms(y[calm], fs, 2, 40))
    mot = np.c_[[d[f'motor[{i}]'] for i in range(4)]].T
    res['mot_hf'] = np.mean([band_rms(mot[air, i], fs, 40, fs / 2) for i in range(4)])
    res['mot_mean'] = mot[air].mean()
    return res

if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(D, 'Pavo20_Pro_motor_tau_ms*_btfl_001.01.csv')))
    R = [analyse(f) for f in files]
    for r in R:
        print(f"\n### adrc_motor_tau_ms = {r['tau']}: {r['dur']:.0f} s, log {r['fs']:.0f} Hz, throttle median {r['thr_med']:.0f} %, vbat median {r['vbat']:.2f} V, motor mean {r['mot_mean']:.0f}, motor HF(40+ Hz) {r['mot_hf']:.1f}")
        for ax in ('roll', 'pitch'):
            a = r[ax]
            print(f"  {ax:5}: {a['n']:3d} moves, peak/setpoint {a['pk']:.3f} (IQR {a['pk_iqr'][0]:.2f}–{a['pk_iqr'][1]:.2f}), >10 % over {100*a['over10']:.0f} %, 50 % lag {a['lag']:.1f} ms | "
                  f"err RMS active {a['err_act']:.1f}, calm {a['err_calm']:.1f} deg/s | P RMS {a['P_rms']:.1f}, D RMS {a['D_rms']:.1f}, D 40+ Hz {a['Dhf']:.1f} | gyro calm 2–40 Hz {a['gyro_lf_calm']:.2f}, 40+ Hz {a['gyro_hf']:.2f}")

#!/usr/bin/env python3
"""Check the motor-pole-in-z3 hypothesis against tester Blackbox logs (debug_mode = ADRC).

A. Plant identification, ESO-free:  dω/dt ≈ b_acc · pt1_τ(u)   (u = logged pidsum, grid over τ)
B. z3 decomposition:                 z3 ≈ −z2/τ + κ · LP3(b0·scale·u)   → τ_z3 and the relative b0 error κ
C. Replay of logged setpoint steps through the loop model (plain law as coded, and the motor-pole variant)
   with the identified plant, starting from the logged ESO state; overshoot ratio log vs model.
"""
import sys, csv, glob, os
import numpy as np
from scipy.signal import butter, filtfilt, lfilter

def read_headers(path):
    h = {}
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) >= 2: h[row[0].strip()] = row[1].strip()
    return h

def load_csv(path, cols):
    with open(path) as f:
        names = [c.strip() for c in f.readline().split(',')]
    idx = [names.index(c) for c in cols]
    data = np.loadtxt(path, delimiter=',', skiprows=1, usecols=idx, dtype=float, ndmin=2)
    return {c: data[:, i] for i, c in enumerate(cols)}

def pt1(x, hz, dt):
    om = 2 * np.pi * hz * dt; k = om / (om + 1)
    return lfilter([k], [1, -(1 - k)], x)

def pt1_tau(x, tau, dt):
    k = dt / (dt + tau)
    return lfilter([k], [1, -(1 - k)], x)

def lp3(x, w, dt):
    for _ in range(3): x = pt1_tau(x, 1 / w, dt)
    return x

def deriv(x, dt, hz=80.0):
    b, a = butter(2, hz / (0.5 / dt)); xs = filtfilt(b, a, x)
    return np.gradient(xs, dt), xs

def analyse(csv_path):
    hdr = read_headers(csv_path.replace('.csv', '.headers.csv'))
    wc = [float(v) for v in hdr['adrcWC'].split(',')]; wo = [float(v) for v in hdr['adrcWO'].split(',')]
    b0 = [float(v) for v in hdr['adrcB0'].split(',')]
    z3s = float(hdr.get('adrc_z3_log_scale', 16)); pslim = float(hdr.get('pidsum_limit', 500))
    loop_dt = float(hdr['looptime']) * 1e-6 * float(hdr.get('pid_process_denom', 1))
    cols = ['time (us)'] + [f'axis{k}[{a}]' for a in (0, 1) for k in 'PIDF'] + [f'setpoint[{a}]' for a in (0, 1)] \
         + [f'gyroADC[{a}]' for a in (0, 1)] + [f'debug[{i}]' for i in range(8)] + ['setpoint[3]']
    d = load_csv(csv_path, cols)
    t = d['time (us)'] * 1e-6; dt = np.median(np.diff(t))
    scale = d['debug[7]'] / 100.0; gate = scale > 0; scale = np.abs(scale)
    name = os.path.basename(csv_path).replace('.01.csv', '')
    print(f"\n### {name}: {hdr.get('Craft name','')} wc {wc[0]:.0f}/{wc[1]:.0f} wo {wo[0]:.0f}/{wo[1]:.0f} b0 {b0[0]:.0f}/{b0[1]:.0f}, "
          f"PID {1/loop_dt:.0f} Hz, log {1/dt:.0f} Hz, pidsum_limit {pslim:.0f}, adrc_gyro_lpf {hdr.get('adrc_gyro_lpf_hz')} Hz, "
          f"{t[-1]-t[0]:.0f} s, gate open {100*gate.mean():.0f} %")
    results = {}
    for ax, axname, zi in ((0, 'roll', (0, 1, 2)), (1, 'pitch', (3, 4, 5))):
        u = np.clip(sum(d[f'axis{k}[{ax}]'] for k in 'PIDF'), -pslim, pslim)
        y = d[f'gyroADC[{ax}]']; r = d[f'setpoint[{ax}]']
        z1, z2, z3 = d[f'debug[{zi[0]}]'], d[f'debug[{zi[1]}]'], d[f'debug[{zi[2]}]'] * z3s
        # ---- A: plant fit on airborne samples with real excitation
        ydot, ys = deriv(y, dt)
        m = gate & (np.abs(z2) < 32000) & (np.abs(z3 / z3s) < 32000)
        act = (pt1_tau(np.abs(np.gradient(r, dt)), 0.2, dt) > 100) | (pt1_tau(np.abs(r), 0.2, dt) > 80)  # stick activity
        mA = m & act
        best = None
        for tau in np.arange(0.002, 0.081, 0.001):
            for use_scale in (False, True):
                T = pt1_tau(u * (scale if use_scale else 1.0), tau, dt)
                X = np.c_[T[mA], np.ones(mA.sum())]
                coef, res, *_ = np.linalg.lstsq(X, ydot[mA], rcond=None)
                ss = np.sum((ydot[mA] - ydot[mA].mean())**2); r2 = 1 - np.sum((ydot[mA] - X @ coef)**2) / ss
                if best is None or r2 > best[0]: best = (r2, tau, coef[0], use_scale)
        r2, tau, b_acc, use_scale = best
        b0_fit = b_acc / tau
        # ---- B: how much of z3's variation is the structural term -z2/tau (tau from A, not fitted here)
        z3c = z3[mA] - z3[mA].mean(); pred = -z2[mA] / tau; pred -= pred.mean()
        ssB = np.sum(z3c**2); r2B = 1 - np.sum((z3c - pred)**2) / ssB
        X2 = np.c_[z2[mA], np.ones(mA.sum())]; c2, *_ = np.linalg.lstsq(X2, z3[mA], rcond=None)
        tau_z3 = -1 / c2[0] if c2[0] < 0 else float('nan'); r2_z2only = 1 - np.sum((z3[mA] - X2 @ c2)**2) / np.sum((z3[mA]-z3[mA].mean())**2)
        kappa = float('nan')
        print(f"  {axname:5} A: tau {tau*1e3:4.1f} ms, b_acc {b_acc:6.1f} deg/s^2/unit{' (x scale)' if use_scale else ''}, b_acc/tau = {b0_fit:6.0f} vs b0 {b0[ax]:.0f} (ratio {b0_fit/b0[ax]:.2f}), R2 {r2:.2f}, n {mA.sum()}"
              f"\n        B: var(z3) explained by -z2/tau_A: R2 {r2B:.2f}; free slope fit z3~z2 gives tau {tau_z3*1e3:5.1f} ms (R2 {r2_z2only:.2f}); wo·tau {wo[ax]*tau:.1f}, wc·tau {wc[ax]*tau:.2f}")
        results[axname] = dict(tau=tau, b_acc=b_acc, use_scale=use_scale, tau_z3=tau_z3, kappa=kappa)
        # ---- C: step replay
        steps = find_steps(t, r, dt)
        ratios_log, ratios_plain, ratios_meso, errs = [], [], [], []
        for (i0, i1, plateau) in steps:
            if not gate[i0:i1].all(): continue
            w0 = max(0, i0 - int(0.06 / dt)); w1 = min(len(t), i1 + int(0.15 / dt))
            seg = slice(w0, w1)
            ylog = y[seg]; rseg = r[seg]; tseg = t[seg] - t[w0]
            pk_log = np.max(np.sign(plateau) * ylog[int(0.06/dt):]) / abs(plateau)
            sim_p = replay(tseg, rseg, ylog[0], z1[w0], z2[w0], z3[w0], u[w0], scale[seg].mean(), wc[ax], wo[ax], b0[ax], b_acc, tau, loop_dt,
                           float(hdr.get('adrc_gyro_lpf_hz', 150)), pslim, meso=False, use_scale=use_scale)
            sim_m = replay(tseg, rseg, ylog[0], z1[w0], z2[w0], z3[w0], u[w0], scale[seg].mean(), wc[ax], wo[ax], b0[ax], b_acc, tau, loop_dt,
                           float(hdr.get('adrc_gyro_lpf_hz', 150)), pslim, meso=True, use_scale=use_scale)
            pk_p = np.max(np.sign(plateau) * sim_p[int(0.06/dt):]) / abs(plateau)
            pk_m = np.max(np.sign(plateau) * sim_m[int(0.06/dt):]) / abs(plateau)
            ratios_log.append(pk_log); ratios_plain.append(pk_p); ratios_meso.append(pk_m)
            errs.append(np.sqrt(np.mean((sim_p - ylog)**2)) / abs(plateau))
        if ratios_log:
            rl, rp, rm = map(np.array, (ratios_log, ratios_plain, ratios_meso))
            print(f"        C: {len(rl)} steps >= 150 deg/s: peak/plateau log median {np.median(rl):.3f} (IQR {np.percentile(rl,25):.2f}–{np.percentile(rl,75):.2f}); "
                  f"model plain {np.median(rp):.3f}; motor-pole variant {np.median(rm):.3f}; replay RMS err {np.median(errs)*100:.0f} % of plateau; "
                  f"share > 1.10: log {100*np.mean(rl>1.1):.0f} % / plain {100*np.mean(rp>1.1):.0f} % / meso {100*np.mean(rm>1.1):.0f} %")
        else:
            print("        C: no clean steps")
    return results

def find_steps(t, r, dt, amp=150.0, rise_max=0.04, hold=0.08, tol=0.2):
    n_rise = int(rise_max / dt); n_hold = int(hold / dt); steps = []; i = n_rise
    while i < len(r) - n_hold:
        d = r[i] - r[i - n_rise]
        if abs(d) >= amp and abs(r[i - n_rise]) < 0.3 * abs(d):
            plateau = r[i]; seg = r[i:i + n_hold]
            if np.all(np.abs(seg - plateau) <= tol * abs(plateau)):
                steps.append((i - n_rise, i + n_hold, plateau)); i += n_hold
                continue
        i += 1
    return steps

def replay(tseg, rseg, y0, z10, z20, z30, u0, sc, wc, wo, b0n, b_acc, tau, dt, lpf_hz, pslim, meso, use_scale=False):
    b0 = b0n * sc; kp = wc * wc; inv = 1 / tau if meso else 0.0; kd = 2 * wc - inv
    b1, b2, b3 = 3 * wo, 3 * wo**2, wo**3
    om = 2 * np.pi * lpf_hz * 1.553773974 * dt; k = om / (om + 1) if lpf_hz > 0 else 1.0
    n = int(tseg[-1] / dt); tt = np.arange(n) * dt; rr = np.interp(tt, tseg, rseg)
    s1 = s = z1 = y0; z2 = z20; z3 = z30; w = y0; Tm = u0; up = u0; out = np.empty(n)
    for i in range(n):
        s1 += k * (w - s1); s += k * (s1 - s); e = z1 - s
        z1 += dt * (z2 - b1 * e); z2 += dt * (z3 + b0 * up - inv * z2 - b2 * e); z3 += dt * (-0.3 * z3 - b3 * e)
        z3 = max(-pslim * b0, min(pslim * b0, z3))
        u = max(-pslim, min(pslim, (kp * (rr[i] - z1) - kd * z2 - z3) / b0)); up = u
        Tm += dt * (u - Tm) / tau; w += dt * b_acc * (sc if use_scale else 1.0) * Tm
        out[i] = w
    return np.interp(tseg, tt, out)

if __name__ == '__main__':
    files = sys.argv[1:] or sorted(glob.glob(os.path.expanduser('~/storage/adrc-logs/_decoded_mathreview/*.01.csv')))
    for f in files:
        try: analyse(f)
        except Exception as ex: print(f"\n### {os.path.basename(f)}: FAILED {ex!r}")

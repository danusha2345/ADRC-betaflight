#!/usr/bin/env python3
"""Closed-loop fit of the plant (b_acc, tau, delay) to logged stick moves.

For every stick move (>= 150 deg/s change within 40 ms) the loop model — the ADRC law exactly as coded, with the
log's own wc/wo/b0, pre-ESO lpf, sigma and pidsum limit — is driven by the logged setpoint from the logged ESO
state, against a plant  w' = b_acc T,  tau T' = u(t - d) - T.  The plant parameters are chosen to minimise the
median RMS error between the simulated and the logged gyro over all moves.  Then the same moves are replayed with
the motor-pole variant of the law to see what it would have done.
"""
import sys, os
import numpy as np
from log_check import read_headers, load_csv

def find_moves(r, dt, amp=150.0, win=0.10, after=0.15):
    n_w = int(win / dt); n_a = int(after / dt); i = n_w; out = []
    while i < len(r) - n_a:
        dr = r[i] - r[i - n_w]
        if abs(dr) >= amp:
            out.append((i - n_w, i + n_a, np.sign(dr))); i += n_a
        else: i += 1
    return out

def replay_vec(R, y0, z20, z30, u0, sc, wc, wo, b0n, sigma, lpf_hz, pslim, dt, b_acc, tau, d, meso=False):
    """R: (n_win, n_steps) setpoint at loop rate; initial states per window. Returns simulated gyro (n_win, n_steps)."""
    nw, n = R.shape
    b0 = b0n * sc; kp = wc * wc; inv = 1 / tau if meso else 0.0; kd = np.maximum(2 * wc - inv, 0.2 * wc)
    b1, b2, b3 = 3 * wo, 3 * wo**2, wo**3
    om = 2 * np.pi * lpf_hz * 1.553773974 * dt; k = om / (om + 1) if lpf_hz > 0 else 1.0
    nd = max(1, int(round(d / dt)))
    s1 = y0.copy(); s = y0.copy(); z1 = y0.copy(); z2 = z20.copy(); z3 = z30.copy(); w = y0.copy(); Tm = u0.copy(); up = u0.copy()
    ubuf = [u0.copy() for _ in range(nd)]; out = np.empty((nw, n))
    for i in range(n):
        s1 += k * (w - s1); s += k * (s1 - s); e = z1 - s
        z1 += dt * (z2 - b1 * e); z2 += dt * (z3 + b0 * up - inv * z2 - b2 * e); z3 += dt * (-sigma * z3 - b3 * e)
        np.clip(z3, -pslim * b0, pslim * b0, out=z3)
        u = np.clip((kp * (R[:, i] - z1) - kd * z2 - z3) / b0, -pslim, pslim); up = u
        ubuf.append(u); ua = ubuf.pop(0)
        Tm += dt * (ua - Tm) / tau; w += dt * b_acc * Tm
        out[:, i] = w
    return out

def analyse(csv_path, max_win=30):
    hdr = read_headers(csv_path.replace('.csv', '.headers.csv'))
    wc = [float(v) for v in hdr['adrcWC'].split(',')]; wo = [float(v) for v in hdr['adrcWO'].split(',')]
    b0 = [float(v) for v in hdr['adrcB0'].split(',')]
    z3s = float(hdr.get('adrc_z3_log_scale', 16)); pslim = float(hdr.get('pidsum_limit', 500))
    loop_dt = float(hdr['looptime']) * 1e-6 * float(hdr.get('pid_process_denom', 1))
    lpf = float(hdr.get('adrc_gyro_lpf_hz', 150)); sigma = float(hdr.get('adrc_sigma_decay', 3)) / 10
    cols = ['time (us)'] + [f'axis{k}[{a}]' for a in (0, 1) for k in 'PIDF'] + [f'setpoint[{a}]' for a in (0, 1)] \
         + [f'gyroADC[{a}]' for a in (0, 1)] + [f'debug[{i}]' for i in range(8)]
    d = load_csv(csv_path, cols)
    t = d['time (us)'] * 1e-6; dt = np.median(np.diff(t))
    scale = np.abs(d['debug[7]']) / 100.0; gate = d['debug[7]'] > 0
    name = os.path.basename(csv_path).replace('.01.csv', '')
    print(f"\n### {name}: {hdr.get('Craft name','')} wc {wc[0]:.0f}/{wc[1]:.0f} wo {wo[0]:.0f}/{wo[1]:.0f} b0 {b0[0]:.0f}/{b0[1]:.0f}, PID {1/loop_dt:.0f} Hz, log {1/dt:.0f} Hz, lpf {lpf:.0f}, sigma {sigma}, pidsum {pslim:.0f}")
    rows = []
    for ax, axname, zi in ((0, 'roll', (0, 1, 2)), (1, 'pitch', (3, 4, 5))):
        u = np.clip(sum(d[f'axis{k}[{ax}]'] for k in 'PIDF'), -pslim, pslim)
        y = d[f'gyroADC[{ax}]']; r = d[f'setpoint[{ax}]']
        z2, z3 = d[f'debug[{zi[1]}]'], d[f'debug[{zi[2]}]'] * z3s
        moves = [mv for mv in find_moves(r, dt) if gate[max(0, mv[0] - int(0.05/dt)):mv[1]].all()]
        if len(moves) > max_win:
            moves = [moves[i] for i in np.linspace(0, len(moves) - 1, max_win).astype(int)]
        if len(moves) < 5:
            print(f"  {axname:5}: only {len(moves)} usable stick moves"); continue
        pre = int(0.05 / dt); n_steps = int((0.05 + 0.10 + 0.15) / loop_dt) - 2
        tt = np.arange(n_steps) * loop_dt
        R = []; Y = []; y0 = []; z20 = []; z30 = []; u0 = []; sc = []; sg = []
        for (i0, i1, s_) in moves:
            w0 = i0 - pre; seg = slice(w0, i1); tseg = t[seg] - t[w0]
            R.append(np.interp(tt, tseg, r[seg])); Y.append(np.interp(tt, tseg, y[seg]))
            y0.append(y[w0]); z20.append(z2[w0]); z30.append(z3[w0]); u0.append(u[w0]); sc.append(scale[seg].mean()); sg.append(s_)
        R, Y = np.array(R), np.array(Y); y0, z20, z30, u0, sc, sg = map(np.array, (y0, z20, z30, u0, sc, sg))
        R0 = R[:, :1]; Y0 = Y[:, :1]
        pk_r = np.max(sg[:, None] * (R - R0), axis=1); ok = pk_r >= 120
        R, Y, y0, z20, z30, u0, sc, sg, pk_r, R0, Y0 = R[ok], Y[ok], y0[ok], z20[ok], z30[ok], u0[ok], sc[ok], sg[ok], pk_r[ok], R0[ok], Y0[ok]
        if len(R) < 5:
            print(f"  {axname:5}: only {len(R)} usable stick moves"); continue
        # grid search
        best = None
        for tau in (0.005, 0.008, 0.011, 0.015, 0.020, 0.027, 0.036, 0.048):
            for dly in (0.0, 0.005, 0.010, 0.015):
                for ratio in (0.5, 0.65, 0.8, 1.0, 1.25, 1.55, 1.9, 2.4):
                    b_acc = b0[ax] * tau * ratio
                    S = replay_vec(R, y0, z20, z30, u0, sc, wc[ax], wo[ax], b0[ax], sigma, lpf, pslim, loop_dt, b_acc, tau, dly)
                    err = np.median(np.sqrt(np.mean((S - Y)**2, axis=1)) / pk_r)
                    if best is None or err < best[0]: best = (err, b_acc, tau, dly, ratio)
        err, b_acc, tau, dly, ratio = best
        Sp = replay_vec(R, y0, z20, z30, u0, sc, wc[ax], wo[ax], b0[ax], sigma, lpf, pslim, loop_dt, b_acc, tau, dly)
        Sm = replay_vec(R, y0, z20, z30, u0, sc, wc[ax], wo[ax], b0[ax], sigma, lpf, pslim, loop_dt, b_acc, tau, dly, meso=True)
        rl = np.max(sg[:, None] * (Y - Y0), axis=1) / pk_r; rp = np.max(sg[:, None] * (Sp - Y0), axis=1) / pk_r; rm = np.max(sg[:, None] * (Sm - Y0), axis=1) / pk_r
        # how well does a no-lag plant (tau 4 ms, d 0) do, for contrast
        S0 = replay_vec(R, y0, z20, z30, u0, sc, wc[ax], wo[ax], b0[ax], sigma, lpf, pslim, loop_dt, b0[ax] * 0.004 * ratio, 0.004, 0.0)
        err0 = np.median(np.sqrt(np.mean((S0 - Y)**2, axis=1)) / pk_r)
        print(f"  {axname:5} {len(R)} moves: plant fit b_acc {b_acc:6.1f}, tau {tau*1e3:4.1f} ms, delay {dly*1e3:4.1f} ms (b_acc/tau = {ratio:.2f}·b0), replay err {err*100:4.1f} % of peak (no-lag plant: {err0*100:4.1f} %); "
              f"wo·tau {wo[ax]*tau:.1f}, wo·(tau+d) {wo[ax]*(tau+dly):.1f}\n"
              f"        peak gyro / peak setpoint: log {np.median(rl):.3f} (IQR {np.percentile(rl,25):.2f}–{np.percentile(rl,75):.2f}) | model as coded {np.median(rp):.3f} (IQR {np.percentile(rp,25):.2f}–{np.percentile(rp,75):.2f}) | motor-pole variant {np.median(rm):.3f} (IQR {np.percentile(rm,25):.2f}–{np.percentile(rm,75):.2f})"
              f" | share > 1.10: log {100*np.mean(rl>1.1):.0f} % / coded {100*np.mean(rp>1.1):.0f} % / mp {100*np.mean(rm>1.1):.0f} %")
        rows.append(dict(log=name, axis=axname, craft=hdr.get('Craft name',''), wc=wc[ax], wo=wo[ax], b0=b0[ax], b_acc=b_acc, tau=tau, d=dly, ratio=ratio, err=err, err0=err0,
                         n=len(R), rl=float(np.median(rl)), rp=float(np.median(rp)), rm=float(np.median(rm)), sl=float(np.mean(rl>1.1)), sp=float(np.mean(rp>1.1)), sm=float(np.mean(rm>1.1))))
    return rows

if __name__ == '__main__':
    import json
    rows = []
    for f in sys.argv[1:]:
        try: rows += analyse(f)
        except Exception as ex: print(f"\n### {os.path.basename(f)}: FAILED {ex!r}")
    json.dump(rows, open('logcheck3_rows.json', 'w'), indent=1)

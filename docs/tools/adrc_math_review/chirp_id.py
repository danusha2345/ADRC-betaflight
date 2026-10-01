#!/usr/bin/env python3
"""Plant identification from a Betaflight chirp flight on ADRC (setpoint sweep = exogenous excitation).

H_plant(f) = S_ry / S_ru   (unbiased in closed loop),  T(f) = S_ry / S_rr  (measured closed-loop tracking).
Fit H to  b_acc·e^(-s d) / ( s (1 + s τ) )  over the coherent band, then compare the measured T with the loop
model (law as coded / motor-pole variant) on the identified plant, and predict the step overshoot of both.
"""
import sys, os
import numpy as np
from scipy.signal import csd, coherence
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_check import read_headers, load_csv
from adrc_math_review import controller_dss, freqresp, plant_dss, pt1_resp, margins, DT
from adrc_math_review4 import controller_meso
from adrc_math_review3 import sim_meso, metrics

def etfe(r, u, y, fs, nper=4096):
    f, Sru = csd(r, u, fs=fs, nperseg=nper); _, Sry = csd(r, y, fs=fs, nperseg=nper); _, Srr = csd(r, r, fs=fs, nperseg=nper)
    _, Cry = coherence(r, y, fs=fs, nperseg=nper); _, Cru = coherence(r, u, fs=fs, nperseg=nper)
    return f, Sry / Sru, Sry / Srr, Cry, Cru

def fit_plant(f, H, C, fmin=1.5, fmax=150.0, cmin=0.8):
    band = (f >= fmin) & (f <= fmax) & (C >= cmin) & np.isfinite(H)
    w = 2 * np.pi * f[band]; Hb = H[band]; wgt = np.sqrt(C[band])
    def res3(p):
        b, tau, d = p; e = (b * np.exp(-1j * w * d) / (1j * w * (1 + 1j * w * tau)) - Hb) / np.abs(Hb) * wgt; return np.r_[e.real, e.imag]
    def res2(p):
        b, tau = p; e = (b / (1j * w * (1 + 1j * w * tau)) - Hb) / np.abs(Hb) * wgt; return np.r_[e.real, e.imag]
    def res4(p):  # two lags + delay
        b, t1, t2, d = p; e = (b * np.exp(-1j * w * d) / (1j * w * (1 + 1j * w * t1) * (1 + 1j * w * t2)) - Hb) / np.abs(Hb) * wgt; return np.r_[e.real, e.imag]
    b0g = np.median(np.abs(Hb) * w)
    best3 = min((least_squares(res3, [b0g, t0, d0], bounds=([1e-2, 1e-4, 0], [1e6, 0.5, 0.05])) for t0 in (0.005, 0.015, 0.04) for d0 in (0, 0.003, 0.01)), key=lambda s: s.cost)
    best2 = least_squares(res2, [b0g, 0.015], bounds=([1e-2, 1e-4], [1e6, 0.5]))
    best4 = min((least_squares(res4, [b0g, t0, 0.003, d0], bounds=([1e-2, 1e-4, 1e-4, 0], [1e6, 0.5, 0.5, 0.05])) for t0 in (0.01, 0.03) for d0 in (0, 0.005)), key=lambda s: s.cost)
    def res5(p):  # lead + lag + delay (yaw: reaction torque adds a zero)
        b, tz, tau, d = p; e = (b * (1 + 1j * w * tz) * np.exp(-1j * w * d) / (1j * w * (1 + 1j * w * tau)) - Hb) / np.abs(Hb) * wgt; return np.r_[e.real, e.imag]
    best5 = min((least_squares(res5, [b0g, tz0, t0, 0.002], bounds=([1e-2, 0, 1e-4, 0], [1e6, 1.0, 0.5, 0.05])) for tz0 in (0.01, 0.05, 0.2) for t0 in (0.005, 0.02)), key=lambda s: s.cost)
    err = lambda s: np.sqrt(np.mean(s.fun**2))
    return dict(band=band, lag_delay=(best3.x, err(best3)), lag=(best2.x, err(best2)), twolag_delay=(best4.x, err(best4)), lead_lag_delay=(best5.x, err(best5)))

def model_T(wc, wo, b0, b_acc, tau, d, w, loop_dt, lpf, sigma, gyro_lpf2, meso):
    if meso: A, B, C, D = controller_meso(wc, wo, b0, 1 / tau, sigma=sigma, gyro_lpf_hz=lpf, dt=loop_dt)
    else:    A, B, C, D = controller_dss(wc, wo, b0, sigma=sigma, gyro_lpf_hz=lpf, dt=loop_dt)
    H = freqresp(A, B, C, D, w, dt=loop_dt); Hy, Hr = H[:, 0], H[:, 1]
    Ad, Bd, Cd, Dd = plant_dss(b_acc, tau, dt=loop_dt); P = freqresp(Ad, Bd, Cd, Dd, w, dt=loop_dt)[:, 0, 0]
    z = np.exp(1j * w * loop_dt); Pd = P * z ** (-max(0, int(round(d / loop_dt))))
    G = pt1_resp(gyro_lpf2, w, dt=loop_dt) if gyro_lpf2 > 0 else 1.0
    L = -Hy * G * Pd
    T = Hr * Pd / (1 + L)            # r -> y (gyro before the BF filter)
    return T, L

def analyse(csv_path, segments):
    hdr = read_headers(csv_path.replace('.csv', '.headers.csv'))
    wc = [float(v) for v in hdr['adrcWC'].split(',')]; wo = [float(v) for v in hdr['adrcWO'].split(',')]; b0 = [float(v) for v in hdr['adrcB0'].split(',')]
    pslim = [float(hdr.get('pidsum_limit', 500))] * 2 + [float(hdr.get('pidsum_limit_yaw', 400))]
    loop_dt = float(hdr['looptime']) * 1e-6 * float(hdr.get('pid_process_denom', 1)); lpf = float(hdr.get('adrc_gyro_lpf_hz', 150)); sigma = float(hdr.get('adrc_sigma_decay', 3)) / 10
    glpf2 = float(hdr.get('gyro_lpf2_static_hz', 0))
    cols = ['time (us)'] + [f'axis{k}[{a}]' for a in range(3) for k in 'PIDF'] + [f'setpoint[{a}]' for a in range(3)] + [f'gyroADC[{a}]' for a in range(3)] + ['debug[7]']
    d = load_csv(csv_path, cols); t = d['time (us)'] * 1e-6; t -= t[0]; dt = np.median(np.diff(t)); fs = 1 / dt
    print(f"### {os.path.basename(csv_path)}: {hdr.get('Craft name')} wc {wc} wo {wo} b0 {b0} law {hdr.get('adrc_b0_law')} lpf {lpf:.0f} sigma {sigma} gyro_lpf2 {glpf2:.0f} PID {1/loop_dt:.0f} Hz log {fs:.0f} Hz")
    for ax, name in enumerate(('roll', 'pitch', 'yaw')):
        t0, t1 = segments[ax]; m = (t >= t0) & (t <= t1)
        r = d[f'setpoint[{ax}]'][m]; y = d[f'gyroADC[{ax}]'][m]; u = np.clip(sum(d[f'axis{k}[{ax}]'][m] for k in 'PIDF'), -pslim[ax], pslim[ax])
        sc = np.abs(d['debug[7]'][m]).mean() / 100
        r, y, u = r - r.mean(), y - y.mean(), u - u.mean()
        f, H, T, Cry, Cru = etfe(r, u, y, fs)
        fit = fit_plant(f, H, Cry)
        (b3, tau3, d3), e3 = fit['lag_delay']; (b2, tau2), e2 = fit['lag']; (b4, t41, t42, d4), e4 = fit['twolag_delay']
        band = fit['band']
        print(f"\n  {name} ({t0}-{t1} s, b0 scale {sc:.2f}): coherent band {f[band][0]:.1f}-{f[band][-1]:.1f} Hz ({band.sum()} bins)")
        print(f"    plant fits:  lag+delay: b_acc {b3:7.1f} deg/s^2/unit, tau {tau3*1e3:5.1f} ms, delay {d3*1e3:4.1f} ms, err {e3:.3f}"
              f" | lag only: b_acc {b2:7.1f}, tau {tau2*1e3:5.1f} ms, err {e2:.3f} | two lags+delay: b {b4:7.1f}, tau {t41*1e3:4.1f}/{t42*1e3:4.1f} ms, d {d4*1e3:3.1f} ms, err {e4:.3f}")
        print(f"    => b_acc/tau {b3/tau3:6.0f} vs configured b0 {b0[ax]:.0f} (ratio {b3/tau3/b0[ax]:.2f}); b_acc/(tau+d) {b3/(tau3+d3):6.0f}; wo*tau {wo[ax]*tau3:.2f}, wo*(tau+d) {wo[ax]*(tau3+d3):.2f}, wc*(tau+d) {wc[ax]*(tau3+d3):.2f}")
        (b5, tz5, tau5, d5), e5 = fit['lead_lag_delay']
        print(f"    lead+lag+delay: b {b5:7.1f}, zero at {1/tz5 if tz5>0 else float('inf'):6.1f} rad/s (T_z {tz5*1e3:5.1f} ms), tau {tau5*1e3:5.1f} ms, delay {d5*1e3:4.1f} ms, err {e5:.3f}")
        # margins and T from the MEASURED plant (controller model exact, plant as measured)
        wb = 2 * np.pi * f[1:]; Hm = H[1:]
        A_, B_, C_, D_ = controller_dss(wc[ax], wo[ax], b0[ax] * sc, sigma=sigma, gyro_lpf_hz=lpf, dt=loop_dt); Hc = freqresp(A_, B_, C_, D_, wb, dt=loop_dt)
        Gm = pt1_resp(glpf2, wb, dt=loop_dt) if glpf2 > 0 else 1.0
        okb = band[1:]
        Lmeas = -Hc[:, 0] * Gm * Hm; Tcons = Hc[:, 1] * Hm / (1 + Lmeas)
        mmeas = margins(wb[okb], Lmeas[okb])
        print(f"    with the MEASURED plant: PM {mmeas.get('PM', float('nan')):.0f} deg at {mmeas.get('wgc', float('nan'))/2/np.pi:.1f} Hz, GM {mmeas.get('GM_dB', float('nan')):.1f} dB at {mmeas.get('wpc', float('nan'))/2/np.pi:.1f} Hz; "
              f"T consistency (|T| model-from-measured-plant vs measured) at 3/8/20/40 Hz: " + ", ".join(f"{abs(Tcons[np.argmin(abs(f[1:]-fr))]):.3f}/{abs(T[np.argmin(abs(f-fr))]):.3f}" for fr in (3, 8, 20, 40)))
        # table
        w = 2 * np.pi * f
        Tp, Lp = model_T(wc[ax], wo[ax], b0[ax] * sc, b3, tau3, d3, w[1:], loop_dt, lpf, sigma, glpf2, meso=False)
        Tm, Lm = model_T(wc[ax], wo[ax], b0[ax] * sc, b3, tau3, d3, w[1:], loop_dt, lpf, sigma, glpf2, meso=True)
        print(f"    {'f Hz':>6} {'coh r>y':>7} {'coh r>u':>7} {'|H|w':>7} {'ph(H)+90':>8} | {'|T| meas':>8} {'ph T':>6} | {'|T| coded':>9} {'|T| mp':>7}")
        for fr in (2, 3, 5, 8, 12, 16, 20, 25, 30, 40, 50, 65, 80, 100, 130):
            i = np.argmin(abs(f - fr)); j = i - 1
            print(f"    {f[i]:6.1f} {Cry[i]:7.2f} {Cru[i]:7.2f} {abs(H[i])*w[i]:7.1f} {np.degrees(np.angle(H[i]))+90:8.1f} | {abs(T[i]):8.3f} {np.degrees(np.angle(T[i])):6.0f} | {abs(Tp[j]):9.3f} {abs(Tm[j]):7.3f}")
        bm = (f >= 2) & (f <= 60) & (Cry >= 0.8)
        print(f"    |T| peak 2-60 Hz: measured {np.max(abs(T[bm])):.3f} at {f[bm][np.argmax(abs(T[bm]))]:.1f} Hz; model coded {np.max(abs(Tp[bm[1:]])):.3f}; motor-pole {np.max(abs(Tm[bm[1:]])):.3f}")
        mp = margins(w[1:], Lp); mm = margins(w[1:], Lm)
        print(f"    loop margins on this plant: coded PM {mp.get('PM',float('nan')):.0f} deg GM {mp.get('GM_dB',float('nan')):.1f} dB | motor-pole PM {mm.get('PM',float('nan')):.0f} deg GM {mm.get('GM_dB',float('nan')):.1f} dB")
        rs, os_ = metrics(sim_meso(wc[ax], wo[ax], b0[ax] * sc, b3, tau3, None, sigma=sigma, lpf_hz=lpf, dt=loop_dt))
        rm, om = metrics(sim_meso(wc[ax], wo[ax], b0[ax] * sc, b3, tau3, tau3, sigma=sigma, lpf_hz=lpf, dt=loop_dt))
        print(f"    step 100 deg/s on this plant (no delay): coded rise {rs:.0f} ms / overshoot {os_:.1f} % | motor-pole rise {rm:.0f} ms / overshoot {om:.1f} %")

if __name__ == '__main__':
    analyse(os.path.expanduser('~/storage/adrc-logs/8ksal8-20261001-chirp/_decoded/US25_Chirp_fit_pump2_btfl_001.01.csv'), {0: (33.0, 49.5), 1: (57.0, 73.5), 2: (99.5, 116.0)})

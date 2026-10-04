#!/usr/bin/env python3
"""Re-check of the margin / model numbers quoted for the jmsweng 2.5" A/B (mp2, 2026-10-04).

For each axis: plant from the chirp of each flight (fitted lag+delay, and the raw measured H), controller model of
each law (plain / motor pole) -> loop margins and modelled closed-loop T (peak, -3 dB)."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_check import read_headers, load_csv
from chirp_id import etfe, fit_plant
from adrc_math_review import controller_dss, freqresp, margins
from adrc_math_review4 import controller_meso
from ab_mp2 import find_sweeps, D

LOOP_DT = 250e-6
WC, WO, B0 = 80.0, 90.0, (4616.0, 3636.0)
FILES = {0: D + '/mp2_test_flights_2.5_in/tau_0.01.csv', 22: D + '/mp2_test_flights_2.5_in/tau_22.01.csv'}

def ctrl(law_tau_ms, b0, w):
    if law_tau_ms: A, B, C, Dm = controller_meso(WC, WO, b0, 1000.0 / law_tau_ms, sigma=0.3, gyro_lpf_hz=150.0, dt=LOOP_DT)
    else:          A, B, C, Dm = controller_dss(WC, WO, b0, sigma=0.3, gyro_lpf_hz=150.0, dt=LOOP_DT)
    H = freqresp(A, B, C, Dm, w, dt=LOOP_DT); return H[:, 0], H[:, 1]

def plant_fit(b, tau, d, w): return b * np.exp(-1j * w * d) / (1j * w * (1 + 1j * w * tau))

def bw_peak(f, T, fmax=60):
    m = (f >= 1.5) & (f <= fmax); ip = np.argmax(np.abs(T[m])); fp = f[m][ip]
    below = np.where((f > fp) & (np.abs(T) < 0.707))[0]
    return abs(T[m][ip]), fp, (f[below[0]] if len(below) else np.nan)

meas = {}
for tau_flown, path in FILES.items():
    h = read_headers(path.replace('.csv', '.headers.csv'))
    assert float(h['looptime']) * float(h['pid_process_denom']) * 1e-6 == LOOP_DT
    assert h['adrcWC'].startswith('80,80') and h['adrcWO'].startswith('90,90') and h['adrcB0'].startswith('4616,3636'), (h['adrcWC'], h['adrcWO'], h['adrcB0'])
    assert float(h['adrc_motor_tau_ms']) == tau_flown and float(h['adrc_sigma_decay']) == 3 and float(h['adrc_gyro_lpf_hz']) == 150
    cols = ['time (us)'] + [f'axis{k}[{a}]' for a in range(2) for k in 'PIDF'] + [f'setpoint[{a}]' for a in range(3)] + [f'gyroADC[{a}]' for a in range(2)]
    d = load_csv(path, cols); t = d['time (us)'] * 1e-6; t -= t[0]; dt = np.median(np.diff(t)); fs = 1 / dt
    sw = find_sweeps(t, [d[f'setpoint[{a}]'] for a in range(3)], dt, 20.0)
    for ax in (0, 1):
        a, b = sw[ax][0]; m = (t >= a) & (t <= b)
        r = d[f'setpoint[{ax}]'][m]; y = d[f'gyroADC[{ax}]'][m]; u = np.clip(sum(d[f'axis{k}[{ax}]'] for k in 'PIDF')[m], -500, 500)
        f, H, T, Cry, Cru = etfe(r - r.mean(), u - u.mean(), y - y.mean(), fs, nper=2048)
        (b3, tau3, d3), e3 = fit_plant(f, H, Cry, fmax=100.0)['lag_delay']
        meas[(ax, tau_flown)] = dict(f=f, H=H, T=T, C=Cry, fit=(b3, tau3, d3, e3))

for ax, name in ((0, 'roll'), (1, 'pitch')):
    print(f"\n===== {name}, b0 {B0[ax]:.0f}")
    for tau_flown in (0, 22):
        b3, tau3, d3, e3 = meas[(ax, tau_flown)]['fit']
        print(f"  plant from the tau={tau_flown} flight: b_acc {b3:.1f}, tau {tau3*1e3:.1f} ms, delay {d3*1e3:.1f} ms, fit err {e3:.3f}, b_acc/tau {b3/tau3:.0f} = {b3/tau3/B0[ax]:.2f} x b0")
    for law in (0, 22):
        print(f"  --- law tau = {law}")
        for tau_flown in (0, 22):
            M = meas[(ax, tau_flown)]; b3, tau3, d3, e3 = M['fit']
            # (a) fitted plant on a dense grid
            w = 2 * np.pi * np.logspace(np.log10(0.5), np.log10(150), 6000); Hy, Hr = ctrl(law, B0[ax], w); P = plant_fit(b3, tau3, d3, w)
            L = -Hy * P; mg = margins(w, L); Tm = Hr * P / (1 + L); pk, fp, bw = bw_peak(w / 2 / np.pi, Tm)
            # (b) raw measured H over the coherent band
            f = M['f']; ok = (f >= 1.5) & (f <= 100) & (M['C'] >= 0.8); wf = 2 * np.pi * f[ok]; Hy2, Hr2 = ctrl(law, B0[ax], wf)
            L2 = -Hy2 * M['H'][ok]; mg2 = margins(wf, L2)
            print(f"      plant[{tau_flown:2d}] fitted: PM {mg.get('PM', np.nan):5.1f} deg at {mg.get('wgc', np.nan)/2/np.pi:4.1f} Hz, GM {mg.get('GM_dB', np.nan):4.1f} dB at {mg.get('wpc', np.nan)/2/np.pi:4.1f} Hz | model T peak {pk:.3f} at {fp:4.1f} Hz, -3 dB {bw:5.1f} Hz"
                  f" || raw H: PM {mg2.get('PM', np.nan):5.1f} at {mg2.get('wgc', np.nan)/2/np.pi:4.1f} Hz, GM {mg2.get('GM_dB', np.nan):4.1f} dB at {mg2.get('wpc', np.nan)/2/np.pi:4.1f} Hz (coherent band to {f[ok].max():.0f} Hz, {ok.sum()} pts)")
        M = meas[(ax, law)]; ok = (M['f'] >= 1.5) & (M['f'] <= 60) & (M['C'] >= 0.8); pk, fp, bw = bw_peak(M['f'], np.where(ok, M['T'], 0))
        print(f"      measured T in the flight that flew this law: peak {pk:.3f} at {fp:.1f} Hz")
    # full measured T curves side by side
    f = meas[(ax, 0)]['f']; sel = (f >= 1) & (f <= 40)
    print("  f Hz    : " + " ".join(f"{x:5.1f}" for x in f[sel]))
    for tf in (0, 22):
        print(f"  |T| t={tf:2d}: " + " ".join(f"{abs(x):5.2f}" for x in meas[(ax, tf)]['T'][sel]))
        print(f"  coh t={tf:2d}: " + " ".join(f"{x:5.2f}" for x in meas[(ax, tf)]['C'][sel]))

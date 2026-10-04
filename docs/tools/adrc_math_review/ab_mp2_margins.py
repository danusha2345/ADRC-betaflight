#!/usr/bin/env python3
"""Loop margins and modelled closed-loop T for both laws on the plants measured in jmsweng's A/B flights
(mp2, 2026-10-04; 2.5" tau 0 / 22 and 5" tau 0 / 23).

For each axis: plant from the chirp of each flight (fitted lag+delay, and the raw measured H over the coherent
band below 0.9 x the frequency the sweep reached), controller model of each law (plain / motor pole) -> margins,
modelled T peak and -3 dB. Chirp windows come from the flight-mode flags (ab_mp2.chirp_windows).

The controller is modelled with the b0 the firmware actually used: base b0 x the throttle schedule, which is logged
(debug[7] / 100 with debug_mode = ADRC); its median over the chirp the plant came from is applied."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_check import read_headers, load_csv
from chirp_id import etfe, fit_plant
from adrc_math_review import controller_dss, freqresp, margins
from adrc_math_review4 import controller_meso
from ab_mp2 import chirp_windows, D

LOOP_DT = 250e-6
CRAFT = {'2.5 inch': {0: D + '/mp2_test_flights_2.5_in/tau_0.01.csv', 22: D + '/mp2_test_flights_2.5_in/tau_22.01.csv'},
         '5 inch':   {0: D + '/mp2_test_flights_5_in/tau_0.01.csv',   23: D + '/mp2_test_flights_5_in/tau_23.01.csv'}}

def ctrl(law_tau_ms, wc, wo, b0, w):
    if law_tau_ms: A, B, C, Dm = controller_meso(wc, wo, b0, 1000.0 / law_tau_ms, sigma=0.3, gyro_lpf_hz=150.0, dt=LOOP_DT)
    else:          A, B, C, Dm = controller_dss(wc, wo, b0, sigma=0.3, gyro_lpf_hz=150.0, dt=LOOP_DT)
    H = freqresp(A, B, C, Dm, w, dt=LOOP_DT); return H[:, 0], H[:, 1]

def plant_fit(b, tau, d, w): return b * np.exp(-1j * w * d) / (1j * w * (1 + 1j * w * tau))

def bw_peak(f, T, fmax=60):
    m = (f >= 1.5) & (f <= fmax); ip = np.argmax(np.abs(T[m])); fp = f[m][ip]
    below = np.where((f > fp) & (np.abs(T) < 0.707) & (f <= fmax))[0]
    return abs(T[m][ip]), fp, (f[below[0]] if len(below) else np.nan)

def measure(files):
    meas = {}; tune = None
    for tau_flown, path in files.items():
        h = read_headers(path.replace('.csv', '.headers.csv'))
        assert float(h['looptime']) * float(h['pid_process_denom']) * 1e-6 == LOOP_DT
        assert float(h['adrc_motor_tau_ms']) == tau_flown and float(h['adrc_sigma_decay']) == 3 and float(h['adrc_gyro_lpf_hz']) == 150
        this = tuple(tuple(float(v) for v in h[k].split(',')) for k in ('adrcWC', 'adrcWO', 'adrcB0')); assert tune in (None, this); tune = this
        cols = ['time (us)'] + [f'axis{k}[{a}]' for a in range(2) for k in 'PIDF'] + [f'setpoint[{a}]' for a in range(3)] + [f'gyroADC[{a}]' for a in range(2)] + ['debug[7]']
        d = load_csv(path, cols); t = d['time (us)'] * 1e-6; t -= t[0]; fs = 1 / np.median(np.diff(t))
        sw = chirp_windows(path, t, [d[f'setpoint[{a}]'] for a in range(3)], h)
        for ax in (0, 1):
            a, b, fend = sw[ax][0]; m = (t >= a) & (t <= b)
            r = d[f'setpoint[{ax}]'][m]; y = d[f'gyroADC[{ax}]'][m]; u = np.clip(sum(d[f'axis{k}[{ax}]'] for k in 'PIDF')[m], -500, 500)
            f, H, T, Cry, Cru = etfe(r - r.mean(), u - u.mean(), y - y.mean(), fs, nper=2048)
            (b3, tau3, d3), e3 = fit_plant(f, H, Cry, fmax=min(100.0, 0.9 * fend))['lag_delay']
            meas[(ax, tau_flown)] = dict(f=f, H=H, T=T, C=Cry, fit=(b3, tau3, d3, e3), fend=fend, scale=float(np.median(d['debug[7]'][m])) / 100)
    return meas, tune

if __name__ == '__main__':
    for craft, files in CRAFT.items():
        meas, (WC, WO, B0) = measure(files); laws = sorted(files)
        for ax, name in ((0, 'roll'), (1, 'pitch')):
            print(f"\n===== {craft}, {name}: wc {WC[ax]:.0f}, wo {WO[ax]:.0f}, b0 {B0[ax]:.0f}")
            for tf in laws:
                b3, tau3, d3, e3 = meas[(ax, tf)]['fit']
                print(f"  plant from the tau={tf} flight (sweep to {meas[(ax, tf)]['fend']:.0f} Hz): b_acc {b3:.1f}, tau {tau3*1e3:.1f} ms, delay {d3*1e3:.1f} ms, fit err {e3:.3f}, b_acc/tau {b3/tau3:.0f} = {b3/tau3/B0[ax]:.2f} x base b0; b0 schedule x{meas[(ax, tf)]['scale']:.2f} there -> {b3/tau3/B0[ax]/meas[(ax, tf)]['scale']:.2f} x the b0 in use")
            for law in laws:
                print(f"  --- law tau = {law}")
                for tf in laws:
                    M = meas[(ax, tf)]; b3, tau3, d3, e3 = M['fit']; b0 = B0[ax] * M['scale']
                    w = 2 * np.pi * np.logspace(np.log10(0.5), np.log10(150), 6000); P = plant_fit(b3, tau3, d3, w)
                    Hy, Hr = ctrl(law, WC[ax], WO[ax], b0, w); L = -Hy * P; mg = margins(w, L); pk, fp, bw = bw_peak(w / 2 / np.pi, Hr * P / (1 + L))
                    Hyb, _ = ctrl(law, WC[ax], WO[ax], b0 * 1.25, w); mb = margins(w, -Hyb * P)
                    f = M['f']; ok = (f >= 1.5) & (f <= min(100.0, 0.9 * M['fend'])) & (M['C'] >= 0.8); wf = 2 * np.pi * f[ok]
                    Hy2, _ = ctrl(law, WC[ax], WO[ax], b0, wf); m2 = margins(wf, -Hy2 * M['H'][ok])
                    print(f"      plant[{tf:2d}] fitted: PM {mg.get('PM', np.nan):5.1f} deg at {mg.get('wgc', np.nan)/2/np.pi:4.1f} Hz, GM {mg.get('GM_dB', np.nan):4.1f} dB at {mg.get('wpc', np.nan)/2/np.pi:4.1f} Hz"
                          f" (b0 x1.25: PM {mb.get('PM', np.nan):5.1f}, GM {mb.get('GM_dB', np.nan):4.1f}) | model T peak {pk:.3f} at {fp:4.1f} Hz, -3 dB {bw:5.1f} Hz"
                          f" || raw H: PM {m2.get('PM', np.nan):5.1f} at {m2.get('wgc', np.nan)/2/np.pi:4.1f} Hz, GM {m2.get('GM_dB', np.nan):4.1f} dB at {m2.get('wpc', np.nan)/2/np.pi:4.1f} Hz (band to {f[ok].max():.0f} Hz, {ok.sum()} pts)")
                M = meas[(ax, law)]; fmax = min(60.0, 0.9 * M['fend']); ok = (M['f'] >= 1.5) & (M['f'] <= fmax) & (M['C'] >= 0.8); pk, fp, bw = bw_peak(M['f'], np.where(ok, M['T'], 0), fmax)
                above = np.where((M['f'] > fp) & (np.abs(M['T']) < 0.707) & (M['f'] <= fmax))[0]
                print(f"      measured T in the flight that flew this law (valid to {fmax:.0f} Hz): peak {pk:.3f} at {fp:.1f} Hz, -3 dB {M['f'][above[0]] if len(above) else float('nan'):.1f} Hz")
            f = meas[(ax, laws[0])]['f']; sel = (f >= 1) & (f <= 30)
            print("  f Hz    : " + " ".join(f"{x:5.1f}" for x in f[sel]))
            for tf in laws:
                print(f"  |T| t={tf:2d}: " + " ".join(f"{abs(x):5.2f}" for x in meas[(ax, tf)]['T'][sel]))
                print(f"  coh t={tf:2d}: " + " ".join(f"{x:5.2f}" for x in meas[(ax, tf)]['C'][sel]))

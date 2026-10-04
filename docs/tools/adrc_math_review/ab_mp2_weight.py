#!/usr/bin/env python3
"""Timeline of jmsweng's suspended-weight flight (5", mp2, tau 23, 2026-10-04): what ended it.

Per-second motor command / eRPM / I term / rates, a 20 ms view of the moment motor[1] stops answering, and the
yaw-authority picture before it."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_check import read_headers, load_csv
from ab_mp2 import D

p = D + '/mp2_test_flights_5_in/suspended_weight.01.csv'; h = read_headers(p.replace('.csv', '.headers.csv'))
cols = ['time (us)', 'setpoint[3]', 'amperageLatest (A)', 'vbatLatest (V)'] + [f'motor[{i}]' for i in range(4)] + [f'eRPM[{i}]' for i in range(4)] \
     + [f'gyroADC[{a}]' for a in range(3)] + [f'setpoint[{a}]' for a in range(3)] + [f'axisI[{a}]' for a in range(3)] + [f'accSmooth[{i}]' for i in range(3)]
d = load_csv(p, cols); t = d['time (us)'] * 1e-6; t -= t[0]; dt = np.median(np.diff(t))
acc = np.sqrt(sum(d[f'accSmooth[{i}]'] ** 2 for i in range(3))) / float(h.get('acc_1G', 2048))
mot = np.c_[[d[f'motor[{i}]'] for i in range(4)]].T; erpm = np.c_[[d[f'eRPM[{i}]'] for i in range(4)]].T
gyro = np.c_[[d[f'gyroADC[{a}]'] for a in range(3)]].T; sp = np.c_[[d[f'setpoint[{a}]'] for a in range(3)]].T; I = np.c_[[d[f'axisI[{a}]'] for a in range(3)]].T

def rows(t0, t1, step):
    print("   t    | thr | motor cmd x4        | eRPM x4             | I r/p/y mean   | |gyro| max r/p/y | |sp| max r/p/y | acc g | amps")
    for s in np.arange(t0, t1, step):
        m = (t >= s) & (t < s + step)
        if not m.any(): continue
        print(f"{s:7.2f} | {d['setpoint[3]'][m].mean()/10:3.0f} | " + " ".join(f"{x:4.0f}" for x in mot[m].mean(axis=0)) + " | " + " ".join(f"{x:4.0f}" for x in erpm[m].mean(axis=0))
              + " | " + "/".join(f"{x:4.0f}" for x in I[m].mean(axis=0)) + " | " + "/".join(f"{x:4.0f}" for x in np.abs(gyro[m]).max(axis=0))
              + " | " + "/".join(f"{x:3.0f}" for x in np.abs(sp[m]).max(axis=0)) + f" | {acc[m].max():4.1f} | {d['amperageLatest (A)'][m].mean():4.1f}")

print(f"adrc_motor_tau_ms {h.get('adrc_motor_tau_ms')}, wc/wo/b0 {h.get('adrcWC')} / {h.get('adrcWO')} / {h.get('adrcB0')}, motorOutput {h.get('motorOutput')}, {t[-1]:.1f} s\n")
rows(0, t[-1], 1.0)
print("\n20 ms view of the stop:"); rows(14.80, 15.20, 0.02)

c1, e1 = mot[:, 1], erpm[:, 1]
after = t >= 15.2; pre = (t >= 1.5) & (t < 14.9); yawp = (t >= 7.0) & (t < 13.0); three = (t >= 15.0) & (t < 16.5)
hit = np.argmax(acc > 8)
print(f"\nmotor[1] after 15.2 s: command median {np.median(c1[after]):.0f}, eRPM median {np.median(e1[after]):.0f}; the other three (to 16.5 s): eRPM median "
      + "/".join(f"{np.median(erpm[after & (t < 16.5), i]):.0f}" for i in (0, 2, 3)))
print(f"current peak at the stall: {d['amperageLatest (A)'][(t >= 14.9) & (t < 15.1)].max():.0f} A at t = {t[(t >= 14.9) & (t < 15.1)][np.argmax(d['amperageLatest (A)'][(t >= 14.9) & (t < 15.1)])]:.2f} s")
print(f"first acc > 8 g: t = {t[hit]:.2f} s; rates on three motors (15.0-16.5 s): |gyro| max r/p/y " + "/".join(f"{x:.0f}" for x in np.abs(gyro[three]).max(axis=0)))
print(f"rates after the first impact: |gyro| max r/p/y " + "/".join(f"{x:.0f}" for x in np.abs(gyro[t >= t[hit] - 0.05]).max(axis=0)))
print(f"before the stop (1.5-14.9 s): a motor at max {100*np.mean(mot[pre].max(axis=1) >= 2040):.1f} % of the time")
print(f"7-13 s: motor mean " + "/".join(f"{x:.0f}" for x in mot[yawp].mean(axis=0)) + f"; a motor at idle {100*np.mean(mot[yawp].min(axis=1) <= 165):.0f} % of the time; yaw I at its {h.get('pidsum_limit_yaw')} bound for {np.sum(np.abs(I[yawp, 2]) >= 399)*dt:.2f} s;"
      f" |yaw rate| max {np.abs(gyro[yawp, 2]).max():.0f} with |yaw setpoint| max {np.abs(sp[yawp, 2]).max():.0f}")

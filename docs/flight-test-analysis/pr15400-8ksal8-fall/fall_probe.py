#!/usr/bin/env python3
"""Everything quoted in ANALYSIS.md for 8ksal8's 2026-08-03 fall log.

Usage: python3 fall_probe.py truncated_log.01.csv [arm_beep_seconds]

The arm-beep time comes from the decoder's .event sidecar ("Sync beep") and is the
zero point every timing figure in ANALYSIS.md is measured from.
"""

import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

path = sys.argv[1] if len(sys.argv) > 1 else "truncated_log.01.csv"
ARM_BEEP = float(sys.argv[2]) if len(sys.argv) > 2 else 30.650492

with open(path) as f:
    names = [c.strip() for c in f.readline().split(",")]
flagcols = [i for i, n in enumerate(names) if "(flags)" in n]
numcols = [i for i, n in enumerate(names) if i not in flagcols]
num = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=numcols, invalid_raise=False)
flags = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=flagcols, dtype=str,
                      invalid_raise=False, autostrip=True)
cols = {names[c]: k for k, c in enumerate(numcols)}
C = lambda n: num[:, cols[n]]

t = C("time (us)") / 1e6
tr = t - t[0]
motors = np.column_stack([C(f"motor[{i}]") for i in range(4)])
erpm = np.column_stack([C(f"eRPM[{i}]") for i in range(4)])
gyro = np.column_stack([C(f"gyroADC[{i}]") for i in range(3)])
sp = np.column_stack([C(f"setpoint[{i}]") for i in range(3)])
I = np.column_stack([C(f"axisI[{i}]") for i in range(3)])
vbat, amp, thr, d7 = C("vbatLatest (V)"), C("amperageLatest (A)"), C("rcCommand[3]"), C("debug[7]")

print("== 1. where the log stops ==")
print(f"{len(t)} samples, {tr[-1]:.3f} s of logging, log clock {t[0]:.3f}..{t[-1]:.3f} s")
print(f"arm beep at {ARM_BEEP:.3f} s -> last sample is {t[-1]-ARM_BEEP:.3f} s after the beep")
print(f"failsafePhase values seen: {sorted(set(flags[:, 2]))}")
print(f"rxSignalReceived low samples: {int((C('rxSignalReceived') < 1).sum())}, "
      f"rxFlightChannelsValid low: {int((C('rxFlightChannelsValid') < 1).sum())}")

print("\n== 2. loop timing right up to the cut ==")
dt = np.diff(t) * 1000
print(f"whole log: median {np.median(dt):.3f} ms, p99 {np.percentile(dt,99):.3f}, max {dt.max():.2f}"
      f" (at {tr[np.argmax(dt)]:.3f} s), samples > 1 ms: {int((dt>1).sum())}")
k = tr[:-1] > tr[-1] - 5.0
print(f"last 5 s:  median {np.median(dt[k]):.3f} ms, p99 {np.percentile(dt[k],99):.3f}, "
      f"max {dt[k].max():.3f}")

print("\n== 3. state in the last second ==")
k = tr > tr[-1] - 1.0
print(f"throttle {thr[k].min():.0f}..{thr[k].max():.0f}, vbat {vbat[k].min():.2f}..{vbat[k].max():.2f} V, "
      f"current {amp[k].mean():.1f} A mean (flight max {amp.max():.1f} A)")
print(f"motor commands {motors[k].min():.0f}..{motors[k].max():.0f}, "
      f"eRPM {erpm[k].min():.0f}..{erpm[k].max():.0f}")
print(f"|gyro-setpoint| max r/p/y {np.abs(gyro[k]-sp[k]).max(axis=0)}")
print(f"|I| max r/p/y {np.abs(I[k]).max(axis=0)} (limits 500/500/400); "
      f"whole log {np.abs(I).max(axis=0)}")
print(f"b0 throttle scale {d7[k].min()/100:.2f}..{d7[k].max()/100:.2f}, "
      f"liftoff latch negative (gated) samples in last second: {int((d7[k]<0).sum())}")
print(f"rail (>=2040) samples in last second: {int((motors[k]>=2040).sum())}")

print("\n== 4. motor-path health over the whole flight ==")
print(f"eRPM <= 0 duty per motor: {[f'{100*np.mean(erpm[:,i]<=0):.2f}%' for i in range(4)]}")
fitm = (motors.min(axis=1) > 300) & (motors.max(axis=1) < 2040)
mdl = np.zeros_like(erpm)
for i in range(4):
    a, b = np.polyfit(motors[fitm, i], erpm[fitm, i], 1)
    mdl[:, i] = a * motors[:, i] + b
    print(f"  motor{i}: eRPM = {a:.3f}·cmd {b:+.0f}")
W = 60  # 30 ms of trailing command history
hits = 0
print("  desync screen (command >= 900, steady within 60 over 30 ms, eRPM < 70 % of model, >= 5 ms):")
for i in range(4):
    c = motors[:, i]
    steady = np.zeros(len(c), bool)
    sw = sliding_window_view(c, W)
    steady[W - 1:] = (sw.max(axis=1) - sw.min(axis=1)) < 60
    idx = np.where(steady & (c >= 900) & (erpm[:, i] < 0.70 * mdl[:, i]))[0]
    for s in np.split(idx, np.where(np.diff(idx) > 3)[0] + 1) if len(idx) else []:
        if (t[s[-1]] - t[s[0]]) * 1000 >= 5:
            hits += 1
            print(f"    motor{i} at {tr[s[0]]:.3f} s")
print(f"    hits: {hits}")
print("  median eRPM/command in 5 s bins (steady band 800-1600):")
edges = np.arange(0, tr[-1] + 5.0, 5.0)
for a, b in zip(edges[:-1], edges[1:]):
    k = (tr >= a) & (tr < b)
    row = []
    for i in range(4):
        kk = k & (motors[:, i] > 800) & (motors[:, i] < 1600) & (erpm[:, i] > 200)
        row.append(np.median(erpm[kk, i] / motors[kk, i]) if kk.sum() > 50 else np.nan)
    print(f"    {b:5.0f} s  " + "  ".join(f"{v:.3f}" for v in row))

print("\n== 5. last 300 ms, every 10 ms ==")
k = np.where(tr > tr[-1] - 0.30)[0][::20]
print(f"{'t':>8s} {'thr':>5s} {'vbat':>6s} {'amp':>5s} "
      f"{'m0':>5s} {'m1':>5s} {'m2':>5s} {'m3':>5s} {'gr':>5s} {'gp':>5s} {'gy':>5s}")
for i in k:
    print(f"{tr[i]:8.4f} {thr[i]:5.0f} {vbat[i]:6.2f} {amp[i]:5.1f} "
          + " ".join(f"{motors[i,j]:5.0f}" for j in range(4)) + " "
          + " ".join(f"{gyro[i,j]:5.0f}" for j in range(3)))

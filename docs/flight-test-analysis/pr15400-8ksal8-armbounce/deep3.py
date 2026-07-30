#!/usr/bin/env python3
"""Session 3 deep dive: why is the gate open at a quiet arm, where does the
z3 windup go, what happens at throttle-up."""
import csv
import numpy as np

MIN_OUT, MAX_OUT = 198, 2047
COLS = ["time (us)", "rcCommand[3]",
        "setpoint[0]", "setpoint[1]", "setpoint[2]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[2]", "debug[5]", "debug[6]", "debug[7]"]

def load(path):
    with open(path) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        idx = [hdr.index(c) for c in COLS]
        rows = []
        for line in r:
            try:
                rows.append([float(line[i]) for i in idx])
            except (ValueError, IndexError):
                pass
    a = np.array(rows)
    return {c: a[:, j] for j, c in enumerate(COLS)}

for sess in ("01", "02", "03"):
    d = load(f"Airmode_Arm_Angle_Air_btfl_all.{sess}.csv")
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    print(f"--- session {sess}: first 100 ms sample-level yaw/rp gyro ---")
    n = int(0.1 * fs)
    gy = np.stack([d[f"gyroUnfilt[{ax}]"][:n] for ax in range(3)])
    print(f"  max |gyro| R/P/Y over first 100 ms: {np.abs(gy[0]).max():.0f}/{np.abs(gy[1]).max():.0f}/{np.abs(gy[2]).max():.0f} dps")
    print(f"  debug7[0..5] = {d['debug[7]'][:6]}")

d = load("Airmode_Arm_Angle_Air_btfl_all.03.csv")
t = d["time (us)"] / 1e6; t -= t[0]
fs = 1 / np.median(np.diff(t))
mot = [d[f"motor[{i}]"] for i in range(4)]
coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
thr = (d["rcCommand[3]"] - 1000) / 10
print("\n--- session 3 full timeline, 1 s rows to takeoff+5s ---")
i_to = np.argmax(thr > 5)
print(f"first stick throttle >5% at t={t[i_to]:.2f}s")
print("   t   | thr%  coll% | z3R(x16)  z3P(x16)  z3Y(x16) | mot max | maxgy_rp")
W = int(1.0 * fs)
for st in range(0, min(len(t), int((t[i_to] + 5) * fs)) - W, W):
    ws = slice(st, st + W)
    print(f" {t[st]:5.1f} | {np.median(thr[ws]):5.1f} {np.median(coll[ws]):5.1f} | "
          f"{d['debug[2]'][ws].mean()*16:+9.0f} {d['debug[5]'][ws].mean()*16:+9.0f} {d['debug[6]'][ws].mean()*16:+9.0f} | "
          f"{max(m[ws].max() for m in mot):4.0f} | "
          f"{max(np.abs(d['gyroUnfilt[0]'][ws]).max(), np.abs(d['gyroUnfilt[1]'][ws]).max()):5.0f}")
# takeoff jump quantification
sl = (t >= t[i_to] - 0.2) & (t <= t[i_to] + 1.0)
print(f"\naround first throttle-up: gyro_rp max {max(np.abs(d['gyroUnfilt[0]'][sl]).max(), np.abs(d['gyroUnfilt[1]'][sl]).max()):.0f} dps, "
      f"sp_rp max {max(np.abs(d['setpoint[0]'][sl]).max(), np.abs(d['setpoint[1]'][sl]).max()):.0f} dps")

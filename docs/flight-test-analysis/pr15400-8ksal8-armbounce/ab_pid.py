#!/usr/bin/env python3
"""Classic-PID vs ADRC arm A/B (8ksal8, 2026-07-30): angle box on at arm,
bottom-mounted battery -> craft starts tilted and tries to right itself.
Log1 PID + airmode on switch (on at arm)  -> bounces
Log2 PID + airmode permanent feature      -> rights itself, controlled
Log3 ADRC + airmode permanent feature     -> bounces"""
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

FILES = [("PID + airmode SWITCH (on at arm)", "AirMode_sw_on_Angle_onPIDs.01.csv", False),
         ("PID + airmode FEATURE", "Airmode_on_Angle_onPIDs.01.csv", False),
         ("ADRC + airmode FEATURE", "Airmode_on_Angle_onADRC.01.csv", True)]

for name, path, is_adrc in FILES:
    d = load(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{i}]"] for i in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    thr = (d["rcCommand[3]"] - 1000) / 10
    gy_rp = np.maximum(np.abs(d["gyroUnfilt[0]"]), np.abs(d["gyroUnfilt[1]"]))
    sp_rp = np.maximum(np.abs(d["setpoint[0]"]), np.abs(d["setpoint[1]"]))
    sat = np.max(mot, axis=0) >= 2040
    print(f"\n=== {name} ===  ({path}, dur {t[-1]:.1f}s, fs {fs:.0f} Hz)")
    print(f"stick throttle: max {thr.max():.1f}% (0% whole log: {(thr < 1).all()})")
    n3 = min(len(t), int(5.0 * fs))
    print(f"first 5 s: gyro_rp peak {gy_rp[:n3].max():.0f} dps | sp_rp peak {sp_rp[:n3].max():.0f} dps | "
          f"collective max {coll[:n3].max():.0f}% | any-motor-sat {sat[:n3].mean()*100:.1f}% of samples")
    # settle: first time after which gyro_rp stays <20 dps for 1 s
    W = int(1.0 * fs)
    settle = None
    for st in range(0, len(t) - W):
        if gy_rp[st:st + W].max() < 20:
            settle = t[st]; break
    print(f"settle (gyro_rp <20 dps sustained 1 s): {settle if settle is None else round(settle, 2)} s")
    if is_adrc:
        gate = d["debug[7]"] > 0
        print(f"gate open: {gate.mean()*100:.0f}% of log; debug7[0]={d['debug[7]'][0]:.0f}; "
              f"z3 P/Y extremes: {d['debug[5]'].min()*16:+.0f}/{d['debug[5]'].max()*16:+.0f}, "
              f"{d['debug[6]'].min()*16:+.0f}/{d['debug[6]'].max()*16:+.0f}")
    # 0.25 s rows first 3 s
    print("   t   | sp_rp_max gy_rp_max | coll% | sat%")
    W2 = int(0.25 * fs)
    for st in range(0, min(len(t), int(3.0 * fs)) - W2, W2):
        ws = slice(st, st + W2)
        print(f" {t[st]:5.2f} | {sp_rp[ws].max():9.0f} {gy_rp[ws].max():9.0f} | {np.median(coll[ws]):5.1f} | {sat[ws].mean()*100:4.0f}")

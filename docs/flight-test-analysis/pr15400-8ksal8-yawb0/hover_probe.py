#!/usr/bin/env python3
"""Measure the actual hover collective of a log and compare it to the anchor.

adrc_hover_throttle is the anchor of the b0 throttle schedule, so what matters
for jmsweng's hover-offset hypothesis is the *offset* between that setting and
the collective the craft really hovers at - which moves with pack voltage.

Calm windows: 0.5 s, gate open, no motor rail, |setpoint| < 50 dps,
|gyro| < 120 dps, |acc| within 0.85-1.15 g (i.e. roughly level, not climbing
or descending hard). Reported per voltage bin so the sag effect is visible.
"""

import csv
import sys
from pathlib import Path

import numpy as np


def headers(path):
    hp = path.parent / (path.name[:-4] + ".headers.csv")
    out = {}
    if hp.exists():
        for row in csv.reader(hp.open()):
            if len(row) >= 2:
                out[row[0]] = row[1]
    return out


def load(path, names):
    with path.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    use = [n for n in names if n in idx]
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in use], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    return {n: arr[:, i] for i, n in enumerate(use)}


def main(path):
    path = Path(path)
    h = headers(path)
    lo, hi = (int(v) for v in h.get("motorOutput", "48,1847").split(","))
    names = (["time (us)", "debug[7]", "vbatLatest (V)"]
             + [f"motor[{i}]" for i in range(4)]
             + [f"gyroUnfilt[{i}]" for i in range(3)]
             + [f"setpoint[{i}]" for i in range(3)]
             + [f"accSmooth[{i}] (g)" for i in range(3)])
    d = load(path, names)
    t = d["time (us)"] / 1e6
    fs = 1 / np.median(np.diff(t))
    mot = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    coll = (mot.mean(axis=0) - lo) / (hi - lo) * 100
    gate = d["debug[7]"] > 0
    gyro = np.vstack([d[f"gyroUnfilt[{i}]"] for i in range(3)])
    sp = np.vstack([d[f"setpoint[{i}]"] for i in range(3)])
    acc = np.vstack([d[f"accSmooth[{i}] (g)"] for i in range(3)])
    accn = np.sqrt((acc ** 2).sum(axis=0))
    vbat = d["vbatLatest (V)"]

    win, hop = int(0.5 * fs), max(1, int(0.1 * fs))
    rows = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if not gate[sl].all() or mot[:, sl].max() >= hi:
            continue
        if np.abs(sp[:, sl]).max() >= 50 or np.abs(gyro[:, sl]).max() >= 120:
            continue
        if not (0.85 <= np.median(accn[sl]) <= 1.15):
            continue
        rows.append((np.median(coll[sl]), np.median(vbat[sl])))

    anchor = float(h.get("adrc_hover_throttle", "nan"))
    print(f"\n=== {path.name} ===  anchor adrc_hover_throttle = {anchor:.0f} %")
    if not rows:
        print("  no calm windows")
        return
    r = np.asarray(rows)
    print(f"  calm windows {len(r)} ({len(r)*0.1:.1f} s of hops): "
          f"collective med {np.median(r[:,0]):.1f} % "
          f"(p10 {np.percentile(r[:,0],10):.1f}, p90 {np.percentile(r[:,0],90):.1f}), "
          f"vbat med {np.median(r[:,1]):.2f} V")
    print(f"  offset anchor - measured = {anchor - np.median(r[:,0]):+.1f} points")
    edges = np.percentile(r[:, 1], [0, 33, 66, 100])
    for i in range(3):
        m = (r[:, 1] >= edges[i]) & (r[:, 1] <= edges[i + 1])
        if m.sum() >= 3:
            print(f"    vbat {edges[i]:.2f}-{edges[i+1]:.2f} V: "
                  f"collective med {np.median(r[m,0]):.1f} % (n={m.sum()})")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)

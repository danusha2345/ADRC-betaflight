#!/usr/bin/env python3
"""ADRC-025: punch->chop rebound on the 2026-07-15 flights, using the exact
event criteria of pr15400-b4/analyze_b4_punches.py (throttle > 40 % gate-open,
chop below 15 % within 4 s, calm-stick = max |setpoint R/P| < 60 deg/s in the
0.6 s after the chop; rebound = peak |gyro| in that 0.6 s).

Run from this directory after decoding the .bbl files.
"""
import csv as csvmod
import numpy as np

LOGS = [
    ("btfl_003_p1_throttle_punch_rebound.01.csv", "003 punch (p1)"),
    ("btfl_006_p1_chops_and_playing.01.csv", "006 chops (p1)"),
    ("btfl_010_p1_playing.01.csv", "010 playing (p1)"),
    ("btfl_009_p2_stock_tune_rolls_n_punches.01.csv", "009 punches (p2)"),
]

def load(path):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]",
            "debug[5]", "debug[7]", "setpoint[0]", "setpoint[1]"]
    d = np.genfromtxt(path, delimiter=",", skip_header=1,
                      usecols=[idx[c] for c in cols])
    return {c: d[:, k] for k, c in enumerate(cols)}

def punches(d):
    t = d["time (us)"] * 1e-6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000) / 10
    gate = np.sign(d["debug[7]"])
    n = len(t)
    ev = []
    i = 0
    while i < n - int(fs):
        if thr[i] > 40 and gate[i] > 0:
            pk = i
            while pk < n - 1 and thr[pk] >= 15:
                pk += 1
            if (t[pk] - t[i]) < 4.0 and thr[pk] < 15:
                k2 = min(n, pk + int(0.6 * fs))
                spmax = max(np.abs(d["setpoint[0]"][pk:k2]).max(),
                            np.abs(d["setpoint[1]"][pk:k2]).max())
                if spmax < 60:
                    ev.append((t[pk], thr[i:pk].max(),
                               np.abs(d["gyroADC[1]"][pk:k2]).max(),
                               np.abs(d["gyroADC[0]"][pk:k2]).max(),
                               np.abs(d["debug[5]"][pk:k2] * 16).max() / 1000))
                i = k2
                continue
            i = pk
        i += 1
    return ev

def main():
    allp1 = []
    for f, lab in LOGS:
        ev = punches(load(f))
        print(f"=== {lab}: {len(ev)} calm punch->chop events")
        for e in ev:
            print(f"  t={e[0]:6.1f}s thrmax={e[1]:3.0f}% peakP={e[2]:5.0f} "
                  f"peakR={e[3]:5.0f} z3P|{e[4]:4.0f}k|")
        if lab.endswith("(p1)"):
            allp1 += [e[2] for e in ev]
    if allp1:
        print(f"\np1 pooled: {len(allp1)} events, peakP median={np.median(allp1):.0f} "
              f"max={max(allp1):.0f} deg/s")

if __name__ == "__main__":
    main()

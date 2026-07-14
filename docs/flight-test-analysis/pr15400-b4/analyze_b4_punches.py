#!/usr/bin/env python3
"""Punch->chop rebound comparison across builds (the source of the rebound
table in ANALYSIS.md).

Event definition (same as ANALYSIS.md Methods):
  punch  = throttle > 40 % with the gate open;
  chop   = throttle falling below 15 % within < 4 s of the punch start;
  calm   = max |setpoint roll/pitch| < 60 deg/s during the 0.6 s after the chop
           (pilot not commanding rotation - only these events count);
  rebound = peak |pitch gyro| (and |roll|) in that 0.6 s window.

Run after decoding the .bbl files with blackbox_decode (see ANALYSIS.md);
adjust BASE to where the CSVs are.
"""
import csv as csvmod
import numpy as np

BASE = "/home/danik/Projects_and_coding/ADRC-betaflight/blackbox/bvandevliet/"
LOGS = [
    ("btfl_002-ACRO.01.csv", "baseline (pre-remediation, scale cap 9)"),
    ("btfl_ACRO2.01.csv", "b3 'ACRO2' (Bob's file label)"),
    ("btfl_AIR2.01.csv", "b3 'AIR2' (Bob's file label)"),
    ("b4/btfl_001.01.csv", "b4 log1"),
    ("b4/btfl_002.01.csv", "b4 log2"),
    ("b4/btfl_003.01.csv", "b4 log3"),
    ("b4/btfl_004.01.csv", "b4 log4"),
]


def load(path):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]",
            "debug[5]", "debug[7]", "setpoint[0]", "setpoint[1]"]
    data = np.genfromtxt(path, delimiter=",", skip_header=1,
                         usecols=[idx[c] for c in cols])
    return {c: data[:, k] for k, c in enumerate(cols)}


def punches(d):
    t = d["time (us)"] * 1e-6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000) / 10
    gate = np.sign(d["debug[7]"])
    n = len(t)
    events = []
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
                if spmax < 60:  # calm-stick filter
                    events.append({
                        "t": t[pk],
                        "thrmax": thr[i:pk].max(),
                        "peakP": np.abs(d["gyroADC[1]"][pk:k2]).max(),
                        "peakR": np.abs(d["gyroADC[0]"][pk:k2]).max(),
                        "z3P_k": np.abs(d["debug[5]"][pk:k2] * 16).max() / 1000,
                    })
                i = k2
                continue
            i = pk
        i += 1
    return events


groups = {}
for path, label in LOGS:
    try:
        ev = punches(load(BASE + path))
    except OSError as e:
        print(f"{label}: skipped ({e})")
        continue
    groups[label] = ev
    print(f"\n=== {label}: {len(ev)} calm punch->chop events ===")
    for e in ev:
        print(f"  t={e['t']:6.1f}s thrmax={e['thrmax']:3.0f}%  "
              f"peakP={e['peakP']:5.0f} peakR={e['peakR']:5.0f} deg/s  "
              f"z3P |{e['z3P_k']:4.0f}k|")
    if ev:
        pp = [e["peakP"] for e in ev]
        print(f"  peakP median={np.median(pp):.1f} max={max(pp):.0f} deg/s")

b4 = [e for l, ev in groups.items() if l.startswith("b4") for e in ev]
if b4:
    pp = [e["peakP"] for e in b4]
    print(f"\nb4 pooled: {len(b4)} events, peakP median={np.median(pp):.1f} "
          f"max={max(pp):.0f} deg/s, z3P max {max(e['z3P_k'] for e in b4):.0f}k")

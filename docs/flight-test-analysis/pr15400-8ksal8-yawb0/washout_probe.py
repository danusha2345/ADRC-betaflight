#!/usr/bin/env python3
"""Yaw washout episodes in the 2026-08-03 wo-160/150 pair (8ksal8 Pavo20).

Episode = contiguous run of |gyro_yaw - setpoint_yaw| (both LP 15 Hz) > 40 dps
lasting >= 30 ms, first/last 1 s excluded.  Prints onset context: setpoint and
gyro at the error peak, saturation duty inside the episode, yaw |I| max.
Usage: python3 washout_probe.py <decoded.csv> ...
"""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

COLS = ["time (us)", "setpoint[2]", "gyroUnfilt[2]", "axisI[2]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "debug[6]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]"]


def run(path):
    path = Path(path)
    hdr = {}
    for row in csv.reader((path.parent / (path.name[:-4] + ".headers.csv")).open()):
        if len(row) >= 2:
            hdr[row[0]] = row[1]
    lo, hi = (int(v) for v in hdr["motorOutput"].split(","))

    with path.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in COLS], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    d = {n: arr[:, i] for i, n in enumerate(COLS)}

    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    lp = butter(2, 15, btype="lowpass", fs=fs, output="sos")
    g = sosfiltfilt(lp, d["gyroUnfilt[2]"])
    s = sosfiltfilt(lp, d["setpoint[2]"])
    err = g - s
    motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    sat = motors.max(axis=0) >= hi
    iy = np.abs(d["axisI[2]"])

    edge = int(fs)
    mask = np.abs(err) > 40
    mask[:edge] = mask[-edge:] = False
    print(f"\n=== {path.name}  wo {hdr['adrcWO']}  dur {t[-1]:.1f} s ===")
    n = 0
    on = None
    for i in range(1, len(mask)):
        if mask[i] and not mask[i - 1]:
            on = i
        if on is not None and (not mask[i] or i == len(mask) - 1):
            if t[i] - t[on] >= 0.030:
                sl = slice(on, i)
                pk = on + int(np.argmax(np.abs(err[sl])))
                n += 1
                print(f"  @{t[on]:7.2f}s dur {(t[i]-t[on])*1000:4.0f} ms  "
                      f"peak err {err[pk]:+6.0f} dps (setp {s[pk]:+6.0f}, gyro {g[pk]:+6.0f})  "
                      f"gyro max |{np.max(np.abs(g[sl])):.0f}|  "
                      f"sat {sat[sl].mean()*100:3.0f} %  |I|max {iy[sl].max():3.0f}  "
                      f"|roll| max {np.max(np.abs(d['gyroUnfilt[0]'][sl])):4.0f}  "
                      f"|pitch| max {np.max(np.abs(d['gyroUnfilt[1]'][sl])):4.0f}  "
                      f"z3clip {np.mean(np.abs(d['debug[6]'][sl]) >= 32700)*100:3.0f} %")
            on = None
    print(f"  episodes: {n}")


for p in sys.argv[1:]:
    run(p)

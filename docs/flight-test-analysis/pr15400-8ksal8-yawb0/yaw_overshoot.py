#!/usr/bin/env python3
"""Large-signal yaw overshoot: how far the gyro runs past a held yaw command.

A "hold" is a stretch where |setpoint_yaw| stays above MIN_DPS for >= MIN_DUR and
changes by less than 15 % inside the stretch.  Overshoot = max |gyro| in the hold
(plus 100 ms of tail) divided by the mean |setpoint| of the hold.

This is a sparse post-hoc detector on free-flight logs, not a step-response test:
the qualifying-hold count depends strongly on MIN_DPS/MIN_DUR and on how the
pilot happened to fly.  Pass --sweep to print the threshold sensitivity before
reading anything into a single row.

Usage: python3 yaw_overshoot.py [--sweep] <decoded.csv> ...
"""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

MIN_DPS = 150.0
MIN_DUR = 0.15
COLS = ["time (us)", "setpoint[2]", "gyroUnfilt[2]"]


def holds(path, min_dps, min_dur):
    path = Path(path)
    with path.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in COLS], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    t = arr[:, 0] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    lp = butter(2, 30, btype="lowpass", fs=fs, output="sos")
    s = sosfiltfilt(lp, arr[:, 1])
    g = sosfiltfilt(lp, arr[:, 2])

    over = np.abs(s) > min_dps
    tail = int(0.1 * fs)
    ratios = []
    on = None
    for i in range(1, len(over)):
        if over[i] and not over[i - 1]:
            on = i
        if on is not None and (not over[i] or i == len(over) - 1):
            if t[i] - t[on] >= min_dur:
                sl = slice(on, min(i + tail, len(t)))
                base = np.abs(s[on:i]).mean()
                if (np.abs(s[on:i]).std() / base) < 0.15:
                    ratios.append(np.abs(g[sl]).max() / base)
            on = None
    return np.asarray(ratios)


def tag_of(path):
    path = Path(path)
    hdr = {}
    for row in csv.reader((path.parent / (path.name[:-4] + ".headers.csv")).open()):
        if len(row) >= 2:
            hdr[row[0]] = row[1]
    return (f"b0_yaw {hdr.get('adrcB0','?').split(',')[-1]} wo {hdr.get('adrcWO','?').split(',')[-1]}"
            f" wc {hdr.get('adrcWC','?').split(',')[-1]}")


def report(path, min_dps, min_dur):
    r = holds(path, min_dps, min_dur)
    name = Path(path).name
    if len(r):
        print(f"{name:32s} {tag_of(path):28s} holds {len(r):2d}  "
              f"overshoot med {np.median(r):.2f} p90 {np.percentile(r,90):.2f} max {r.max():.2f}")
    else:
        print(f"{name:32s} {tag_of(path):28s} no yaw holds above {min_dps:.0f} dps")


args = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--sweep" in sys.argv[1:]:
    print("threshold sensitivity: median overshoot (n qualifying holds)\n")
    grid = [(120, 0.10), (150, 0.10), (150, 0.15), (150, 0.20), (200, 0.15), (250, 0.15)]
    print(f"{'log':32s}" + "".join(f"{f'>{d:.0f}/{u*1000:.0f}ms':>16s}" for d, u in grid))
    for p in args:
        cells = []
        for d, u in grid:
            r = holds(p, d, u)
            cells.append(f"{np.median(r):.2f} (n={len(r)})" if len(r) else "-")
        print(f"{Path(p).name:32s}" + "".join(f"{c:>16s}" for c in cells))
else:
    for p in args:
        report(p, MIN_DPS, MIN_DUR)

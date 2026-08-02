#!/usr/bin/env python3
"""Closed-gate (grounded) margin probe for the Getting_close sessions."""
import csv, sys
import numpy as np
from pathlib import Path

COLS = ["time (us)", "rcCommand[3]", "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "debug[7]", "motor[0]", "motor[1]", "motor[2]", "motor[3]"]

for p in sys.argv[1:]:
    p = Path(p)
    with p.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    arr = np.genfromtxt(p, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in COLS], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    t = (arr[:, 0] - arr[0, 0]) / 1e6
    thr = arr[:, 1]
    gyro = arr[:, 2:5]
    gate = arr[:, 5] > 0
    fs = 1.0 / np.median(np.diff(t))
    n_closed = (~gate).sum()
    if n_closed == 0:
        print(f"{p.name}: gate open from first sample (in-air log start), no grounded segment")
        continue
    # contiguity: transitions
    trans = np.flatnonzero(np.diff(gate.astype(int)))
    segs = f"{len(trans)} transition(s) at t={[round(t[i],2) for i in trans[:6]]}"
    closed = ~gate
    gmax = np.abs(gyro[closed]).max(axis=0)
    # sustained-above-20dps runs on any axis while closed
    over = (np.abs(gyro).max(axis=1) > 20) & closed
    runs = []
    if over.any():
        d = np.flatnonzero(np.diff(np.concatenate(([0], over.view(np.int8), [0]))))
        for a, b in zip(d[::2], d[1::2]):
            runs.append((t[a], (b - a) / fs * 1000))
    longest = max((ms for _, ms in runs), default=0.0)
    thr_at_open = thr[np.flatnonzero(gate)[0]] if gate.any() else float('nan')
    print(f"{p.name}: closed {n_closed/fs:.1f}s ({100*n_closed/len(t):.0f}%), {segs}")
    print(f"   grounded |gyro| max r/p/y = {gmax[0]:.0f}/{gmax[1]:.0f}/{gmax[2]:.0f} dps; "
          f">20dps runs: {len(runs)}, longest {longest:.1f} ms (hold=25ms); rcThrottle at open = {thr_at_open:.0f}")

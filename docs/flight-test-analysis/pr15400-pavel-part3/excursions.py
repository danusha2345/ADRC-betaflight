#!/usr/bin/env python3
"""Uncommanded high-rate events in the part-3 logs, with onset context.

A per-axis *interval* is |gyro| > 200 dps sustained >= 100 ms on an axis while
|setpoint| < 30 dps on that same axis (first and last 1.0 s of the log
excluded). Intervals overlapping in time across axes are merged into one
*event*; note this only merges overlaps — an oscillatory departure with short
sub-threshold gaps can still appear as several events. The reported angle is
the integrated body-axis angle |∫gyro dt| on the dominant qualifying axis
(net body-frame rotation during the event, not an attitude reconstruction).
The detector cannot tell a tune departure from a crash impact — crash logs
must be flagged by the caller.

For each event an onset-context line reports motor saturation duty (any
motor at the true upper rail, `motorOutput` high value from the headers
file) over the 100 ms and 300 ms before onset and during the event, and the
per-axis |I| maxima just before (100 ms) and during — the numbers behind the
"complete loss of motor authority" discussion in ANALYSIS.md §3.
"""
import csv
import sys
from pathlib import Path

import numpy as np

THRESH_DPS = 200.0
CMD_QUIET_DPS = 30.0
MIN_DUR_S = 0.10
EDGE_S = 1.0

for pth in sys.argv[1:]:
    p = Path(pth)
    with p.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    cols = (["time (us)"] + [f"setpoint[{i}]" for i in range(3)]
            + [f"gyroUnfilt[{i}]" for i in range(3)]
            + [f"motor[{i}]" for i in range(4)] + [f"axisI[{i}]" for i in range(3)])
    arr = np.genfromtxt(p, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in cols], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    t = (arr[:, 0] - arr[0, 0]) / 1e6
    fs = 1.0 / np.median(np.diff(t))
    sp = arr[:, 1:4]
    gy = arr[:, 4:7]
    mot = arr[:, 7:11]
    axI = arr[:, 11:14]

    hp = p.parent / (p.name[:-4] + ".headers.csv")
    hi = None
    for row in csv.reader(hp.open()):
        if len(row) >= 2 and row[0] == "motorOutput":
            hi = int(row[1].split(",")[1])
    sat = (mot >= hi).any(axis=1)

    edge = (t > EDGE_S) & (t < t[-1] - EDGE_S)
    intervals = []  # (start_idx, end_idx, axis)
    for ax in range(3):
        m = (np.abs(gy[:, ax]) > THRESH_DPS) & (np.abs(sp[:, ax]) < CMD_QUIET_DPS) & edge
        d = np.flatnonzero(np.diff(np.concatenate(([0], m.view(np.int8), [0]))))
        for a, b in zip(d[::2], d[1::2]):
            if (b - a) / fs >= MIN_DUR_S:
                intervals.append((a, b, ax))

    # merge time-overlapping per-axis intervals into events
    intervals.sort()
    events = []
    for a, b, ax in intervals:
        if events and a <= events[-1][1]:
            ev = events[-1]
            events[-1] = (ev[0], max(ev[1], b), ev[2] | {ax})
        else:
            events.append((a, b, {ax}))

    descr = []
    for a, b, axes in events:
        ang = {ax: abs(float(np.trapezoid(gy[a:b, ax], t[a:b]))) for ax in axes}
        dom = max(ang, key=ang.get)
        peak = float(np.abs(gy[a:b, dom]).max())
        descr.append((a, b, "RPY"[dom], peak, ang[dom]))
    descr.sort(key=lambda x: -x[4])
    tops = "; ".join(f"{axn}@{t[a]:.2f}s {pk:.0f}dps {(b - a) / fs * 1000:.0f}ms ang≈{an:.0f}deg"
                     for a, b, axn, pk, an in descr[:4])
    print(f"{p.name}: events {len(events)} (per-axis intervals {len(intervals)})"
          + (f" | top by angle: {tops}" if tops else ""))
    for a, b, axn, pk, an in descr:
        pre1 = (t >= t[a] - 0.100) & (t < t[a])
        pre3 = (t >= t[a] - 0.300) & (t < t[a])
        dur = slice(a, b)
        Ipre = np.abs(axI[pre1]).max(axis=0).round(0) if pre1.any() else "n/a"
        Idur = np.abs(axI[dur]).max(axis=0).round(0)
        print(f"    onset {t[a]:.3f}s ({axn}): sat[-100ms] {sat[pre1].mean() * 100:.0f} %, "
              f"sat[-300ms] {sat[pre3].mean() * 100:.1f} %, sat[during] {sat[dur].mean() * 100:.0f} %; "
              f"|I|max pre {Ipre} during {Idur}")

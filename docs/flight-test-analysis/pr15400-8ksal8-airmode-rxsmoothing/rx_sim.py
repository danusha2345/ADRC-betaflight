#!/usr/bin/env python3
"""Replay Betaflight's shouldUpdateSmoothing() (src/main/fc/rc.c, 2026.6.1 / master) on the
RC frame intervals recorded by debug_mode = RX_TIMING (debug[0] = interval / 10 us,
debug[1] = frame timestamp / 100 us).  Usage: rx_sim.py <decoded .01.csv> [...]
Prints the packet pattern and how many times the RC-smoothing cutoffs would be (re)set
from three starting rate estimates. Zero means the smoothing filters never get a gain."""
import csv
import re
import sys
import numpy as np


def intervals(path):
    with open(path) as fh:
        rd = csv.reader(fh)
        hdr = [c.strip().split(" ")[0] for c in next(rd)]
        rows = [r for r in rd if len(r) == len(hdr)]
    d0 = np.array([r[hdr.index("debug[0]")] for r in rows], float) * 10
    d1 = np.array([r[hdr.index("debug[1]")] for r in rows], float)
    new = np.r_[True, np.diff(d1) != 0]
    iv = d0[new]
    return iv[iv > 0]


def simulate(iv, smoothed):
    valid = outl = 0
    prev = 0
    hits = []
    for i, us in enumerate(iv):
        if not 800 <= us <= 65500:
            valid = outl = 0
            continue
        rate = 1e6 / us
        delta = rate - smoothed
        if abs(delta) > smoothed * 0.2:
            sign = -1 if delta < 0 else 1
            if outl == 0:
                prev, outl = sign, 1
            elif sign != prev:
                outl, prev = 0, sign
            else:
                outl += 1
            valid = 0
        else:
            smoothed += 0.1 * (rate - smoothed)
            valid += 1
            outl = 0
        if valid >= 3:
            valid = 0
            hits.append(i)
        if outl >= 3:
            smoothed, outl = rate, 0
    return hits, smoothed


for path in sys.argv[1:]:
    iv = intervals(path)
    s = "".join("S" if x < 3000 else "L" for x in iv)
    runs = {k: len(re.findall(f"(?<!{k}){k}{{3,}}(?!{k})", s)) for k in "SL"}
    print(f"{path}: {len(iv)} frames, short(<3 ms) {100 * np.mean(iv < 3000):.1f}%, "
          f"median {np.median(iv):.0f} us, runs of >=3 equal gaps: {runs}, head {s[:24]}")
    for start in (100.0, 250.0, 500.0):
        hits, sm = simulate(iv, start)
        print(f"   from {start:.0f} Hz: cutoff updates {len(hits)} at frames {hits[:4]} -> final estimate {sm:.0f} Hz")

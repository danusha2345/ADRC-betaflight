#!/usr/bin/env python3
"""20-80 Hz motor-command activity vs upper-rail contact, at matched collective.

Splits a log into 0.5 s windows (50 % overlap), classifies each by median
collective and by the fraction of samples in which any motor sat at the
configured high rail, and reports the band-limited RMS of the motor mean in
each cell.  Also prints the window-level correlation and a first/second-half
split of the high-collective windows.

Both the "rail" flag and the HF measure come from the same motor-command
signal, and collective does not control for maneuver, setpoint or cross-axis
load: this measures association, not causation, and it is not a measurement of
anything audible.

Usage: python3 rail_hf_probe.py <decoded.csv> ...
"""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

WIN_S = 0.5
BANDS = [(40, 55), (55, 70), (70, 85), (85, 101)]


def run(path):
    path = Path(path)
    hdr = {}
    for row in csv.reader((path.parent / (path.name[:-4] + ".headers.csv")).open()):
        if len(row) >= 2:
            hdr[row[0]] = row[1]
    lo, hi = (int(v) for v in hdr["motorOutput"].split(","))

    cols = ["time (us)"] + [f"motor[{i}]" for i in range(4)]
    with path.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in cols], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    t = arr[:, 0] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = arr[:, 1:5]
    coll = (mot.mean(axis=1) - lo) / (hi - lo) * 100
    rail = mot.max(axis=1) >= hi
    sos = butter(2, [20, 80], btype="bandpass", fs=fs, output="sos")
    hf = sosfiltfilt(sos, mot.mean(axis=1))

    w = int(WIN_S * fs)
    rows = []
    for s in range(0, len(t) - w, w // 2):
        sl = slice(s, s + w)
        rows.append((t[s], np.median(coll[sl]), rail[sl].mean(),
                     np.sqrt(np.mean(hf[sl] ** 2))))
    r = np.asarray(rows)

    print(f"\n=== {path.name}  wo {hdr.get('adrcWO')}  b0 {hdr.get('adrcB0')} ===")
    print("  collective    n(rail<0.5%)  HF20-80   n(rail>=2%)  HF20-80")
    for a, b in BANDS:
        m = (r[:, 1] >= a) & (r[:, 1] < b)
        q = r[m & (r[:, 2] < 0.005)]
        s_ = r[m & (r[:, 2] >= 0.02)]
        f1 = f"{np.median(q[:, 3]):7.1f}" if len(q) else "      -"
        f2 = f"{np.median(s_[:, 3]):7.1f}" if len(s_) else "      -"
        print(f"  {a:3d}-{b:3d} %      {len(q):5d}   {f1}       {len(s_):5d}  {f2}")

    hiC = r[r[:, 1] > 50]
    if len(hiC) > 4:
        print(f"  window corr(rail duty, HF) over coll>50 %: "
              f"{np.corrcoef(hiC[:, 2], hiC[:, 3])[0, 1]:+.2f}  (n={len(hiC)})")
        half = t[-1] / 2
        for lbl, sel in [("1st half", hiC[hiC[:, 0] < half]),
                         ("2nd half", hiC[hiC[:, 0] >= half])]:
            if len(sel):
                print(f"    {lbl}: n={len(sel):3d}  rail duty med {np.median(sel[:, 2])*100:5.1f} %  "
                      f"HF med {np.median(sel[:, 3]):5.1f}")


for p in sys.argv[1:]:
    run(p)

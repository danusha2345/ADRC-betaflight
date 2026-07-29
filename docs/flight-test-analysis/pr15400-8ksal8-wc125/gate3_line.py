#!/usr/bin/env python3
"""Flight 3 (Wind): when/why did the gate open on the ground?
Plus: does the ~310 Hz line track collective (motor line) or stay fixed (frame mode)?"""
import csv
import numpy as np

COLS = ["time (us)", "rcCommand[3]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]", "debug[7]"]
MIN_OUT, MAX_OUT = 198, 2047

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

d = load("../ks0728/f2/3rd_Flight_Wind_btfl_004.01.csv")
t = d["time (us)"] / 1e6; t -= t[0]
fs = 1 / np.median(np.diff(t))
mot = [d[f"motor[{i}]"] for i in range(4)]
coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
gate = d["debug[7]"] > 0
thr = (d["rcCommand[3]"] - 1000) / 10

print("=== flight 3 first 7 s: gate/gyro/throttle timeline (50 ms rows where something happens) ===")
print(f"first sample: debug7={d['debug[7]'][0]:.0f} gate={'OPEN' if gate[0] else 'closed'} coll={coll[0]:.1f}% thr={thr[0]:.1f}%")
# find first gate-open transition if any
tr = np.flatnonzero(~gate[:-1] & gate[1:])
if len(tr) and t[tr[0]] < 7:
    i = tr[0]
    print(f"gate opens at t={t[i]:.3f}s")
    w0, w1 = max(0, i - int(0.3*fs)), i + int(0.3*fs)
    g = np.abs(np.stack([d[f'gyroUnfilt[{ax}]'][w0:w1] for ax in range(3)]))
    print(f"  gyro max any axis in +/-0.3s: {g.max():.0f} dps; throttle {thr[i]:.1f}%; coll {coll[i]:.1f}%")
else:
    print("gate open from sample 0 (no transition in first 7 s)")
# sustained rotation check in first 7 s: windows of 25 ms where min|gyro| any axis > 20
W = int(0.025 * fs)
found = []
gy = np.stack([d[f"gyroUnfilt[{ax}]"] for ax in range(3)])
for st in range(0, int(6.0 * fs) - W, W // 2):
    w = np.abs(gy[:, st:st + W])
    for ax in range(3):
        if w[ax].min() > 20:
            found.append((t[st], ax, w[ax].min(), w[ax].max()))
if found:
    for f0 in found[:8]:
        print(f"  sustained>20dps: t={f0[0]:.2f}s axis{f0[1]} min {f0[2]:.0f} max {f0[3]:.0f}")
else:
    print("  no 25ms window with sustained |gyro|>20 dps in first 6 s (ground)")
print(f"  ground gyro absolute max first 6 s: {np.abs(gy[:, :int(6*fs)]).max():.0f} dps")
print(f"  takeoff (coll>12%) at t={t[np.argmax(coll > 12)]:.2f}s")

print("\n=== line-vs-collective tracking (all 5 logs, pitch gyro, peak in 200-500 Hz per 2 s window) ===")
import glob
for path in sorted(glob.glob("../ks0728/f1/*.01.csv") + glob.glob("../ks0728/f2/*.01.csv") + glob.glob("*.01.csv")):
    dd = load(path)
    tt = dd["time (us)"] / 1e6; tt -= tt[0]
    fs2 = 1 / np.median(np.diff(tt))
    m2 = [dd[f"motor[{i}]"] for i in range(4)]
    c2 = (np.mean(m2, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    W2 = int(2 * fs2)
    pts = []
    for st in range(0, len(tt) - W2, W2):
        ws = slice(st, st + W2)
        cm = c2[ws].mean()
        if cm < 15 or c2[ws].std() > 5:
            continue
        g = dd["gyroUnfilt[1]"][ws]
        F = np.abs(np.fft.rfft((g - g.mean()) * np.hanning(len(g))))**2
        fr = np.fft.rfftfreq(W2, 1 / fs2)
        band = (fr > 200) & (fr < 500)
        pts.append((cm, fr[band][np.argmax(F[band])]))
    if len(pts) >= 8:
        pts = np.array(pts)
        r = np.corrcoef(pts[:, 0], pts[:, 1])[0, 1]
        lo, hi = pts[:, 0].min(), pts[:, 0].max()
        name = path.split("/")[-1][:28]
        print(f"{name:30s} n={len(pts):3d} coll {lo:.0f}-{hi:.0f}%  corr(coll, peakHz) = {r:+.2f}  "
              f"peak range {pts[:,1].min():.0f}-{pts[:,1].max():.0f} Hz")

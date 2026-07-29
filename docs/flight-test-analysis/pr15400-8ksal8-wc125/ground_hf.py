#!/usr/bin/env python3
"""(A) armed-on-ground idle segments: 15-40 Hz self-oscillation check + gate state.
(B) full-rate hover spectrum: dominant HF lines for the wo-vs-resonance heuristic."""
import csv, glob
import numpy as np

FILES = sorted(glob.glob("../ks0728/f1/*.01.csv") + glob.glob("../ks0728/f2/*.01.csv") +
               glob.glob("*.01.csv"))
COLS = ["time (us)", "setpoint[0]", "setpoint[1]",
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

def band_rms(x, fs, f1, f2):
    x = x - x.mean()
    F = np.abs(np.fft.rfft(x * np.hanning(len(x))))**2
    fr = np.fft.rfftfreq(len(x), 1 / fs)
    b = (fr >= f1) & (fr <= f2)
    return np.sqrt(np.sum(F[b]) / np.sum(F[1:])) * x.std()

for path in FILES:
    d = load(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{i}]"] for i in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    name = path.split("/")[-1].replace(".01.csv", "")
    print(f"\n=== {name} ===")

    # (A) ground idle: contiguous run from log start with coll < 8%
    n0 = 0
    while n0 < len(t) and coll[n0] < 8:
        n0 += 1
    if n0 > int(0.3 * fs):
        seg = slice(0, n0)
        dur = t[n0 - 1]
        gate_open = (d["debug[7]"][seg] > 0).mean() * 100
        rms = {ax: band_rms(d[f"gyroUnfilt[{ax}]"][seg], fs, 15, 40) for ax in (0, 1, 2)}
        tot = {ax: np.std(d[f"gyroUnfilt[{ax}]"][seg]) for ax in (0, 1, 2)}
        print(f"(A) ground idle {dur:.2f}s pre-takeoff: gate open {gate_open:.0f}% | "
              f"15-40Hz RMS R/P/Y = {rms[0]:.1f}/{rms[1]:.1f}/{rms[2]:.1f} dps "
              f"(total std {tot[0]:.1f}/{tot[1]:.1f}/{tot[2]:.1f})")
    else:
        print(f"(A) ground idle segment too short ({n0/fs:.2f}s)")

    # (B) hover-band HF spectrum: calm windows 25-40% collective, Welch-average
    W = int(2 * fs)
    acc, nwin = None, 0
    for st in range(0, len(t) - W, W):
        ws = slice(st, st + W)
        c = coll[ws]
        if not (c.min() > 20 and c.max() < 45):
            continue
        if np.std(d["setpoint[0]"][ws]) > 30 or np.std(d["setpoint[1]"][ws]) > 30:
            continue
        g = d["gyroUnfilt[1]"][ws]
        F = np.abs(np.fft.rfft((g - g.mean()) * np.hanning(len(g))))**2
        acc = F if acc is None else acc + F
        nwin += 1
    if nwin:
        fr = np.fft.rfftfreq(W, 1 / fs)
        psd = acc / nwin
        # top-5 peaks above 60 Hz (skip control band), local-max, min separation 15 Hz
        hi = fr > 60
        idxs = np.argsort(psd[hi])[::-1]
        picked = []
        for i in idxs:
            f0 = fr[hi][i]
            if all(abs(f0 - p) > 15 for p, _ in picked):
                floor = np.median(psd[(fr > f0 - 30) & (fr < f0 + 30)])
                picked.append((f0, psd[hi][i] / floor))
            if len(picked) == 5:
                break
        pk = "  ".join(f"{f0:.0f}Hz({r:.0f}x)" for f0, r in sorted(picked))
        print(f"(B) pitch-gyro HF lines (avg {nwin} calm hover windows): {pk}")
    else:
        print("(B) no calm hover windows in 20-45% collective")

#!/usr/bin/env python3
"""ADRC-024: episodic-ring incidence vs tune variant (2026-07-15 flights).

Ring window = 1 s Hann window, gate open, motors on, stick-throttle 10-35 %,
dominant 10-40 Hz PSD peak lands in 18-32 Hz with tone RMS > 5 deg/s and
tone fraction > 0.5 of the 5-100 Hz RMS (the b4 ADRC-024 signature).
Worst window = highest tone RMS among ring windows.

Run from this directory after decoding the .bbl files (blackbox_decode *.bbl).
"""
import csv as csvmod
import numpy as np

LOGS = [
    ("btfl_001_p1_roll_doublets.01.csv", "001 base wc60/wo100"),
    ("btfl_005_p1_pitch_doublets.01.csv", "005 base"),
    ("btfl_006_p1_chops_and_playing.01.csv", "006 base"),
    ("btfl_010_p1_playing.01.csv", "010 base"),
    ("btfl_007_p1_but_higher_wo.01.csv", "007 wo150"),
    ("btfl_008_p1_but_higher_wc.01.csv", "008 wc85"),
    ("btfl_002_p2_converted_stock_tune.01.csv", "002 p2 wc37/wo149"),
    ("btfl_009_p2_stock_tune_rolls_n_punches.01.csv", "009 p2"),
    ("btfl_004_p3_cascade_eso.01.csv", "004 p3 cascade"),
]

def load(path, cols):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    d = np.genfromtxt(path, delimiter=",", skip_header=1,
                      usecols=[idx[c] for c in cols])
    return {c: d[:, k] for k, c in enumerate(cols)}

def tone(x, fs, flo=10, fhi=40):
    w = np.hanning(len(x))
    X = np.fft.rfft((x - x.mean()) * w)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    psd = np.abs(X) ** 2 / (fs * (w ** 2).sum())
    band = (f >= flo) & (f <= fhi)
    pk = np.argmax(psd * band)
    df = f[1] - f[0]
    tr = np.sqrt(psd[(f >= f[pk] - 2) & (f <= f[pk] + 2)].sum() * df * 2)
    tot = np.sqrt(psd[(f >= 5) & (f <= 100)].sum() * df * 2)
    return f[pk], tr, tr / tot if tot > 0 else 0

def main():
    print(f"{'log':<22} {'win10-35%':>9} {'ring n':>6} {'ring%':>6} "
          f"{'f med':>6} {'amp max':>8} {'worst':>14}")
    for path, label in LOGS:
        d = load(path, ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]",
                        "debug[7]", "motor[0]", "motor[1]", "motor[2]", "motor[3]"])
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1 / np.median(np.diff(t))
        thr = (d["rcCommand[3]"] - 1000) / 10
        gate = d["debug[7]"] > 0
        mot = np.mean([d[f"motor[{i}]"] for i in range(4)], axis=0) > 68
        win = int(fs)
        hop = win // 2
        n = 0
        rings = []
        for s in range(0, len(t) - win, hop):
            sl = slice(s, s + win)
            if not (gate[sl].all() and mot[sl].all()):
                continue
            th = thr[sl].mean()
            if not (10 <= th <= 35):
                continue
            n += 1
            fR, aR, frR = tone(d["gyroADC[0]"][sl], fs)
            fP, aP, frP = tone(d["gyroADC[1]"][sl], fs)
            fq, a, fr = (fR, aR, frR) if aR >= aP else (fP, aP, frP)
            if a > 5 and fr > 0.5 and 18 <= fq <= 32:
                rings.append((t[s], fq, a, fr))
        if rings:
            worst = max(rings, key=lambda r: r[2])
            # merge ring windows closer than 1.5 s into independent episodes
            ts = sorted(r[0] for r in rings)
            episodes = 1 + sum(1 for a, b in zip(ts, ts[1:]) if b - a > 1.5)
            print(f"{label:<22} {n:>9} {len(rings):>6} {100*len(rings)/max(n,1):>5.0f}% "
                  f"{np.median([r[1] for r in rings]):>6.1f} {worst[2]:>8.1f} "
                  f"ep={episodes} t={worst[0]:.1f}s@{worst[1]:.0f}Hz")
        else:
            print(f"{label:<22} {n:>9} {'0':>6} {'0':>5}% {'-':>6} {'-':>8}")

if __name__ == "__main__":
    main()

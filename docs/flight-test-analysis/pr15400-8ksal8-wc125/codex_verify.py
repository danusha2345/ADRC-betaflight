#!/usr/bin/env python3
"""Verify Codex re-review claims: z3@start (flight 3), full pre-liftoff ground
band-RMS, motor 1x orders from eRPM vs the 307-318 Hz spectral family."""
import csv, glob
import numpy as np

MIN_OUT, MAX_OUT = 198, 2047
COLS = ["time (us)", "rcCommand[3]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[2]", "debug[5]", "debug[6]", "debug[7]",
        "eRPM[0]", "eRPM[1]", "eRPM[2]", "eRPM[3]",
        "setpoint[0]", "setpoint[1]"]

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

FILES = sorted(glob.glob("../ks0728/f1/*.01.csv") + glob.glob("../ks0728/f2/*.01.csv") +
               glob.glob("*.01.csv"))

print("=== flight 3: z3 and motors at first samples ===")
d3 = load("../ks0728/f2/3rd_Flight_Wind_btfl_004.01.csv")
for i in (0, 1, 2):
    print(f"  sample {i}: z3_R={d3['debug[2]'][i]*16:+.0f} z3_P={d3['debug[5]'][i]*16:+.0f} "
          f"z3_Y={d3['debug[6]'][i]*16:+.0f} motors={[int(d3[f'motor[{m}]'][i]) for m in range(4)]}")
mot0 = np.array([d3[f"motor[{m}]"][:100] for m in range(4)])
print(f"  first 100 samples: motor spread max-min = {np.max(mot0.max(1)-mot0.min(1)):.0f}, "
      f"per-motor means {mot0.mean(1).round(0)}")

print("\n=== full pre-liftoff ground segments: 15-40 Hz band RMS (worst axis) ===")
for path in FILES:
    d = load(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{m}]"] for m in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    # full pre-liftoff = up to first sustained coll>12 (0.25s)
    air_idx = None
    W = int(0.25 * fs)
    for st in range(0, len(t) - W):
        if coll[st:st + W].min() > 12:
            air_idx = st; break
    if air_idx is None or air_idx < int(0.3 * fs):
        print(f"{path.split('/')[-1][:30]:32s} no usable ground segment"); continue
    seg = slice(0, air_idx)
    rms = [band_rms(d[f"gyroUnfilt[{ax}]"][seg], fs, 15, 40) for ax in (0, 1, 2)]
    print(f"{path.split('/')[-1][:30]:32s} dur {t[air_idx]:.2f}s  15-40Hz RMS R/P/Y = "
          f"{rms[0]:.2f}/{rms[1]:.2f}/{rms[2]:.2f} dps  max={max(rms):.2f}")

print("\n=== motor 1x orders from eRPM in calm hover windows (poles=12 -> mech Hz = eRPM*100/6/60) ===")
for path in FILES:
    d = load(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{m}]"] for m in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    W = int(2 * fs)
    freqs = [[] for _ in range(4)]
    for st in range(0, len(t) - W, W):
        ws = slice(st, st + W)
        c = coll[ws]
        if not (c.min() > 20 and c.max() < 45):
            continue
        if np.std(d["setpoint[0]"][ws]) > 30 or np.std(d["setpoint[1]"][ws]) > 30:
            continue
        for m in range(4):
            freqs[m].append(np.median(d[f"eRPM[{m}]"][ws]) * 100 / 6 / 60)
    if freqs[0]:
        med = [np.median(f) for f in freqs]
        print(f"{path.split('/')[-1][:30]:32s} n={len(freqs[0]):3d}  motor 1x med = "
              f"{med[0]:.0f}/{med[1]:.0f}/{med[2]:.0f}/{med[3]:.0f} Hz")

#!/usr/bin/env python3
"""Re-verification pass: ring-window narrowness (wind pitfall), SQRT cap check,
looser sticking scan, collective sanity."""
import csv, glob
import numpy as np

FILES = sorted(glob.glob("f1/*.01.csv") + glob.glob("f2/*.01.csv"))
COLS = ["time (us)", "rcCommand[3]",
        "setpoint[0]", "setpoint[1]", "setpoint[2]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[7]"]
MIN_OUT, MAX_OUT = 198, 2047
HOVER = 29.0

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

for path in FILES:
    d = load(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{i}]"] for i in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    scale = np.abs(d["debug[7]"]) / 100
    air = coll > 12
    name = path.split("/")[-1].replace(".01.csv", "")
    print(f"\n=== {name} ===")

    # SQRT cap sanity: expected scale = clamp(sqrt(LPF(coll)/hover), 1, 3)
    # compare observed max scale vs sqrt of observed p99.9 collective
    c999 = np.percentile(coll[air], 99.9)
    print(f"scale max obs {scale[air].max():.3f}; sqrt(p99.9 coll {c999:.0f}%/29) = {np.sqrt(c999/HOVER):.3f} "
          f"(LPF 2 Hz => obs max should be <= instantaneous bound)")
    # saturation exposure (collective validity pitfall)
    sat = (np.max(mot, axis=0) >= 2040) & air
    print(f"any-motor-at-max while airborne: {sat.mean()*100:.2f}% of samples")

    # ring windows with narrowness check
    W, H = int(fs), int(0.25 * fs)
    gate = d["debug[7]"] > 0
    flagged = []
    for st in range(0, len(t) - W, H):
        ws = slice(st, st + W)
        if not air[ws].all() or not gate[ws].all():
            continue
        calm = all(np.std(d[f"setpoint[{ax}]"][ws]) < 30 and
                   np.max(np.abs(d[f"setpoint[{ax}]"][ws])) < 30 for ax in (0, 1))
        if not calm:
            continue
        for ax, lbl in ((0, "roll"), (1, "pitch"), (2, "yaw")):
            g = d[f"gyroUnfilt[{ax}]"][ws]
            g = g - g.mean()
            F = np.abs(np.fft.rfft(g * np.hanning(len(g))))**2
            fr = np.fft.rfftfreq(len(g), 1 / fs)
            band = (fr >= 18) & (fr <= 32)
            rms = np.sqrt(np.sum(F[band]) / np.sum(F[1:])) * g.std()
            if rms > 10:
                ipk = np.argmax(F[band]); pk = fr[band][ipk]
                # local floor: median PSD in 10-50 Hz excluding +/-3 Hz around peak
                loc = (fr >= 10) & (fr <= 50) & (np.abs(fr - pk) > 3)
                ratio = F[band][ipk] / np.median(F[loc])
                # low-freq skirt: energy 1-8 Hz vs band
                lf = (fr >= 1) & (fr <= 8)
                lf_ratio = np.sum(F[lf]) / np.sum(F[band])
                flagged.append((t[st], lbl, rms, pk, ratio, lf_ratio))
    if flagged:
        print("flagged windows (narrowness: peak/floor; LF skirt: E[1-8Hz]/E[band]):")
        for w in flagged:
            verdict = "LINE" if w[4] > 10 and w[5] < 2 else "skirt/wind"
            print(f"  t={w[0]:6.1f} {w[1]:5s} rms {w[2]:5.1f} dps @ {w[3]:4.1f} Hz  "
                  f"peak/floor {w[4]:6.1f}x  LF/band {w[5]:5.2f}  -> {verdict}")
    else:
        print("no flagged ring windows")

    # looser sticking scan: >=150 ms, |sp|med>100, gyro med < 40% of sp
    Ws = int(0.15 * fs)
    found = 0
    for ax, lbl in ((0, "roll"), (1, "pitch")):
        sp, gy = d[f"setpoint[{ax}]"], d[f"gyroUnfilt[{ax}]"]
        for st in range(0, len(t) - Ws, Ws // 2):
            ws = slice(st, st + Ws)
            if not air[ws].all():
                continue
            spm = np.median(sp[ws]); gym = np.median(gy[ws])
            if abs(spm) > 100 and abs(gym) < 0.4 * abs(spm):
                found += 1
                if found <= 5:
                    print(f"  loose stall-cand {lbl} t={t[st]:.2f} sp~{spm:+.0f} gyro~{gym:+.0f}")
    if not found:
        print("  loose scan (>=150 ms, |sp|>100): none")
    elif found > 5:
        print(f"  ... {found} loose candidates total")

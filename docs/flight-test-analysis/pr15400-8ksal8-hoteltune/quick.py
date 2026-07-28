#!/usr/bin/env python3
"""8ksal8 2026-07-28 first hotel-tune flights (b5, SQRT law live)."""
import csv, glob, sys
import numpy as np

FILES = sorted(glob.glob("f1/*.01.csv") + glob.glob("f2/*.01.csv"))
COLS = ["time (us)", "rcCommand[3]",
        "setpoint[0]", "setpoint[1]", "setpoint[2]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[7]", "debug[2]", "debug[5]", "debug[6]",
        "amperageLatest (A)", "vbatLatest (V)"]
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

for path in FILES:
    d = load(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{i}]"] for i in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    scale = np.abs(d["debug[7]"]) / 100
    gate = np.sign(d["debug[7]"])
    air = coll > 12
    name = path.split("/")[-1].replace(".01.csv", "")
    print(f"\n=== {name} ===")
    print(f"fs {fs:.0f} Hz, dur {t[-1]:.0f} s, airborne {air.mean()*t[-1]:.0f} s, "
          f"gate open {(gate>0).mean()*100:.0f}%")
    print(f"collective med/p90/max {np.median(coll[air]):.0f}/{np.percentile(coll[air],90):.0f}/{coll[air].max():.0f} %  "
          f"b0scale med/p90/max {np.median(scale[air]):.2f}/{np.percentile(scale[air],90):.2f}/{scale[air].max():.2f}")

    # hardened ring criterion: 1s window, 0.25s hop, calm sp, 18-32 Hz max-axis band RMS > 10
    W, H = int(fs), int(0.25 * fs)
    ring, tot, worst = 0, 0, (0, 0, "")
    for st in range(0, len(t) - W, H):
        ws = slice(st, st + W)
        if not air[ws].all() or gate[ws].min() <= 0:
            continue
        calm = all(np.std(d[f"setpoint[{ax}]"][ws]) < 30 and
                   np.max(np.abs(d[f"setpoint[{ax}]"][ws])) < 30 for ax in (0, 1))
        if not calm:
            continue
        tot += 1
        for ax, lbl in ((0, "roll"), (1, "pitch"), (2, "yaw")):
            g = d[f"gyroUnfilt[{ax}]"][ws]
            g = g - g.mean()
            F = np.fft.rfft(g * np.hanning(len(g)))
            fr = np.fft.rfftfreq(len(g), 1 / fs)
            band = (fr >= 18) & (fr <= 32)
            # band RMS via Parseval on the windowed signal (approx, consistent across files)
            rms = np.sqrt(np.sum(np.abs(F[band])**2) / np.sum(np.abs(F[1:])**2)) * g.std()
            if rms > worst[0]:
                pk = fr[band][np.argmax(np.abs(F[band]))]
                worst = (rms, pk, f"{lbl} t={t[st]:.1f}")
            if rms > 10:
                ring += 1
                break
    print(f"ring windows {ring}/{tot}, worst band-RMS {worst[0]:.1f} dps @ {worst[1]:.1f} Hz ({worst[2]})")

    # sticking scan: 0.25s windows where |sp|med > 150 and |gyro|med < 0.4*|sp|med
    Ws = int(0.25 * fs)
    events = []
    for ax, lbl in ((0, "roll"), (1, "pitch")):
        sp, gy = d[f"setpoint[{ax}]"], d[f"gyroUnfilt[{ax}]"]
        run = None
        for st in range(0, len(t) - Ws, Ws // 2):
            ws = slice(st, st + Ws)
            if not air[ws].all():
                run = None; continue
            spm = np.median(sp[ws]); gym = np.median(gy[ws])
            if abs(spm) > 150 and abs(gym) < 0.4 * abs(spm) and np.sign(spm) != -np.sign(gym):
                if run is None:
                    run = [t[st], t[st + Ws], spm, gym, lbl]
                else:
                    run[1] = t[st + Ws]
            else:
                if run and run[1] - run[0] >= 0.25:
                    events.append(tuple(run))
                run = None
    for e in events:
        print(f"  stall-cand {e[4]} t={e[0]:.1f}-{e[1]:.1f}s ({(e[1]-e[0])*1000:.0f} ms) sp~{e[2]:+.0f} gyro~{e[3]:+.0f}")
    if not events:
        print("  no sticking-like stalls (|sp|>150, gyro<40% of sp, >=250 ms)")

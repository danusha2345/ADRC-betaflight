#!/usr/bin/env python3
"""bvandevliet SPEEDYBEE, 2026-07-22: the wc/wo 2x2 on SQRT (b5, b0=2000).

Sessions (headers): log1 = 60/100, log2 = 45/100, log3 = 60/150,
log4..7 = 45/150 attempts, log8 = 45/100. All 543f1a5ff, adrc_b0_law = 1.

Run after: for f in btfl_00*.bbl; do blackbox_decode --debug \
    --unit-frame-time us "$f"; done
Part 1: per-log gate/saturation overview (the wo = 150 failure signature).
Part 2: ring episodes in the flyable arms (the wc lever test), same hardened
criterion as jm_lawab2.py (overlapping 1 s windows, 0.25 s hop, setpoint
std AND max < 30 dps, max-axis 18-32 Hz band RMS > 10 dps, merged episodes,
frequency from the max-RMS axis).
"""
import csv
import numpy as np

CFG = {1: "60/100", 2: "45/100", 3: "60/150", 4: "45/150", 5: "45/150",
       6: "45/150", 7: "45/150", 8: "45/100"}
COLS = ["time (us)", "rcCommand[3]", "debug[7]", "gyroUnfilt[0]",
        "gyroUnfilt[1]", "setpoint[0]", "setpoint[1]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]"]


def load(fname, cols):
    with open(fname) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        idx = [hdr.index(c) for c in cols]
        rows = []
        for line in r:
            try:
                rows.append([float(line[i]) for i in idx])
            except (ValueError, IndexError):
                pass
    a = np.array(rows)
    return {c: a[:, j] for j, c in enumerate(cols)}


def band_rms(x, fs, f1, f2):
    x = x - np.mean(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = (f >= f1) & (f <= f2)
    return np.sqrt(2 * np.sum(np.abs(X[m]) ** 2)) / len(x)


print("=== Part 1: gate / saturation overview ===")
for n in range(1, 9):
    d = load(f"btfl_00{n}.01.csv", COLS)
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000) / 10
    o = d["debug[7]"] >= 0
    sat = (np.maximum.reduce([d[f"motor[{i}]"] for i in range(4)])
           >= 2000).mean() * 100
    if o.any():
        i0 = int(np.argmax(o))
        i1 = len(o) - int(np.argmax(o[::-1]))
        g = d["gyroUnfilt[0]"][i0:i1]
        g = g - np.mean(g)
        info = f"gate@{t[i0]:5.2f}s thr@open {thr[i0]:5.1f}%"
        if len(g) > 200:
            X = np.abs(np.fft.rfft(g * np.hanning(len(g))))
            f = np.fft.rfftfreq(len(g), 1 / fs)
            b = (f >= 3) & (f <= 120)
            info += f"  domPk {f[b][np.argmax(X[b])]:5.1f} Hz  gyroP2P {np.ptp(g):5.0f}"
    else:
        info = "gate NEVER open"
    print(f"log{n} wc/wo {CFG[n]} dur {t[-1]:5.1f}s  thr med {np.median(thr):5.1f}% "
          f"max {thr.max():5.1f}%  motorSat {sat:4.1f}%  {info}")

print()
print("=== Part 2: ring episodes in the flyable arms ===")
for n in (1, 2, 8):
    d = load(f"btfl_00{n}.01.csv", COLS)
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    o = d["debug[7]"] >= 0
    i0 = int(np.argmax(o))
    i1 = len(o) - int(np.argmax(o[::-1]))
    thr = (d["rcCommand[3]"] - 1000) / 10
    W = int(round(fs))
    HOP = W // 4
    hits, tot, worst, wf = [], 0, 0.0, 0.0
    for st in range(i0, i1 - W, HOP):
        ws = slice(st, st + W)
        sp0, sp1 = d["setpoint[0]"][ws], d["setpoint[1]"][ws]
        if (np.std(sp0) >= 30 or np.std(sp1) >= 30 or
                np.max(np.abs(sp0)) >= 30 or np.max(np.abs(sp1)) >= 30):
            continue
        tot += 1
        rr = [band_rms(d[ax][ws], fs, 18, 32)
              for ax in ("gyroUnfilt[0]", "gyroUnfilt[1]")]
        ai = int(np.argmax(rr))
        r = rr[ai]
        if r > 10:
            hits.append((t[ws.start], np.median(thr[ws]), r))
        if r > worst:
            g = d[("gyroUnfilt[0]", "gyroUnfilt[1]")[ai]][ws]
            g = g - np.mean(g)
            spec = np.abs(np.fft.rfft(g * np.hanning(len(g))))
            f = np.fft.rfftfreq(len(g), 1 / fs)
            b = (f >= 10) & (f <= 40)
            worst, wf = r, f[b][np.argmax(spec[b])]
    ep = []
    for t0, tm, r in hits:
        if ep and t0 <= ep[-1][1] + 0.3:
            ep[-1] = (ep[-1][0], t0 + 1, max(ep[-1][2], r))
        else:
            ep.append((t0, t0 + 1, r))
    print(f"log{n} wc/wo {CFG[n]}: ringWin {len(hits)}/{tot}  episodes {len(ep)}  "
          f"worst {worst:5.1f} dps @{wf:4.1f} Hz")
    for t0, t1, r in ep:
        print(f"    ep {t0:5.1f}-{t1:5.1f}s peak {r:5.1f} dps")

#!/usr/bin/env python3
"""jmsweng DAKEFPV, 2026-07-21: law A/B redo with adrc_hover_throttle = 28
(btfl_lawab2.bbl, 9 sessions: 1,2 = QUADRATIC; 3,4 = SQRT; 5,6,9 = LINEAR;
7,8 = FIXED — matches the headers' adrc_b0_law 0,0,1,1,2,2,3,3,2).

Run after: blackbox_decode --debug --unit-frame-time us btfl_lawab2.bbl
Same corrected methods as jm_b0sweep.py (band RMS sqrt(2*sum|X|^2)/N, gate
slice masked before windowing). Ring window = 1 s, calm R/P setpoints
(std < 30 dps), max-axis 18-32 Hz band RMS > 10 dps.
"""
import csv
import numpy as np

LAW = {1: "QUAD", 2: "QUAD", 3: "SQRT", 4: "SQRT", 5: "LIN", 6: "LIN",
       7: "FIX", 8: "FIX", 9: "LIN"}
COLS = ["time (us)", "rcCommand[3]", "debug[7]", "gyroUnfilt[0]",
        "gyroUnfilt[1]", "setpoint[0]", "setpoint[1]"]


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


for n in range(1, 10):
    d = load(f"btfl_lawab2.{n:02d}.csv", COLS)
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    o = d["debug[7]"] >= 0
    n_open = int((np.diff(o.astype(int)) == 1).sum())
    i0 = int(np.argmax(o))
    i1 = len(o) - int(np.argmax(o[::-1]))
    s = slice(i0, i1)
    d7 = d["debug[7]"][s]
    thr = (d["rcCommand[3]"] - 1000) / 10
    W = int(round(fs))
    ring, tot, worst, wf = 0, 0, 0.0, 0.0
    events = []
    for w in range((s.stop - s.start) // W):
        ws = slice(s.start + w * W, s.start + (w + 1) * W)
        if (np.std(d["setpoint[0]"][ws]) >= 30 or
                np.std(d["setpoint[1]"][ws]) >= 30):
            continue
        tot += 1
        r = max(band_rms(d["gyroUnfilt[0]"][ws], fs, 18, 32),
                band_rms(d["gyroUnfilt[1]"][ws], fs, 18, 32))
        if r > 10:
            ring += 1
            events.append((t[ws.start], np.median(thr[ws]),
                           np.percentile(thr[ws], 90), r))
        if r > worst:
            g = d["gyroUnfilt[0]"][ws] - np.mean(d["gyroUnfilt[0]"][ws])
            spec = np.abs(np.fft.rfft(g * np.hanning(len(g))))
            f = np.fft.rfftfreq(len(g), 1 / fs)
            b = (f >= 10) & (f <= 40)
            worst, wf = r, f[b][np.argmax(spec[b])]
    print(f"log{n} {LAW[n]:4s} dur {t[-1]:5.1f}s opens={n_open}  "
          f"d7 med/p90/max {np.median(d7):3.0f}/{np.percentile(d7, 90):3.0f}/"
          f"{d7.max():3.0f}  thr med {np.median(thr[s]):4.1f}%  "
          f"ring {ring}/{tot} calm windows  worst {worst:4.1f} dps @{wf:4.1f} Hz")
    for te, tm, tp, r in events:
        print(f"        ring @{te:5.1f}s thr med {tm:4.1f}% p90 {tp:5.1f}%  {r:4.1f} dps")

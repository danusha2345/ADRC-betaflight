#!/usr/bin/env python3
"""jmsweng DAKEFPV, 2026-07-21: law A/B redo with adrc_hover_throttle = 28
(btfl_lawab2.bbl, 9 sessions: 1,2 = QUADRATIC; 3,4 = SQRT; 5,6,9 = LINEAR;
7,8 = FIXED — matches the headers' adrc_b0_law 0,0,1,1,2,2,3,3,2).

Run after: blackbox_decode --debug --unit-frame-time us btfl_lawab2.bbl
Same corrected methods as jm_b0sweep.py (band RMS sqrt(2*sum|X|^2)/N, gate
slice masked before windowing). Ring window = 1 s, hop 0.25 s (overlapping —
a fixed non-overlapping grid can straddle or miss episodes), calm R/P
setpoints gated on BOTH std < 30 dps and max |setpoint| < 30 dps (the
std-only gate admitted windows containing brief commanded transients), the
reported frequency comes from the same axis that produced the max band RMS.
Overlapping ring windows are merged into episodes for counting.
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
    HOP = W // 4
    tot, worst, wf = 0, 0.0, 0.0
    hits = []
    for start in range(s.start, s.stop - W, HOP):
        ws = slice(start, start + W)
        sp0, sp1 = d["setpoint[0]"][ws], d["setpoint[1]"][ws]
        if (np.std(sp0) >= 30 or np.std(sp1) >= 30 or
                np.max(np.abs(sp0)) >= 30 or np.max(np.abs(sp1)) >= 30):
            continue
        tot += 1
        rr = [band_rms(d[ax][ws], fs, 18, 32)
              for ax in ("gyroUnfilt[0]", "gyroUnfilt[1]")]
        ax_i = int(np.argmax(rr))
        r = rr[ax_i]
        if r > 10:
            hits.append((t[ws.start], t[ws.stop - 1], np.median(thr[ws]),
                         np.percentile(thr[ws], 90), r))
        if r > worst:
            ax = ("gyroUnfilt[0]", "gyroUnfilt[1]")[ax_i]
            g = d[ax][ws] - np.mean(d[ax][ws])
            spec = np.abs(np.fft.rfft(g * np.hanning(len(g))))
            f = np.fft.rfftfreq(len(g), 1 / fs)
            b = (f >= 10) & (f <= 40)
            worst, wf = r, f[b][np.argmax(spec[b])]
    # merge overlapping/adjacent ring windows into episodes
    episodes = []
    for t0, t1, tm, tp, r in hits:
        if episodes and t0 <= episodes[-1][1] + 0.3:
            e = episodes[-1]
            episodes[-1] = (e[0], max(e[1], t1), e[2] + [(tm, tp)], max(e[3], r))
        else:
            episodes.append((t0, t1, [(tm, tp)], r))
    print(f"log{n} {LAW[n]:4s} dur {t[-1]:5.1f}s opens={n_open}  "
          f"d7 med/p90/max {np.median(d7):3.0f}/{np.percentile(d7, 90):3.0f}/"
          f"{d7.max():3.0f}  thr med {np.median(thr[s]):4.1f}%  "
          f"ringWin {len(hits)}/{tot} (hop 0.25 s)  episodes {len(episodes)}  "
          f"worst {worst:4.1f} dps @{wf:4.1f} Hz")
    for t0, t1, thrs, r in episodes:
        tms = [x[0] for x in thrs]
        tps = [x[1] for x in thrs]
        print(f"        episode {t0:5.1f}-{t1:5.1f}s  thr med {np.median(tms):4.1f}% "
              f"p90 {max(tps):5.1f}%  peak {r:4.1f} dps")

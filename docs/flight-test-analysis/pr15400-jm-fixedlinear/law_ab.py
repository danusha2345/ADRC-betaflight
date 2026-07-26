#!/usr/bin/env python3
"""jmsweng 5" (DAKEFPVF405), 2026-07-25 — FIXED vs LINEAR b0 law A/B on b5.

Headers (identical apart from the law): 543f1a5ff = b5 tag, pid_type = ADRC,
debug_mode = ADRC, wc = 40/40/40, wo = 100/100/100, b0 = 2000/2000/2000,
adrc_hover_throttle = 28, adrc_liftoff_throttle = 40, thrust_linear = 0,
motor_poles = 14. Fixed.bbl: adrc_b0_law = 3 (FIXED); Linear.bbl: = 2 (LINEAR).

Run after: for f in *.bbl; do blackbox_decode --debug --unit-frame-time us "$f"; done

Ring criterion is the hardened one from pr15400-b5-wcwo2x2/wcwo_2x2.py:
1 s windows, 0.25 s hop, gate open, setpoint std AND max < 30 dps on roll+pitch,
max-axis 18-32 Hz band RMS > 10 dps, episodes merged over 0.3 s gaps.
"""
import csv

import numpy as np

COLS = ["time (us)", "rcCommand[3]", "debug[7]",
        "gyroUnfilt[0]", "gyroUnfilt[1]",
        "setpoint[0]", "setpoint[1]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]"]


def load(fname):
    with open(fname) as f:
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
    x = x - np.mean(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = (f >= f1) & (f <= f2)
    return np.sqrt(2 * np.sum(np.abs(X[m]) ** 2)) / len(x)


for name in ("Fixed", "Linear"):
    d = load(f"{name}.01.csv")
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    o = d["debug[7]"] >= 0
    i0 = int(np.argmax(o))
    i1 = len(o) - int(np.argmax(o[::-1]))
    thr = (d["rcCommand[3]"] - 1000) / 10
    scale = np.abs(d["debug[7]"][i0:i1]) / 100
    print(f"=== {name}: airborne {(i1 - i0) / fs:5.1f} s  "
          f"thr med {np.median(thr[i0:i1]):4.1f} % max {thr[i0:i1].max():5.1f} %  "
          f"b0 scale med {np.median(scale):.2f} max {scale.max():.2f}")

    W = int(round(fs))
    HOP = W // 4
    hits, tot, worst, wf, wax = [], 0, 0.0, 0.0, ""
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
            hits.append((t[ws.start], r))
        if r > worst:
            g = d[("gyroUnfilt[0]", "gyroUnfilt[1]")[ai]][ws]
            g = g - np.mean(g)
            spec = np.abs(np.fft.rfft(g * np.hanning(len(g))))
            f = np.fft.rfftfreq(len(g), 1 / fs)
            b = (f >= 10) & (f <= 40)
            worst, wf, wax = r, f[b][np.argmax(spec[b])], ("roll", "pitch")[ai]
    ep = []
    for t0, r in hits:
        if ep and t0 <= ep[-1][1] + 0.3:
            ep[-1] = (ep[-1][0], t0 + 1, max(ep[-1][2], r))
        else:
            ep.append((t0, t0 + 1, r))
    print(f"    ringWin {len(hits)}/{tot}  episodes {len(ep)}  "
          f"worst {worst:.1f} dps @ {wf:.1f} Hz ({wax})")
    for t0, t1, r in ep:
        m = (t >= t0) & (t <= t1)
        print(f"      ep {t0:5.1f}-{t1:5.1f} s  peak {r:5.1f} dps  "
              f"thr med {np.median(thr[m]):.0f} % p90 {np.percentile(thr[m], 90):.0f} %")

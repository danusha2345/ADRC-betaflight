#!/usr/bin/env python3
"""Rubber-band diagnostics: gate-closure while airborne, step tracking, rebound."""
import csv, glob
import numpy as np

FILES = sorted(glob.glob("*.01.csv"))
COLS = ["time (us)", "rcCommand[3]",
        "setpoint[0]", "setpoint[1]",
        "gyroADC[0]", "gyroADC[1]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[7]"]
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
    gate = d["debug[7]"] > 0
    air = coll > 12
    name = path.split("/")[-1].replace(".01.csv", "")
    print(f"\n=== {name} ===")

    # gate closed while airborne: episodes
    closed = air & ~gate
    print(f"gate closed while airborne: {closed.mean()*100:.1f}% of samples", end="")
    # count episodes > 100 ms
    edges = np.flatnonzero(np.diff(closed.astype(int)))
    n_ep, tot_ms, longest = 0, 0.0, 0.0
    start = None
    ci = closed.astype(int)
    for i in range(1, len(ci)):
        if ci[i] and not ci[i-1]: start = t[i]
        if not ci[i] and ci[i-1] and start is not None:
            dur = (t[i] - start) * 1000
            if dur >= 100: n_ep += 1; tot_ms += dur; longest = max(longest, dur)
            start = None
    print(f", episodes>=100ms: {n_ep}, total {tot_ms/1000:.1f}s, longest {longest:.0f} ms")

    # step tracking + rebound, roll & pitch: find sp steps >200 dps amplitude
    for ax, lbl in ((0, "roll"), (1, "pitch")):
        sp, gy = d[f"setpoint[{ax}]"], d[f"gyroADC[{ax}]"]
        # latency by cross-correlation on active segments
        act = air & (np.abs(sp) > 30)
        if act.sum() > fs * 5:
            s = sp[act] - sp[act].mean(); g = gy[act] - gy[act].mean()
            n = min(len(s), int(fs * 60))
            s, g = s[:n], g[:n]
            lags = np.arange(0, int(0.05 * fs))
            cc = [np.dot(s[:-l or None], g[l:]) for l in lags]
            lat = lags[int(np.argmax(cc))] / fs * 1000
        else:
            lat = float("nan")
        # rebound: sp returns to |sp|<20 after |sp|>300; measure counter-swing of gyro in next 300 ms
        reb = []
        i = 1
        big = np.abs(sp) > 300
        small = np.abs(sp) < 20
        idx_end = np.flatnonzero(big[:-1] & small[1:])
        for ie in idx_end:
            if not air[ie]: continue
            sgn = np.sign(sp[ie])
            w = gy[ie:ie + int(0.3 * fs)]
            if len(w) < 10: continue
            counter = -sgn * w.min() if sgn > 0 else -sgn * w.max()
            reb.append(max(0.0, -counter if sgn < 0 else 0) if False else (sgn * -1 * (w.min() if sgn > 0 else -w.max())))
        if reb:
            reb = np.array([abs(x) for x in reb])
            print(f"{lbl}: latency {lat:.1f} ms, rebounds n={len(reb)}, counter-swing med {np.median(reb):.0f} / p90 {np.percentile(reb,90):.0f} dps")
        else:
            print(f"{lbl}: latency {lat:.1f} ms, no big-step releases")

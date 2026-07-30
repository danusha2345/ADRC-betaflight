#!/usr/bin/env python3
"""8ksal8 hotel-room arm tests: ANGLE+AIRMODE bounce vs AIRMODE-only smooth (ADRC-026 family)."""
import csv, glob
import numpy as np

MIN_OUT, MAX_OUT = 198, 2047
COLS = ["time (us)", "rcCommand[3]",
        "setpoint[0]", "setpoint[1]", "setpoint[2]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[2]", "debug[5]", "debug[6]", "debug[7]",
        "flightModeFlags (flags)"]

def load(path):
    with open(path) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        idx = []
        for c in COLS:
            idx.append(hdr.index(c) if c in hdr else None)
        rows = []
        for line in r:
            try:
                rows.append([float(line[i]) if i is not None and line[i].strip().replace('-','').replace('.','').isdigit() or (i is not None and c != "flightModeFlags (flags)") else 0 for i, c in zip(idx, COLS)])
            except (ValueError, IndexError):
                pass
    a = np.array(rows)
    return {c: a[:, j] for j, c in enumerate(COLS)}

def loadsafe(path):
    with open(path) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        idx = {c: (hdr.index(c) if c in hdr else None) for c in COLS}
        rows = []
        flags = []
        for line in r:
            try:
                rows.append([float(line[idx[c]]) for c in COLS[:-1]])
                flags.append(line[idx[COLS[-1]]].strip() if idx[COLS[-1]] is not None else "")
            except (ValueError, IndexError):
                pass
    a = np.array(rows)
    d = {c: a[:, j] for j, c in enumerate(COLS[:-1])}
    d["flags"] = flags
    return d

for path in sorted(glob.glob("*.0*.csv")):
    d = loadsafe(path)
    t = d["time (us)"] / 1e6; t -= t[0]
    fs = 1 / np.median(np.diff(t))
    mot = [d[f"motor[{i}]"] for i in range(4)]
    coll = (np.mean(mot, axis=0) - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    gate = d["debug[7]"] > 0
    thr = (d["rcCommand[3]"] - 1000) / 10
    print(f"\n=== {path} ===")
    print(f"fs {fs:.0f} Hz, dur {t[-1]:.1f} s, flags first: {d['flags'][0]!r}, flags uniq: {sorted(set(d['flags']))[:4]}")
    # gate opening moment
    if gate[0]:
        print("gate OPEN at first sample")
        io = 0
    else:
        tr = np.flatnonzero(~gate[:-1] & gate[1:])
        io = tr[0] + 1 if len(tr) else None
        print(f"gate opens at t={t[io]:.3f}s" if io is not None else "gate never opens")
    # first 3 s timeline, 0.2 s rows
    print("   t   | thr%  coll% | gate | maxsp_rp  maxgy_rp | sp_yaw gy_yaw | z3P(x16)   z3Y(x16) | mot max")
    W = int(0.2 * fs)
    for st in range(0, min(len(t), int(3.2 * fs)) - W, W):
        ws = slice(st, st + W)
        msp = max(np.abs(d["setpoint[0]"][ws]).max(), np.abs(d["setpoint[1]"][ws]).max())
        mgy = max(np.abs(d["gyroUnfilt[0]"][ws]).max(), np.abs(d["gyroUnfilt[1]"][ws]).max())
        print(f" {t[st]:5.2f} | {np.median(thr[ws]):5.1f} {np.median(coll[ws]):5.1f} | "
              f"{'OPEN' if gate[ws].mean() > 0.5 else ' .  '} | {msp:8.0f} {mgy:9.0f} | "
              f"{np.abs(d['setpoint[2]'][ws]).max():6.0f} {np.abs(d['gyroUnfilt[2]'][ws]).max():6.0f} | "
              f"{d['debug[5]'][ws].mean()*16:+9.0f} {d['debug[6]'][ws].mean()*16:+9.0f} | "
              f"{max(m[ws].max() for m in mot):4.0f}")
    # sustained-rotation check before gate open
    if io and io > 10:
        gy = np.stack([d[f"gyroUnfilt[{ax}]"][:io] for ax in range(3)])
        Wh = int(0.025 * fs)
        hit = None
        for st in range(0, io - Wh):
            w = np.abs(gy[:, st:st + Wh])
            for ax in range(3):
                if w[ax].min() > 20:
                    hit = (t[st], ax); break
            if hit: break
        print(f"pre-open sustained>20dps/25ms: {hit}")
        print(f"pre-open max |setpoint| R/P: {np.abs(d['setpoint[0]'][:io]).max():.0f}/{np.abs(d['setpoint[1]'][:io]).max():.0f} dps (ANGLE leveling demand)")

#!/usr/bin/env python3
"""ADRC-021 qualitative ESO model-residual cross-check: regress the
observer's z3 (roll, debug[2]*16) on the applied control u. If
b0_eff = b0*scale were exactly right, z3 would be uncorrelated with u; a
negative slope means the ESO over-estimates its control authority
(b0_eff > b0_true).

NOT an independent plant-gain estimate - it reuses the same u, gyro and b0
law as identify_b0.py. Windowing matches identify_b0.py's length, overlap,
gate, no-clip and u-RMS criteria, but does NOT apply its R^2 >= 0.5 /
positive-slope selection (plus it drops debug-railed windows). ESO bandwidth
attenuates the fast component of z3, so slopes under-measure
|b0_true - b0_eff|; sign and trend are the payload.

Run from this directory after decoding the .bbl files.
"""
import csv as csvmod
import numpy as np
from scipy.signal import butter, filtfilt

Z3SCALE = 16.0
LOGS = [("btfl_001_p1_roll_doublets.01.csv", "001r", 2000),
        ("btfl_006_p1_chops_and_playing.01.csv", "006r", 2000),
        ("btfl_010_p1_playing.01.csv", "010r", 2000)]

def load(path):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", "axisP[0]", "axisI[0]", "axisD[0]", "debug[2]", "debug[7]",
            "motor[0]", "motor[1]", "motor[2]", "motor[3]"]
    d = np.genfromtxt(path, delimiter=",", skip_header=1,
                      usecols=[idx[c] for c in cols])
    return {c: d[:, k] for k, c in enumerate(cols)}

def main():
    print(f"{'log':<6} {'coll bin':>9} {'n':>4} {'slope z3~u':>10} {'b0_eff med':>10}")
    for fname, tag, b0base in LOGS:
        d = load(fname)
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1 / np.median(np.diff(t))
        u = np.clip(d["axisP[0]"] + d["axisI[0]"] + d["axisD[0]"], -500, 500)
        z3 = d["debug[2]"] * Z3SCALE
        railed = np.abs(d["debug[2]"]) >= 32700
        gate = d["debug[7]"] > 0
        scale = np.abs(d["debug[7]"]) / 100.0
        motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
        coll = (motors.mean(axis=0) - 48) / (2047 - 48) * 100
        noclip = (motors.min(axis=0) > 60) & (motors.max(axis=0) < 1950)
        bl, al = butter(2, 25 / (fs / 2), "low")
        bh, ah = butter(2, 1.5 / (fs / 2), "high")
        ub = filtfilt(bh, ah, filtfilt(bl, al, u))
        z3b = filtfilt(bh, ah, filtfilt(bl, al, z3))
        win = int(0.4 * fs)
        rows = []
        for s in range(0, len(t) - win, win // 2):
            sl = slice(s, s + win)
            if not (gate[sl].all() and noclip[sl].all()) or railed[sl].any():
                continue
            if ub[sl].std() < 8:
                continue
            den = np.dot(ub[sl] - ub[sl].mean(), ub[sl] - ub[sl].mean())
            slope = np.dot(ub[sl] - ub[sl].mean(), z3b[sl] - z3b[sl].mean()) / den
            rows.append((coll[sl].mean(), slope, b0base * scale[sl].mean()))
        rows = np.array(rows)
        for lo, hi in [(10, 16), (18, 27), (30, 40), (40, 60)]:
            m = (rows[:, 0] >= lo) & (rows[:, 0] < hi)
            if m.sum() < 3:
                continue
            print(f"{tag:<6} {lo:>4}-{hi:<4} {int(m.sum()):>4} {np.median(rows[m,1]):>10.0f} "
                  f"{np.median(rows[m,2]):>10.0f}")

if __name__ == "__main__":
    main()

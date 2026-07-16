#!/usr/bin/env python3
"""ADRC-021: identify the plant gain b0 vs collective from the doublet flights.

Model (matches adrc.c at 35adbf14e6 / eda3bb16eb):
    omega_ddot = f + b0_true(collective) * u,   u = constrain(pidSum, +-500)
The ESO uses b0_eff = adrc_b0 * scale, scale = min((collective/hover)^2, 3)
(collective = ~80 ms low-passed mixer collective, hover = adrc_hover_throttle).

Estimator: in short windows with real stick excitation and no motor clipping,
band-limit both u and the measured omega_ddot (double gradient of low-passed
gyro) to 1.5-25 Hz and take the OLS slope b0_hat = cov/var. f is rejected by
the high-pass; motor-lag phase bias is bounded by the 25 Hz low-pass. Windows
are binned by collective; the law verdict compares median b0_hat per bin
against the candidate laws (fixed, linear, quadratic+cap).

Usage: identify_b0.py <csv> <axis 0|1> [label]
Output: one line per accepted window (collective%, b0_hat, R2), then bin table.
"""
import csv as csvmod
import sys
import numpy as np
from scipy.signal import butter, filtfilt

PIDSUM_LIMIT = 500.0
WIN_S = 0.4
HOP_FRAC = 0.5
HP_HZ = 1.5          # rejects f drift (z3 dynamics live below ~1 Hz at steady stick)
LP_HZ = 25.0         # keeps doublet band, bounds motor-lag phase bias
MIN_U_RMS = 8.0      # pidSum units of band-limited excitation, else skip window
MIN_R2 = 0.5
MOTOR_LO, MOTOR_HI = 60, 1950   # clipping guard (motorOutput 48..2047)

def load(path, axis):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", f"setpoint[{axis}]", f"gyroADC[{axis}]",
            f"axisP[{axis}]", f"axisI[{axis}]", f"axisD[{axis}]",
            "rcCommand[3]", "debug[7]",
            "motor[0]", "motor[1]", "motor[2]", "motor[3]"]
    data = np.genfromtxt(path, delimiter=",", skip_header=1,
                         usecols=[idx[c] for c in cols])
    return {c: data[:, k] for k, c in enumerate(cols)}

def bandpass(x, fs):
    bl, al = butter(2, LP_HZ / (fs / 2), "low")
    bh, ah = butter(2, HP_HZ / (fs / 2), "high")
    return filtfilt(bh, ah, filtfilt(bl, al, x))

def identify(path, axis, label):
    d = load(path, axis)
    t = d["time (us)"] * 1e-6
    t -= t[0]
    fs = 1.0 / np.median(np.diff(t))
    gate_open = d["debug[7]"] > 0
    u = np.clip(d[f"axisP[{axis}]"] + d[f"axisI[{axis}]"] + d[f"axisD[{axis}]"],
                -PIDSUM_LIMIT, PIDSUM_LIMIT)
    motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    # mixer-collective proxy in %, same quantity the b0 schedule low-passes
    coll = (motors.mean(axis=0) - 48.0) / (2047.0 - 48.0) * 100.0
    no_clip = (motors.min(axis=0) > MOTOR_LO) & (motors.max(axis=0) < MOTOR_HI)

    bl, al = butter(2, LP_HZ / (fs / 2), "low")
    gyro_lp = filtfilt(bl, al, d[f"gyroADC[{axis}]"])
    om_ddot = np.gradient(np.gradient(gyro_lp, t), t)
    om_ddot_b = bandpass(om_ddot, fs)
    u_b = bandpass(u, fs)

    win = int(WIN_S * fs)
    hop = int(win * HOP_FRAC)
    rows = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if not (gate_open[sl].all() and no_clip[sl].all()):
            continue
        ub, yb = u_b[sl], om_ddot_b[sl]
        u_rms = ub.std()
        if u_rms < MIN_U_RMS:
            continue
        slope = np.dot(ub - ub.mean(), yb - yb.mean()) / np.dot(ub - ub.mean(), ub - ub.mean())
        resid = (yb - yb.mean()) - slope * (ub - ub.mean())
        r2 = 1.0 - resid.var() / yb.var() if yb.var() > 0 else 0.0
        if r2 < MIN_R2 or slope <= 0:
            continue
        rows.append((t[s] + WIN_S / 2, coll[sl].mean(), slope, r2, u_rms))
    return fs, rows

def main():
    path, axis = sys.argv[1], int(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else path
    fs, rows = identify(path, axis, label)
    print(f"### {label} axis={axis} fs={fs:.0f} Hz, accepted windows: {len(rows)}")
    print(f"{'t(s)':>7} {'coll%':>6} {'b0_hat':>8} {'R2':>5} {'uRMS':>6}")
    for r in rows:
        print(f"{r[0]:7.1f} {r[1]:6.1f} {r[2]:8.0f} {r[3]:5.2f} {r[4]:6.1f}")
    if not rows:
        return
    arr = np.array([(r[1], r[2]) for r in rows])
    print("\n--- bins (mixer-collective %) ---")
    print(f"{'bin':>9} {'n':>4} {'b0_hat med':>10} {'p25':>8} {'p75':>8}")
    for lo in range(10, 70, 5):
        m = (arr[:, 0] >= lo) & (arr[:, 0] < lo + 5)
        if m.sum() < 3:
            continue
        q25, med, q75 = np.percentile(arr[m, 1], [25, 50, 75])
        print(f"{lo:>4}-{lo+5:<4} {m.sum():>4} {med:>10.0f} {q25:>8.0f} {q75:>8.0f}")

if __name__ == "__main__":
    main()

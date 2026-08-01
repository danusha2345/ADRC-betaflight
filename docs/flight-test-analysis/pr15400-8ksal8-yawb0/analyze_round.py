#!/usr/bin/env python3
"""Read-only screening of the 2026-07-30/31 ADRC logs (8ksal8 + Pavel_M. part 2).

Usage: python3 analyze_round.py <decoded.csv> [<decoded.csv> ...]

Metrics are deliberately the same family used in the earlier b5 write-ups:
collective from the motor mean (not the stick), gyroUnfilt (already deg/s),
debug[7] for gate/b0-scale, and band-limited RMS for the "chatter" claims.
"""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

COLS = [
    "time (us)", "rcCommand[3]", "vbatLatest (V)",
    "axisI[0]", "axisI[1]", "axisI[2]",
    "setpoint[0]", "setpoint[1]", "setpoint[2]",
    "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
    "accSmooth[0] (g)", "accSmooth[1] (g)", "accSmooth[2] (g)",
    "debug[2]", "debug[5]", "debug[6]", "debug[7]",
    "motor[0]", "motor[1]", "motor[2]", "motor[3]",
]
AXES = ("roll", "pitch", "yaw")


def headers(path):
    hp = path.with_suffix("").with_suffix("")
    hp = path.parent / (path.name[:-4] + ".headers.csv")
    out = {}
    if hp.exists():
        for row in csv.reader(hp.open()):
            if len(row) >= 2:
                out[row[0]] = row[1]
    return out


def loadcols(path):
    with path.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    missing = [n for n in COLS if n not in idx]
    if missing:
        raise RuntimeError(f"{path}: missing {missing}")
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in COLS], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    return {n: arr[:, i] for i, n in enumerate(COLS)}


def band_rms(x, fs, lo, hi):
    """RMS of x restricted to [lo, hi] Hz."""
    hi = min(hi, fs / 2 * 0.98)
    if hi <= lo:
        return float("nan")
    sos = butter(2, [lo, hi], btype="bandpass", fs=fs, output="sos")
    return float(np.sqrt(np.mean(sosfiltfilt(sos, x) ** 2)))


def lag_ms(setpoint, gyro, fs, max_ms=120):
    """Cross-correlation lag of gyro behind setpoint, in ms."""
    a = setpoint - setpoint.mean()
    b = gyro - gyro.mean()
    if np.std(a) < 1e-6 or np.std(b) < 1e-6:
        return float("nan")
    n = int(max_ms * 1e-3 * fs)
    corr = np.correlate(b, a, mode="full")
    mid = len(a) - 1
    seg = corr[mid: mid + n + 1]
    return float(np.argmax(seg) / fs * 1000)


def analyze(path):
    path = Path(path)
    h = headers(path)
    lo, hi = (int(v) for v in h.get("motorOutput", "48,1847").split(","))
    d = loadcols(path)
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    collective = (motors.mean(axis=0) - lo) / (hi - lo) * 100
    scale = np.abs(d["debug[7]"]) / 100
    gate = d["debug[7]"] > 0
    active = gate & (collective > 12)
    saturated = motors.max(axis=0) >= hi
    gyro = np.vstack([d[f"gyroUnfilt[{i}]"] for i in range(3)])
    setp = np.vstack([d[f"setpoint[{i}]"] for i in range(3)])
    acc = np.vstack([d[f"accSmooth[{i}] (g)"] for i in range(3)])
    acc_norm = np.sqrt((acc ** 2).sum(axis=0))
    z3 = np.vstack([d["debug[2]"], d["debug[5]"], d["debug[6]"]])

    tune = "wc %s wo %s b0 %s law %s hover %s" % (
        h.get("adrcWC"), h.get("adrcWO"), h.get("adrcB0"),
        h.get("adrc_b0_law"), h.get("adrc_hover_throttle"))
    print(f"\n=== {path.name} ===")
    print(f"  {tune}; vbatref {h.get('vbatref')}; motorOutput {lo}-{hi}")
    print(f"  dur {t[-1]:.1f} s, fs {fs:.0f} Hz, gate {gate.mean()*100:.0f} %, "
          f"active {active.sum()/fs:.1f} s, saturation {saturated[active].mean()*100:.2f} %")
    if active.sum() < fs * 2:
        print("  (too little active time)")
        return

    print(f"  collective med/p90 {np.median(collective[active]):.1f}/"
          f"{np.percentile(collective[active],90):.1f} %, "
          f"b0scale med/p90/max {np.median(scale[active]):.2f}/"
          f"{np.percentile(scale[active],90):.2f}/{scale[active].max():.2f}, "
          f"vbat med {np.median(d['vbatLatest (V)'][active]):.2f} V")

    # calm hover windows: measured hover collective
    win, hop = int(fs), max(1, int(0.25 * fs))
    calm = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if not active[sl].all() or saturated[sl].any():
            continue
        if np.max(np.abs(setp[:, sl])) >= 35 or np.max(np.abs(gyro[:, sl])) >= 80:
            continue
        if abs(np.median(acc_norm[sl]) - 1.0) > 0.25:
            continue
        calm.append((np.median(collective[sl]), np.median(d["vbatLatest (V)"][sl])))
    if calm:
        c = np.asarray(calm)
        print(f"  calm-hover windows {len(c)}: collective med {np.median(c[:,0]):.1f} % "
              f"(p10 {np.percentile(c[:,0],10):.1f}, p90 {np.percentile(c[:,0],90):.1f}), "
              f"vbat med {np.median(c[:,1]):.2f} V")
    else:
        print("  calm-hover windows: none")

    # band-limited activity on the active phase
    # |I| = |z3/b0| is the b0-independent view of the same state; the debug
    # z3 field is /16 and rails at 32767, i.e. |z3| >= 524k, which a larger b0
    # reaches on its own (z3 absorbs the b0*u model error), so compare on I.
    iterm = np.vstack([d[f"axisI[{i}]"] for i in range(3)])
    ilim = (float(h.get("pidsum_limit", 500)), float(h.get("pidsum_limit", 500)),
            float(h.get("pidsum_limit_yaw", 400)))
    for a in range(3):
        g = gyro[a, active]
        ia = np.abs(iterm[a, active])
        print(f"  {AXES[a]:5s} gyro RMS {np.sqrt(np.mean(g**2)):6.1f} dps | "
              f"HF 20-80 {band_rms(g, fs, 20, 80):5.1f} | "
              f"80-250 {band_rms(g, fs, 80, 250):5.1f} | "
              f"z3 dbg-rail {np.mean(np.abs(z3[a, active]) >= 32700)*100:5.2f} % | "
              f"|I| p95 {np.percentile(ia, 95):5.0f} max {ia.max():5.0f} "
              f"(at limit {np.mean(ia >= ilim[a]-0.5)*100:5.2f} %)")
    m = motors[:, active].mean(axis=0)
    print(f"  motor-mean HF 20-80 {band_rms(m, fs, 20, 80):.1f} | "
          f"80-250 {band_rms(m, fs, 80, 250):.1f} (units of {hi-lo} span)")

    # tracking on commanded segments
    lp = butter(2, 15, btype="lowpass", fs=fs, output="sos")
    for a in range(3):
        cmd = active & (np.abs(setp[a]) > 50) & (acc_norm < 3)
        if cmd.sum() < fs:
            print(f"  {AXES[a]:5s} tracking: n/a")
            continue
        g_lp = sosfiltfilt(lp, gyro[a])
        s_lp = sosfiltfilt(lp, setp[a])
        err = g_lp[cmd] - s_lp[cmd]
        gain = np.std(g_lp[cmd]) / np.std(s_lp[cmd])
        print(f"  {AXES[a]:5s} tracking: n={cmd.sum()/fs:5.1f} s, "
              f"errRMS {np.sqrt(np.mean(err**2)):6.1f} dps "
              f"({np.sqrt(np.mean(err**2))/np.std(s_lp[cmd])*100:4.0f} % of cmd sd), "
              f"gain {gain:.2f}, lag {lag_ms(s_lp[cmd], g_lp[cmd], fs):.0f} ms")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        try:
            analyze(p)
        except Exception as exc:  # keep going through the batch
            print(f"\n=== {p} === FAILED: {exc}")

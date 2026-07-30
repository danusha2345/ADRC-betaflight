#!/usr/bin/env python3
"""Read-only screening of Pavel_M.'s 2026-07-30 Discord Blackbox logs."""

import csv
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt


ROOT = Path(__file__).resolve().parent
LOGS = [
    {
        "name": "AIR65.01",
        "path": ROOT / "decoded-air65/AIR65_tune_30_120_6400.01.csv",
        "motor": (48, 1847),
        "hover": 35.0,
        "tune": "wc 30/30/30, wo 120/120/100, b0 6400/6400/6400, SQRT",
    },
    {
        "name": "AIR65.02",
        "path": ROOT / "decoded-air65/AIR65_tune_30_120_6400.02.csv",
        "motor": (48, 1847),
        "hover": 35.0,
        "tune": "wc 30/30/30, wo 120/120/100, b0 6400/6400/6400, SQRT",
    },
    {
        "name": "METEOR75.01",
        "path": ROOT / "decoded-meteor75/METEOR75_tune_60_100_4000.01.csv",
        "motor": (48, 1847),
        "hover": 40.0,
        "tune": "wc 30/30/30, wo 120/120/100, b0 6400/6400/6400, SQRT",
    },
    {
        "name": "METEOR75.02",
        "path": ROOT / "decoded-meteor75/METEOR75_tune_60_100_4000.02.csv",
        "motor": (48, 1847),
        "hover": 40.0,
        "tune": "wc 30/30/30, wo 120/120/100, b0 4800/4800/4800, SQRT",
    },
]

COLS = [
    "time (us)",
    "rcCommand[3]",
    "vbatLatest (V)",
    "setpoint[0]",
    "setpoint[1]",
    "setpoint[2]",
    "axisI[0]",
    "axisI[1]",
    "axisI[2]",
    "gyroUnfilt[0]",
    "gyroUnfilt[1]",
    "gyroUnfilt[2]",
    "accSmooth[0] (g)",
    "accSmooth[1] (g)",
    "accSmooth[2] (g)",
    "debug[2]",
    "debug[5]",
    "debug[6]",
    "debug[7]",
    "motor[0]",
    "motor[1]",
    "motor[2]",
    "motor[3]",
]

AXES = ("roll", "pitch", "yaw")


def loadcols(path):
    with path.open() as f:
        header = [h.strip() for h in next(csv.reader(f))]
    index = {name: i for i, name in enumerate(header)}
    missing = [name for name in COLS if name not in index]
    if missing:
        raise RuntimeError(f"{path}: missing {missing}")
    arr = np.genfromtxt(
        path,
        delimiter=",",
        skip_header=1,
        usecols=[index[name] for name in COLS],
        invalid_raise=False,
    )
    good = ~np.isnan(arr).any(axis=1)
    arr = arr[good]
    return {name: arr[:, i] for i, name in enumerate(COLS)}


def moving_average(x, count):
    count = max(1, int(count))
    if count == 1:
        return x.copy()
    kernel = np.ones(count) / count
    return np.convolve(x, kernel, mode="same")


def tone(x, fs, low=10.0, high=100.0):
    window = np.hanning(len(x))
    spectrum = np.fft.rfft((x - np.mean(x)) * window)
    freq = np.fft.rfftfreq(len(x), 1 / fs)
    psd = np.abs(spectrum) ** 2 / (fs * np.sum(window**2))
    band = (freq >= low) & (freq <= high)
    if not np.any(band):
        return 0.0, 0.0, 0.0
    masked = np.where(band, psd, -1)
    peak = int(np.argmax(masked))
    df = freq[1] - freq[0]
    around = (freq >= freq[peak] - 2) & (freq <= freq[peak] + 2)
    total_band = (freq >= 5) & (freq <= 150)
    tone_rms = np.sqrt(np.sum(psd[around]) * df * 2)
    total_rms = np.sqrt(np.sum(psd[total_band]) * df * 2)
    fraction = tone_rms / total_rms if total_rms else 0.0
    return float(freq[peak]), float(tone_rms), float(fraction)


def contiguous(mask, max_gap):
    indices = np.flatnonzero(mask)
    if not len(indices):
        return []
    groups = []
    start = prev = int(indices[0])
    for value in indices[1:]:
        value = int(value)
        if value - prev > max_gap:
            groups.append((start, prev + 1))
            start = value
        prev = value
    groups.append((start, prev + 1))
    return groups


def analyze(cfg):
    d = loadcols(cfg["path"])
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    motor_low, motor_high = cfg["motor"]
    collective = (motors.mean(axis=0) - motor_low) / (motor_high - motor_low) * 100
    throttle = (d["rcCommand[3]"] - 1000) / 10
    scale = np.abs(d["debug[7]"]) / 100
    gate = d["debug[7]"] > 0
    active = gate & (collective > 12)
    saturated = motors.max(axis=0) >= motor_high
    gyro_unfilt = np.vstack([d[f"gyroUnfilt[{i}]"] for i in range(3)])
    # gyroUnfilt is already in deg/s and agrees with the established b5
    # analysis pipeline. Do not request --unit-rotation: current decoder
    # conversion overflows gyroADC in these G47X logs.
    gyro = gyro_unfilt
    setpoint = np.vstack([d[f"setpoint[{i}]"] for i in range(3)])
    error = gyro - setpoint
    lowpass = butter(2, 15, btype="lowpass", fs=fs, output="sos")
    gyro_lp = sosfiltfilt(lowpass, gyro, axis=1)
    setpoint_lp = sosfiltfilt(lowpass, setpoint, axis=1)
    error_lp = gyro_lp - setpoint_lp
    acc = np.vstack([d[f"accSmooth[{i}] (g)"] for i in range(3)])
    acc_norm = np.sqrt(np.sum(acc**2, axis=0))
    z3_debug = np.vstack([d["debug[2]"], d["debug[5]"], d["debug[6]"]])
    iterm = np.vstack([d[f"axisI[{i}]"] for i in range(3)])

    print(f"\n=== {cfg['name']} ===")
    print(cfg["tune"])
    print(
        f"duration {t[-1]:.2f} s, fs {fs:.1f} Hz, gate-positive "
        f"{gate.mean() * 100:.1f} %, active {active.sum() / fs:.2f} s"
    )
    if active.any():
        print(
            "active collective med/p90/max "
            f"{np.median(collective[active]):.1f}/"
            f"{np.percentile(collective[active], 90):.1f}/"
            f"{np.max(collective[active]):.1f} %, "
            "stick med/p90/max "
            f"{np.median(throttle[active]):.1f}/"
            f"{np.percentile(throttle[active], 90):.1f}/"
            f"{np.max(throttle[active]):.1f} %"
        )
        print(
            f"b0 scale med/p90/max {np.median(scale[active]):.2f}/"
            f"{np.percentile(scale[active], 90):.2f}/{np.max(scale[active]):.2f}; "
            f"any motor at exact upper rail {saturated[active].mean() * 100:.3f} %"
        )
        print(
            "z3 debug-rail fraction R/P/Y "
            + "/".join(
                f"{(np.abs(z3_debug[i, active]) >= 32700).mean() * 100:.2f} %"
                for i in range(3)
            )
        )
        print(
            "published |I| p95/max R/P/Y "
            + "/".join(
                f"{np.percentile(np.abs(iterm[i, active]), 95):.0f}/"
                f"{np.max(np.abs(iterm[i, active])):.0f}"
                for i in range(3)
            )
        )
        limits = (500.0, 500.0, 400.0)
        print(
            "published I at controller limit R/P/Y "
            + "/".join(
                f"{np.mean(np.abs(iterm[i, active]) >= limits[i] - 0.5) * 100:.3f} %"
                for i in range(3)
            )
        )
        analysis_mask = (
            active
            & (acc_norm < 3)
            & (t > 1)
            & (t < t[-1] - 1)
        )
        print("15 Hz low-pass, quiet-command response (impact/endpoints excluded):")
        for axis in range(3):
            quiet = analysis_mask & (
                moving_average(np.abs(setpoint_lp[axis]), int(0.2 * fs)) < 20
            )
            if quiet.sum() < int(fs):
                continue
            print(
                f"  {AXES[axis]:5s}: n={quiet.sum() / fs:5.1f} s, "
                f"gyro RMS/p95 {np.sqrt(np.mean(gyro_lp[axis, quiet] ** 2)):5.1f}/"
                f"{np.percentile(np.abs(gyro_lp[axis, quiet]), 95):5.1f} dps, "
                f"|gyro|>40 {np.mean(np.abs(gyro_lp[axis, quiet]) > 40) * 100:5.1f} %"
            )

    # Calm one-second windows: used for measured hover and narrow-line scan.
    win = int(fs)
    hop = max(1, int(0.25 * fs))
    calm_rows = []
    rings = []
    for start in range(0, len(t) - win, hop):
        sl = slice(start, start + win)
        if not active[sl].all() or saturated[sl].any():
            continue
        if np.max(np.abs(setpoint[:, sl])) >= 35:
            continue
        if np.max(np.abs(gyro[:, sl])) >= 80:
            continue
        row = (
            t[start],
            np.median(collective[sl]),
            np.median(throttle[sl]),
            np.median(d["vbatLatest (V)"][sl]),
            np.median(scale[sl]),
            np.sqrt(np.mean(error[:, sl] ** 2)),
        )
        calm_rows.append(row)
        for axis in range(3):
            frequency, amplitude, fraction = tone(gyro_unfilt[axis, sl], fs)
            if amplitude > 5 and fraction > 0.5:
                rings.append(
                    (amplitude, frequency, fraction, t[start], AXES[axis])
                )

    if calm_rows:
        rows = np.asarray(calm_rows)
        print(
            f"calm-hover windows {len(rows)}: collective med/IQR "
            f"{np.median(rows[:, 1]):.1f}/"
            f"{np.percentile(rows[:, 1], 25):.1f}-"
            f"{np.percentile(rows[:, 1], 75):.1f} %, "
            f"stick med {np.median(rows[:, 2]):.1f} %, "
            f"vbat med {np.median(rows[:, 3]):.2f} V, "
            f"scale med {np.median(rows[:, 4]):.2f}"
        )
        print(
            f"calm tracking-error RMS median/p90 "
            f"{np.median(rows[:, 5]):.1f}/{np.percentile(rows[:, 5], 90):.1f} dps"
        )
    else:
        print("calm-hover windows: none under strict 1 s criterion")

    if rings:
        rings.sort(reverse=True)
        strong = [row for row in rings if row[0] > 10]
        print(
            f"calm narrow-line windows >5 dps: {len(rings)} "
            f"(>10 dps: {len(strong)}); top:"
        )
        for amplitude, frequency, fraction, start, axis in rings[:6]:
            print(
                f"  t={start:6.2f} {axis:5s} {frequency:5.1f} Hz "
                f"{amplitude:5.1f} dps, fraction {fraction:.2f}"
            )
    else:
        print("calm narrow-line windows: none")

    # Find large stick-throttle moves and measure pitch/yaw response/error.
    thr_smooth = moving_average(throttle, int(0.05 * fs))
    span = int(0.15 * fs)
    delta = np.zeros_like(thr_smooth)
    delta[span:-span] = thr_smooth[2 * span :] - thr_smooth[: -2 * span]
    candidates = np.flatnonzero(active & (np.abs(delta) >= 15))
    transitions = []
    last = -10 * int(fs)
    for index in candidates:
        if index - last < int(0.6 * fs):
            if transitions and abs(delta[index]) > abs(delta[transitions[-1]]):
                transitions[-1] = int(index)
                last = int(index)
            continue
        transitions.append(int(index))
        last = int(index)
    print(f"throttle transitions >=15 points/0.30 s: {len(transitions)}")
    transition_rows = []
    for index in transitions:
        start = max(0, index - int(0.10 * fs))
        end = min(len(t), index + int(0.60 * fs))
        sl = slice(start, end)
        row = {
            "t": t[index],
            "delta": delta[index],
            "spmax": np.max(np.abs(setpoint[:, sl]), axis=1),
            "gmax": np.max(np.abs(gyro_lp[:, sl]), axis=1),
            "emax": np.max(np.abs(error_lp[:, sl]), axis=1),
            "scale0": scale[start],
            "scale1": scale[end - 1],
        }
        transition_rows.append(row)
    transition_rows.sort(
        key=lambda row: max(row["emax"][1], row["emax"][2]), reverse=True
    )
    for row in transition_rows[:8]:
        print(
            f"  t={row['t']:6.2f} dThr={row['delta']:+5.1f}: "
            f"pitch gyro/sp/err {row['gmax'][1]:.0f}/{row['spmax'][1]:.0f}/"
            f"{row['emax'][1]:.0f}, yaw {row['gmax'][2]:.0f}/"
            f"{row['spmax'][2]:.0f}/{row['emax'][2]:.0f}, "
            f"scale {row['scale0']:.2f}->{row['scale1']:.2f}"
        )

    # Strict uncommanded candidates: quiet pitch/yaw setpoint before and during
    # a rate burst. Group nearby samples and integrate the actual gyro rate.
    quiet_count = int(0.20 * fs)
    sp_quiet_pitch = moving_average(np.abs(setpoint_lp[1]), quiet_count) < 20
    sp_quiet_yaw = moving_average(np.abs(setpoint_lp[2]), quiet_count) < 20
    for axis, quiet in ((1, sp_quiet_pitch), (2, sp_quiet_yaw)):
        mask = (
            active
            & quiet
            & (acc_norm < 3)
            & (t > 1)
            & (t < t[-1] - 1)
            & (np.abs(gyro_lp[axis]) > 40)
        )
        events = []
        for start, end in contiguous(mask, max_gap=int(0.08 * fs)):
            lo = max(0, start - int(0.05 * fs))
            hi = min(len(t), end + int(0.05 * fs))
            if t[hi - 1] - t[lo] < 0.04:
                continue
            peak_index = lo + int(np.argmax(np.abs(gyro_lp[axis, lo:hi])))
            rotation = np.trapezoid(gyro_lp[axis, lo:hi], t[lo:hi])
            nearest_transition = (
                min((abs(t[peak_index] - t[i]) for i in transitions), default=999)
            )
            events.append(
                (
                    abs(rotation),
                    t[lo],
                    t[hi - 1],
                    gyro_lp[axis, peak_index],
                    setpoint_lp[axis, peak_index],
                    rotation,
                    nearest_transition,
                    np.max(acc_norm[lo:hi]),
                )
            )
        events.sort(reverse=True)
        print(f"strict uncommanded {AXES[axis]} candidates: {len(events)}")
        for (
            _,
            start,
            end,
            peak,
            sp_at_peak,
            rotation,
            near_thr,
            acc_peak,
        ) in events[:8]:
            print(
                f"  t={start:6.2f}-{end:6.2f} peak {peak:+6.0f} dps "
                f"(sp {sp_at_peak:+5.0f}), integral {rotation:+5.1f} deg, "
                f"nearest throttle transition {near_thr:.2f} s, "
                f"acc max {acc_peak:.2f} g"
            )

    # Broad impact/saturation context.
    print(
        f"acc norm max/p99.9 {np.max(acc_norm):.2f}/"
        f"{np.percentile(acc_norm, 99.9):.2f} g; "
        f"gyro max R/P/Y "
        + "/".join(f"{np.max(np.abs(gyro[i])):.0f}" for i in range(3))
        + " dps"
    )


def main():
    for cfg in LOGS:
        analyze(cfg)


if __name__ == "__main__":
    main()

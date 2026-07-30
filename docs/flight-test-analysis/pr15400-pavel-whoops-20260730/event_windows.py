#!/usr/bin/env python3
"""Compact event tables for the strongest pitch/yaw excursions."""

import importlib.util
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pavel", HERE / "analyze_pavel.py")
pavel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pavel)

WINDOWS = {
    "AIR65.02": [(8.1, 10.0), (11.5, 13.6)],
    "METEOR75.01": [(2.2, 7.7), (47.4, 52.4)],
    "METEOR75.02": [(19.0, 22.1), (69.8, 71.6), (112.0, 117.5)],
}


def report(cfg, ranges):
    d = pavel.loadcols(cfg["path"])
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    gyro = np.vstack([d[f"gyroUnfilt[{axis}]"] for axis in range(3)])
    sp = np.vstack([d[f"setpoint[{axis}]"] for axis in range(3)])
    iterm = np.vstack([d[f"axisI[{axis}]"] for axis in range(3)])
    throttle = (d["rcCommand[3]"] - 1000) / 10
    scale = np.abs(d["debug[7]"]) / 100
    filt = butter(2, 15, btype="lowpass", fs=fs, output="sos")
    gyro = sosfiltfilt(filt, gyro, axis=1)
    sp = sosfiltfilt(filt, sp, axis=1)

    print(f"\n=== {cfg['name']} ===")
    for begin, finish in ranges:
        print(f"window {begin:.1f}..{finish:.1f} s")
        print("  t   thr scl | spP   gyP   I_P | spY   gyY   I_Y")
        step = int(0.2 * fs)
        first = int(np.searchsorted(t, begin))
        last = int(np.searchsorted(t, finish))
        for start in range(first, last, step):
            end = min(start + step, last)
            sl = slice(start, end)
            print(
                f"{np.mean(t[sl]):5.2f} "
                f"{np.median(throttle[sl]):4.0f} {np.median(scale[sl]):3.2f} | "
                f"{np.mean(sp[1, sl]):+4.0f} {np.mean(gyro[1, sl]):+5.0f} "
                f"{np.mean(iterm[1, sl]):+5.0f} | "
                f"{np.mean(sp[2, sl]):+4.0f} {np.mean(gyro[2, sl]):+5.0f} "
                f"{np.mean(iterm[2, sl]):+5.0f}"
            )


def main():
    by_name = {cfg["name"]: cfg for cfg in pavel.LOGS}
    for name, ranges in WINDOWS.items():
        report(by_name[name], ranges)


if __name__ == "__main__":
    main()

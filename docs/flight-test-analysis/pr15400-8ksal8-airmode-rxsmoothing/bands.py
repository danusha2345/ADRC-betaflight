#!/usr/bin/env python3
"""Wide-band motor-spectrum tables used from the 2026-09-13 addendum onward.

Usage: bands.py <decoded.csv> [...]   (blackbox_decode --unit-flags raw; the .bbl must sit next to the .csv)

For each log, after the liftoff gate first opens:
  * the strongest peak over 10-150 Hz (the earlier scripts searched 40-80 Hz and missed modes outside it);
  * per-motor RMS over mean motor output in fixed bands, whole flight and per 1-s window (median, p90, share of
    windows above 5 %), so an intermittent mode is not hidden by an average;
  * the same statistic on windows with no motor at 2047 and a median stick throttle inside a chosen range;
  * the b0 throttle scale actually in force (debug[7]/100, sign carries the gate state) - note the schedule keys on a
    2 Hz low-pass of the APPLIED collective, so this is not a function of stick throttle;
  * worst-axis gyro RMS in the band against setpoint RMS in the same band.
"""
import re
import sys

import numpy as np
from scipy.signal import welch

BANDS = [(10, 25), (25, 38), (38, 55), (55, 70), (70, 90), (90, 120)]


def headers(bbl):
    data = open(bbl, "rb").read(300000)
    out = {}
    for m in re.finditer(rb"H ([^:\n]+):([^\n]*)\n", data):
        out.setdefault(m.group(1).decode(errors="ignore"), m.group(2).decode(errors="ignore").strip())
    return out


def load(path):
    import csv
    with open(path) as fh:
        rd = csv.reader(fh)
        names = [c.strip().split(" ")[0] for c in next(rd)]
        rows = [r for r in rd if len(r) == len(names)]
    out = {}
    for name, col in zip(names, zip(*rows)):
        try:
            out[name] = np.array([x.strip() for x in col], dtype=float)
        except ValueError:
            pass
    return out


def band_rms(segments, fs, lo, hi, nperseg=None):
    vals = []
    for x in segments:
        n = nperseg or min(len(x), int(fs * 2))
        f, p = welch(x - x.mean(), fs=fs, nperseg=n)
        sel = (f >= lo) & (f <= hi)
        vals.append(np.sqrt(np.trapezoid(p[sel], f[sel])))
    return float(np.mean(vals))


def main(paths, thr_lo=42.0, thr_hi=50.0, window_s=1.0):
    for csv_path in paths:
        bbl = csv_path.split(".01.csv")[0] + ".bbl"
        h, d = headers(bbl), load(csv_path)
        t = d["time"] * 1e-6
        fs = 1.0 / np.median(np.diff(t))
        # The gate is bit 0 of adrcState; logs without the field fall back to the sign of debug[7].
        lift = (d["adrcState"].astype(int) & 1) > 0 if "adrcState" in d else d["debug[7]"] > 0
        if not lift.any():
            print(f"{csv_path}: never left the ground")
            continue
        i0 = int(np.argmax(lift))
        motors = [d[f"motor[{k}]"] for k in range(4)]
        whole = [x[i0:] for x in motors]
        mean_out = float(np.mean([x.mean() for x in whole]))
        thr = (d["rcCommand[3]"] - 1000) / 10.0
        scale = d["debug[7]"] / 100.0
        f, p = welch(whole[0] - whole[0].mean(), fs=fs, nperseg=int(fs * 2))
        sel = (f >= 10) & (f <= 150)
        peak = f[sel][np.argmax(p[sel])]
        print(f"\n### {csv_path.split('/')[-1]}  law={h.get('adrc_b0_law')} floor={h.get('adrc_b0_scale_min')} "
              f"wc/wo={h.get('adrcWC')}/{h.get('adrcWO')} hover={h.get('adrc_hover_throttle')} fs={fs:.0f}")
        print(f"  strongest peak 10-150 Hz: {peak:.1f} Hz")
        n = int(window_s * fs)
        for lo, hi in BANDS:
            per_window, matched = [], []
            for s in range(i0, len(t) - n, n):
                seg = np.array([x[s:s + n] for x in motors])
                rms = band_rms(seg, fs, lo, hi, nperseg=n) / seg.mean() * 100
                per_window.append(rms)
                if not (seg >= 2047).any() and thr_lo <= np.median(thr[s:s + n]) <= thr_hi:
                    matched.append((rms, float(np.median(scale[s:s + n]))))
            per_window = np.array(per_window)
            whole_rms = band_rms(whole, fs, lo, hi) / mean_out * 100
            line = (f"  {lo:3d}-{hi:3d} Hz: whole {whole_rms:6.2f} %  windows med {np.median(per_window):6.2f} "
                    f"p90 {np.percentile(per_window, 90):6.2f}  >5 % in {int((per_window > 5).sum()):3d}/{len(per_window)}")
            if matched:
                m = np.array(matched)
                line += (f"  | matched thr {thr_lo:.0f}-{thr_hi:.0f} %, no rail: n={len(m):3d} "
                         f"med {np.median(m[:, 0]):5.2f} p90 {np.percentile(m[:, 0], 90):5.2f} scale {np.median(m[:, 1]):.2f}")
            print(line)
        for lo, hi in [(25, 38), (70, 90)]:
            gyro = [band_rms([d[f"gyroADC[{a}]"][i0:]], fs, lo, hi) for a in range(3)]
            sp = [band_rms([d[f"setpoint[{a}]"][i0:]], fs, lo, hi) for a in range(3)]
            ax = int(np.argmax(gyro))
            print(f"  {lo}-{hi} Hz worst axis {ax}: gyro RMS {gyro[ax]:.2f} deg/s vs setpoint RMS {sp[ax]:.2f}")
        rail = (np.array(whole) >= 2047).any(axis=0).mean() * 100
        amp = d["amperageLatest"][i0:]
        print(f"  rail frames {rail:.2f} %  mean current {amp.mean():.2f} A  p90 {np.percentile(amp, 90):.2f} A")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])

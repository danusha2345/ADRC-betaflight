#!/usr/bin/env python3
"""Per-log overview in the pr15400-8ksal8-th3/overview.py style, for b9 and b10.1 logs.

For each BBL next to its decoded .01.csv (and .01.rawflags.csv from --unit-flags raw):
tune headers, span, vbat, motor-rail samples, |setpoint - gyroADC| median/p90 per axis
over the whole log, z3 debug-rail share per axis, and the numeric mode-mask transitions.
"""
import csv
import glob
import re
import sys
import numpy as np

DEBUG_CLIP = 32767
ARM_BIT, ANGLE_BIT, AIR_BIT = 1 << 0, 1 << 1, 1 << 24
HKEYS = ["Firmware revision", "Craft name", "adrcWC", "adrcWO", "adrcB0", "adrc_hover_throttle",
         "adrc_liftoff_throttle", "adrc_b0_law", "adrc_gyro_lpf_hz", "pidsum_limit_yaw", "motorOutput",
         "rc_smoothing_rx_smoothed", "rc_smoothing_active_cutoffs_ff_sp_thr", "features", "adrc_z3_log_scale"]


def headers(bbl):
    data = open(bbl, "rb").read(300000)
    out = {}
    for m in re.finditer(rb"H ([^:\n]+):([^\n]*)\n", data):
        k = m.group(1).decode(errors="ignore")
        if k in HKEYS and k not in out:
            out[k] = m.group(2).decode(errors="ignore").strip()
    return out


def load(path):
    with open(path) as fh:
        rd = csv.reader(fh)
        names = [c.strip().split(" ")[0] for c in next(rd)]
        rows = [r for r in rd if len(r) == len(names)]
    d = {}
    for n, col in zip(names, zip(*rows)):
        try:
            d[n] = np.array([x.strip() for x in col], dtype=float)
        except ValueError:
            d[n] = np.array([x.strip() for x in col])
    return d


def mask_transitions(rawcsv):
    d = load(rawcsv)
    t = (d["time"] - d["time"][0]) / 1e6
    fm = d["flightModeFlags"].astype(int)
    out, prev = [], None
    for ti, v in zip(t, fm):
        if v != prev:
            out.append((ti, v))
            prev = v
    return out


def main(paths):
    for bbl in paths:
        h = headers(bbl)
        stem = bbl[:-4]
        d = load(stem + ".01.csv")
        t = (d["time"] - d["time"][0]) / 1e6
        m = np.vstack([d[f"motor[{i}]"] for i in range(4)])
        hi = float(h["motorOutput"].split(",")[1])
        med, p90 = [], []
        for ax in range(3):
            e = np.abs(d[f"setpoint[{ax}]"] - d[f"gyroADC[{ax}]"])
            med.append(np.median(e))
            p90.append(np.percentile(e, 90))
        n = len(t)
        clip = [100.0 * float((np.abs(d[f"debug[{i}]"]) >= DEBUG_CLIP).sum()) / n for i in (2, 5, 6)]
        vb = d["vbatLatest"]
        feats = int(h.get("features", "0"))
        tr = mask_transitions(stem + ".01.rawflags.csv")
        trtxt = "; ".join(f"{ti:6.2f}s->{v}" + ("+ANGLE" if v & ANGLE_BIT else "") + ("+AIR" if v & AIR_BIT else "")
                          for ti, v in tr[:5])
        print(f"## {bbl.split('/')[-1]}")
        print(f"   fw {h.get('Firmware revision','?')[:40]}  craft {h.get('Craft name','?')}  "
              f"wc {h.get('adrcWC')} wo {h.get('adrcWO')} b0 {h.get('adrcB0')} law {h.get('adrc_b0_law')} "
              f"hover {h.get('adrc_hover_throttle')}% liftoff {h.get('adrc_liftoff_throttle')}% adrc_lpf {h.get('adrc_gyro_lpf_hz')} "
              f"yawlim {h.get('pidsum_limit_yaw')} z3scale {h.get('adrc_z3_log_scale','n/a')}")
        print(f"   FEATURE_AIRMODE={'on' if feats & (1 << 22) else 'off'}  rx_smoothed {h.get('rc_smoothing_rx_smoothed')} Hz  "
              f"cutoffs {h.get('rc_smoothing_active_cutoffs_ff_sp_thr')}  modes: {trtxt}")
        print(f"   span {t[-1]:6.1f}s  vbat {vb.min():.2f}-{vb.max():.2f} (median {np.median(vb):.2f}) V  "
              f"motor-rail samples {int((m >= hi).sum())} ({100 * (m >= hi).any(axis=0).mean():.2f}% of frames)  "
              f"err med R/P/Y {'/'.join(f'{v:.0f}' for v in med)}  p90 {'/'.join(f'{v:.0f}' for v in p90)}  "
              f"z3 debug-rail R/P/Y {clip[0]:.1f}/{clip[1]:.1f}/{clip[2]:.1f} %")


if __name__ == "__main__":
    main(sys.argv[1:] or sorted(glob.glob("*/*.bbl")))

#!/usr/bin/env python3
"""Score ADRC tunes from blackbox takeoff logs (stdlib only, no dependencies).

Formalizes the tune-selection method proposed by @jmsweng in issue #1: record a
short takeoff + hover with each candidate tune, then compare the logs
quantitatively instead of eyeballing plots.

Usage:
  1. Decode each .bbl with blackbox_decode (https://github.com/betaflight/blackbox-tools):
       blackbox_decode "Take off, 30-100-200.bbl"
  2. Score the resulting CSVs:
       python3 adrc_tune_score.py takeoff/*.csv

Reported per log (roll & pitch, deg/s):
  err RMS 0-1s   tracking-error (gyro - setpoint) RMS in the first airborne second
                 -> the takeoff bounce; the main ranking metric
  err RMS 1-3s   same for seconds 1..3 -> early-hover noise/oscillation
  settle         time until a rolling 100 ms pitch-error RMS stays below 15 deg/s
  z3 peak        max |I-term| (= |z3/b0|) around spool-up -> ground windup of the
                 disturbance estimate (the mechanism behind the bounce)

The tune (P/I/D = wc/wo/b0) is read from the sibling .bbl header when present.
Note: the header stores the raw D value; the effective b0 is D * adrc_b0_scale
(fix #9, default 10), and the scale is not in the header - keep track of it
yourself when comparing logs from different crafts.
Lower is better for every metric. One caveat: one takeoff per tune is a noisy
sample - fly 2-3 takeoffs per candidate and compare the spread before trusting
small differences.
"""
import csv
import glob
import math
import os
import re
import sys


def read_csv_columns(path, wanted):
    cols = {name: [] for name in wanted}
    with open(path) as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        idx = {}
        for name in wanted:
            if name not in header:
                return None
            idx[name] = header.index(name)
        n = len(header)
        for row in reader:
            if len(row) != n:
                continue
            try:
                for name in wanted:
                    cols[name].append(float(row[idx[name]]))
            except ValueError:
                continue
    return cols


def tune_label(csv_path):
    # "Take off, 30-100-200.01.csv" -> sibling "Take off, 30-100-200.bbl"
    base = re.sub(r"\.\d+\.csv$", "", csv_path)
    bbl = base + ".bbl"
    if os.path.exists(bbl):
        with open(bbl, "rb") as f:
            head = f.read(65536)
        m = re.search(rb"H rollPID:(\d+),(\d+),(\d+)", head)
        if m:
            return "/".join(g.decode() for g in m.groups())
    return os.path.basename(csv_path)


def rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else float("nan")


def analyze(path):
    wanted = ["time (us)", "rcCommand[3]",
              "gyroADC[0]", "gyroADC[1]", "setpoint[0]", "setpoint[1]",
              "axisI[0]", "axisI[1]",
              "motor[0]", "motor[1]", "motor[2]", "motor[3]"]
    cols = read_csv_columns(path, wanted)
    if cols is None or len(cols["time (us)"]) < 100:
        return None
    t = [x / 1e6 for x in cols["time (us)"]]
    n = len(t)
    motor_avg = [(cols["motor[0]"][i] + cols["motor[1]"][i]
                  + cols["motor[2]"][i] + cols["motor[3]"][i]) / 4 for i in range(n)]
    m_lo, m_hi = min(motor_avg), max(motor_avg)
    thresh = m_lo + 0.15 * (m_hi - m_lo)
    i0 = next((i for i, m in enumerate(motor_avg) if m > thresh), 0)
    t0 = t[i0]
    dt = (t[-1] - t[0]) / (n - 1)

    def window(a, b):
        return [i for i in range(n) if t0 + a <= t[i] < t0 + b]

    result = {"label": tune_label(path), "file": os.path.basename(path)}
    for name, g, s in (("roll", "gyroADC[0]", "setpoint[0]"),
                       ("pitch", "gyroADC[1]", "setpoint[1]")):
        err = [cols[g][i] - cols[s][i] for i in range(n)]
        result[name + "_rms_1s"] = rms([err[i] for i in window(0.0, 1.0)])
        result[name + "_rms_3s"] = rms([err[i] for i in window(1.0, 3.0)])

    # settle: rolling 100 ms pitch-error RMS stays < 15 deg/s to the end of 4 s
    err_p = [cols["gyroADC[1]"][i] - cols["setpoint[1]"][i] for i in window(0.0, 4.0)]
    k = max(1, int(0.1 / dt))
    settle = float("nan")
    if len(err_p) > k:
        roll_rms = []
        acc = sum(e * e for e in err_p[:k])
        roll_rms.append(math.sqrt(acc / k))
        for i in range(k, len(err_p)):
            acc += err_p[i] * err_p[i] - err_p[i - k] * err_p[i - k]
            roll_rms.append(math.sqrt(max(acc, 0.0) / k))
        for i in range(len(roll_rms)):
            if all(r < 15.0 for r in roll_rms[i:]):
                settle = i * dt
                break
    result["settle_s"] = settle

    # ground windup of the disturbance estimate: max |I| around spool-up
    win = window(-0.2, 1.0)
    result["z3_peak"] = max((abs(cols["axisI[0]"][i]) for i in win), default=float("nan"))
    result["z3_peak"] = max(result["z3_peak"],
                            max((abs(cols["axisI[1]"][i]) for i in win), default=0.0))
    return result


def main(argv):
    paths = []
    for arg in argv or ["*.csv"]:
        paths.extend(glob.glob(arg))
    paths = sorted(p for p in set(paths) if p.endswith(".csv"))
    if not paths:
        print(__doc__)
        return 1
    results = [r for r in (analyze(p) for p in paths) if r]
    results.sort(key=lambda r: r["roll_rms_1s"] + r["pitch_rms_1s"])
    hdr = (f"{'tune (wc/wo/b0)':<18} {'roll RMS':>9} {'pitch RMS':>9} "
           f"{'roll RMS':>9} {'pitch RMS':>9} {'settle':>7} {'z3 peak':>8}  file")
    sub = (f"{'':<18} {'0-1 s':>9} {'0-1 s':>9} {'1-3 s':>9} {'1-3 s':>9} "
           f"{'s':>7} {'|I|':>8}")
    print(hdr)
    print(sub)
    for r in results:
        print(f"{r['label']:<18} {r['roll_rms_1s']:>9.1f} {r['pitch_rms_1s']:>9.1f} "
              f"{r['roll_rms_3s']:>9.1f} {r['pitch_rms_3s']:>9.1f} "
              f"{r['settle_s']:>7.2f} {r['z3_peak']:>8.1f}  {r['file']}")
    print("\nLower is better everywhere. Ranked by takeoff tracking-error RMS (0-1 s).")
    print("A large 'z3 peak' at a bouncy takeoff = ground windup of the disturbance")
    print("estimate (what fix #8 targets). Fly 2-3 takeoffs per tune before trusting")
    print("small differences.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

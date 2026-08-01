#!/usr/bin/env python3
"""Check a short 'the quad freaked out' session for a mechanically dead motor.

Prints, per 0.25 s slice: the gate state, stick throttle, collective, peak gyro
and setpoint, and each motor's command next to its measured eRPM. A motor held
near the output rail while its eRPM stays at idle is a stuck/failed motor, not a
control-law problem.

Usage: python3 motor_fault.py <decoded.csv>
"""

import csv
import sys
from pathlib import Path

import numpy as np


def load(path, names):
    with open(path) as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    use = [n for n in names if n in idx]
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in use], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    return {n: arr[:, i] for i, n in enumerate(use)}


def main(path, lo=48, hi=1847):
    names = (["time (us)", "rcCommand[3]", "debug[7]"]
             + [f"motor[{i}]" for i in range(4)]
             + [f"eRPM[{i}]" for i in range(4)]
             + [f"gyroUnfilt[{i}]" for i in range(3)]
             + [f"setpoint[{i}]" for i in range(3)])
    d = load(path, names)
    t = d["time (us)"] / 1e6
    t -= t[0]
    mot = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    coll = (mot.mean(axis=0) - lo) / (hi - lo) * 100
    gate = d["debug[7]"] > 0
    thr = (d["rcCommand[3]"] - 1000) / 10
    gyro = np.vstack([d[f"gyroUnfilt[{i}]"] for i in range(3)])
    sp = np.vstack([d[f"setpoint[{i}]"] for i in range(3)])

    print(f"=== {Path(path).name} ===  {t[-1]:.2f} s, gate open {gate.mean()*100:.0f} %, "
          f"gate at first sample: {bool(gate[0])}")
    for k in range(int(t[-1] / 0.25) + 1):
        m = (t >= k * 0.25) & (t < (k + 1) * 0.25)
        if m.sum() < 10:
            continue
        cmds = " ".join(f"{np.median(mot[i, m]):6.0f}" for i in range(4))
        rpms = " ".join(f"{np.median(d[f'eRPM[{i}]'][m]):6.0f}" for i in range(4))
        print(f"  t={k*0.25:4.2f}s gate {gate[m].mean():.2f} thr {np.median(thr[m]):5.1f} % "
              f"coll {np.median(coll[m]):5.1f} % gyro|max {np.abs(gyro[:, m]).max():6.0f} "
              f"sp|max {np.abs(sp[:, m]).max():5.0f} | cmd {cmds} | eRPM {rpms}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)

#!/usr/bin/env python3
"""ADRC-021, second craft: pool b0_hat windows from jmsweng's two 2026-07-15
b4 logs (DAKEFPVF405, 2300 kV 5", motorOutput 158..2047, adrc_hover_throttle
= 35) and score the candidate laws in that craft's own frame (hover = 35 %).

Run from this directory after decoding jmsweng/*.bbl in place.
"""
import os
import numpy as np
import identify_b0 as ib

ib.MOTOR_MIN = 158.0
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jmsweng", "")
HOVER = 35.0
LOGS = [("42-100-2000.01.csv", "42-100-2000"),
        ("Converted stock PID.01.csv", "conv-stock")]

def main():
    pooled = []
    for f, tag in LOGS:
        for ax in (0, 1):
            _, rows = ib.identify(BASE + f, ax, tag)
            pooled += [(r[1], r[2]) for r in rows]
            print(f"{tag} axis{ax}: {len(rows)} windows")
    arr = np.array(pooled)
    print(f"\npooled windows: {len(arr)}")
    print(f"{'bin %':>9} {'n':>4} {'b0_hat med':>10} {'p25':>8} {'p75':>8}")
    for lo in range(10, 80, 5):
        m = (arr[:, 0] >= lo) & (arr[:, 0] < lo + 5)
        if m.sum() < 3:
            continue
        q25, med, q75 = np.percentile(arr[m, 1], [25, 50, 75])
        print(f"{lo:>4}-{lo+5:<4} {m.sum():>4} {med:>10.0f} {q25:>8.0f} {q75:>8.0f}")
    for name, law in [("code clamp((c/h)^2,1,3)", lambda c: np.clip((c/HOVER)**2, 1, 3)),
                      ("linear c/h", lambda c: c / HOVER),
                      ("sqrt (c/h)^0.5", lambda c: np.sqrt(c / HOVER)),
                      ("fixed scale=1", lambda c: np.ones_like(c))]:
        c, y = arr[:, 0], arr[:, 1]
        s = law(c)
        b0h = np.exp(np.mean(np.log(y / s)))
        rms = np.sqrt(np.mean(np.log2(y / (b0h * s)) ** 2))
        print(f"{name:<26} b0_hover={b0h:6.0f} rms_log2={rms:.3f}")

if __name__ == "__main__":
    main()

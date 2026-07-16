#!/usr/bin/env python3
"""ADRC-021: pool the per-window b0_hat estimates from all usable logs and
score the candidate b0(collective) laws.

Laws are evaluated in the code's own frame: scale(c) applied to a fitted
b0_hover, collective c in mixer % (see identify_b0.py), hover = 22 %
(adrc_hover_throttle from the flight's diff all). The code's shipped law is
scale = clamp((c/hover)^2, 1, 3). Score = RMS of log(b0_hat/model) over
windows (log-space so under/over-estimation weigh equally), with b0_hover
chosen per law to minimize that RMS (fair to every law).

Usage: fit_b0_law.py   (paths/axes hardcoded to the 2026-07-15 walhalla set)
"""
import os
import numpy as np
import identify_b0 as ib

# CSVs are produced next to the committed .bbl originals: blackbox_decode *.bbl
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "")
HOVER = 22.0
# every p1/p2 log; p3 (cascade experiment, not PR code) excluded
LOGS = [
    ("btfl_001_p1_roll_doublets.01.csv", 0, "001r"),
    ("btfl_001_p1_roll_doublets.01.csv", 1, "001p"),
    ("btfl_002_p2_converted_stock_tune.01.csv", 0, "002r"),
    ("btfl_002_p2_converted_stock_tune.01.csv", 1, "002p"),
    ("btfl_003_p1_throttle_punch_rebound.01.csv", 0, "003r"),
    ("btfl_003_p1_throttle_punch_rebound.01.csv", 1, "003p"),
    ("btfl_005_p1_pitch_doublets.01.csv", 0, "005r"),
    ("btfl_005_p1_pitch_doublets.01.csv", 1, "005p"),
    ("btfl_006_p1_chops_and_playing.01.csv", 0, "006r"),
    ("btfl_006_p1_chops_and_playing.01.csv", 1, "006p"),
    ("btfl_007_p1_but_higher_wo.01.csv", 0, "007r"),
    ("btfl_007_p1_but_higher_wo.01.csv", 1, "007p"),
    ("btfl_008_p1_but_higher_wc.01.csv", 0, "008r"),
    ("btfl_008_p1_but_higher_wc.01.csv", 1, "008p"),
    ("btfl_009_p2_stock_tune_rolls_n_punches.01.csv", 0, "009r"),
    ("btfl_009_p2_stock_tune_rolls_n_punches.01.csv", 1, "009p"),
    ("btfl_010_p1_playing.01.csv", 0, "010r"),
    ("btfl_010_p1_playing.01.csv", 1, "010p"),
]

LAWS = {
    "fixed  scale=1": lambda c: np.ones_like(c),
    "code   clamp((c/h)^2,1,3)": lambda c: np.clip((c / HOVER) ** 2, 1.0, 3.0),
    "quad   (c/h)^2 uncapped": lambda c: (c / HOVER) ** 2,
    "linear c/h": lambda c: c / HOVER,
    "linear clamp(c/h,1,3)": lambda c: np.clip(c / HOVER, 1.0, 3.0),
    "sqrt   (c/h)^0.5": lambda c: np.sqrt(c / HOVER),
}

def main():
    pooled = []           # (coll, b0_hat, axis, label)
    for fname, axis, label in LOGS:
        try:
            _, rows = ib.identify(BASE + fname, axis, label)
        except Exception as e:
            print(f"!! {label}: {e}")
            continue
        for r in rows:
            pooled.append((r[1], r[2], axis, label))
        print(f"{label}: {len(rows)} windows")
    arr = np.array([(p[0], p[1]) for p in pooled])
    print(f"\npooled windows: {len(arr)}  (roll {sum(1 for p in pooled if p[2]==0)}, "
          f"pitch {sum(1 for p in pooled if p[2]==1)})")

    print("\n--- pooled bins (mixer-collective %) ---")
    print(f"{'bin':>9} {'n':>4} {'b0_hat med':>10} {'p25':>8} {'p75':>8} {'ratio med/hover-bin':>12}")
    hov_bin = arr[(arr[:, 0] >= 20) & (arr[:, 0] < 25), 1]
    hov_med = np.median(hov_bin) if len(hov_bin) else np.nan
    for lo in range(5, 70, 5):
        m = (arr[:, 0] >= lo) & (arr[:, 0] < lo + 5)
        if m.sum() < 3:
            continue
        q25, med, q75 = np.percentile(arr[m, 1], [25, 50, 75])
        print(f"{lo:>4}-{lo+5:<4} {m.sum():>4} {med:>10.0f} {q25:>8.0f} {q75:>8.0f} {med/hov_med:>10.2f}x")

    print(f"\n--- law scoring (RMS of log2(b0_hat/model), best-fit b0_hover per law) ---")
    c, y = arr[:, 0], arr[:, 1]
    for name, law in LAWS.items():
        s = law(c)
        # optimal b0_hover in log space: exp(mean(log(y/s)))
        b0h = np.exp(np.mean(np.log(y / s)))
        rms = np.sqrt(np.mean(np.log2(y / (b0h * s)) ** 2))
        print(f"{name:<28} b0_hover={b0h:6.0f}  rms_log2={rms:.3f}")

    # per-axis split at the hover bin, for the axis-difference question
    for ax, axname in ((0, "roll"), (1, "pitch")):
        sub = np.array([(p[0], p[1]) for p in pooled if p[2] == ax])
        if len(sub) < 3:
            continue
        m = (sub[:, 0] >= 18) & (sub[:, 0] < 27)
        if m.sum() >= 3:
            print(f"{axname}: hover-band (18-27%) b0_hat median = {np.median(sub[m,1]):.0f} (n={m.sum()})")

if __name__ == "__main__":
    main()

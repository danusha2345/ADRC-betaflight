#!/usr/bin/env python3
"""ADRC-021 robustness sweeps (run from this directory after decoding):

1. LP-cutoff / window-length / R2-threshold sweep of the pooled headline
   numbers (hover-band median, low/high-bin medians, high/hover ratio).
2. Non-overlapping windows (HOP_FRAC = 1.0): law scoring on both crafts.
3. Leave-one-log-out (Bob corpus): per-law scores, worst-case code-vs-fixed gap.
4. Per-log law winners on jmsweng's two logs.
5. Collective exponent with a frequency covariate: OLS of log(b0_hat) on
   log(coll/hover) + log(dominant excitation frequency of u) + per-log fixed
   effects (Bob corpus). The shipped law implies exponent 2 below the cap.
   Descriptive closed-loop estimate, not an unbiased causal one.
"""
import numpy as np
import identify_b0 as ib
from scipy.signal import butter, filtfilt

BOB = [("btfl_001_p1_roll_doublets.01.csv", 0), ("btfl_001_p1_roll_doublets.01.csv", 1),
       ("btfl_002_p2_converted_stock_tune.01.csv", 0), ("btfl_002_p2_converted_stock_tune.01.csv", 1),
       ("btfl_003_p1_throttle_punch_rebound.01.csv", 0), ("btfl_003_p1_throttle_punch_rebound.01.csv", 1),
       ("btfl_005_p1_pitch_doublets.01.csv", 0), ("btfl_005_p1_pitch_doublets.01.csv", 1),
       ("btfl_006_p1_chops_and_playing.01.csv", 0), ("btfl_006_p1_chops_and_playing.01.csv", 1),
       ("btfl_007_p1_but_higher_wo.01.csv", 0), ("btfl_007_p1_but_higher_wo.01.csv", 1),
       ("btfl_008_p1_but_higher_wc.01.csv", 0), ("btfl_008_p1_but_higher_wc.01.csv", 1),
       ("btfl_009_p2_stock_tune_rolls_n_punches.01.csv", 0), ("btfl_009_p2_stock_tune_rolls_n_punches.01.csv", 1),
       ("btfl_010_p1_playing.01.csv", 0), ("btfl_010_p1_playing.01.csv", 1)]
JMS = [("jmsweng/42-100-2000.01.csv", 0), ("jmsweng/42-100-2000.01.csv", 1),
       ("jmsweng/Converted stock PID.01.csv", 0), ("jmsweng/Converted stock PID.01.csv", 1)]

LAWS = {"sqrt": lambda c, h: np.sqrt(c / h),
        "linear": lambda c, h: c / h,
        "fixed": lambda c, h: np.ones_like(c),
        "code": lambda c, h: np.clip((c / h) ** 2, 1.0, 3.0)}

def collect(logs, motor_min=48.0):
    ib.MOTOR_MIN = motor_min
    out = []
    for f, ax in logs:
        try:
            _, rows = ib.identify(f, ax, "")
        except Exception:
            continue
        out += [(r[1], r[2], f) for r in rows]
    return out

def score(pool, hover):
    res = {}
    c = np.array([p[0] for p in pool])
    y = np.array([p[1] for p in pool])
    for name, law in LAWS.items():
        s = law(c, hover)
        b0h = np.exp(np.mean(np.log(y / s)))
        res[name] = np.sqrt(np.mean(np.log2(y / (b0h * s)) ** 2))
    return res

def main():
    # 1. sweep
    print("=== 1. sweep (Bob corpus): hover/low/high medians ===")
    print(f"{'variant':<18} {'n':>4} {'hover18-27':>10} {'low10-16':>9} {'high40-60':>10} {'hi/hov':>7}")
    for tag, lp, wins, r2 in [("base LP25 w0.4", 25.0, 0.4, 0.5), ("LP=15", 15.0, 0.4, 0.5),
                              ("LP=35", 35.0, 0.4, 0.5), ("win=0.6", 25.0, 0.6, 0.5),
                              ("win=0.25", 25.0, 0.25, 0.5), ("R2>=0.35", 25.0, 0.4, 0.35)]:
        ib.LP_HZ, ib.WIN_S, ib.MIN_R2 = lp, wins, r2
        pool = collect(BOB)
        a = np.array([(p[0], p[1]) for p in pool])
        def med(lo, hi):
            m = (a[:, 0] >= lo) & (a[:, 0] < hi)
            return np.median(a[m, 1]) if m.sum() >= 3 else np.nan
        hov, lo_, hi_ = med(18, 27), med(10, 16), med(40, 60)
        print(f"{tag:<18} {len(a):>4} {hov:>10.0f} {lo_:>9.0f} {hi_:>10.0f} {hi_/hov:>7.2f}")
    ib.LP_HZ, ib.WIN_S, ib.MIN_R2 = 25.0, 0.4, 0.5

    # 2. non-overlapping windows
    print("\n=== 2. non-overlapping windows (HOP_FRAC=1.0) law scores ===")
    ib.HOP_FRAC = 1.0
    for name, logs, mm, hov in [("Bob", BOB, 48.0, 22.0), ("jmsweng", JMS, 158.0, 35.0)]:
        pool = collect(logs, mm)
        sc = score(pool, hov)
        print(f"{name}: n={len(pool)} " + " ".join(f"{k}={v:.3f}" for k, v in sc.items()))
    ib.HOP_FRAC = 0.5

    # 3. leave-one-log-out (Bob)
    print("\n=== 3. leave-one-log-out (Bob, overlapping windows) ===")
    pool = collect(BOB)
    files = sorted(set(p[2] for p in pool))
    worst_gap = None
    for f in files:
        sub = [p for p in pool if p[2] != f]
        sc = score(sub, 22.0)
        gap = sc["code"] - sc["fixed"]
        tag = f.split("_")[1]
        print(f"-{tag:<4} n={len(sub):>3} sqrt={sc['sqrt']:.3f} linear={sc['linear']:.3f} "
              f"fixed={sc['fixed']:.3f} code={sc['code']:.3f} code-fixed={gap:+.3f}")
        if worst_gap is None or gap < worst_gap:
            worst_gap = gap
    print(f"worst code-fixed gap: {worst_gap:+.3f}")

    # 4. per-log winners (jmsweng)
    print("\n=== 4. per-log law scores (jmsweng) ===")
    for f in ["jmsweng/42-100-2000.01.csv", "jmsweng/Converted stock PID.01.csv"]:
        pool = collect([(f, 0), (f, 1)], 158.0)
        sc = score(pool, 35.0)
        best = min(sc, key=sc.get)
        print(f"{f.split('/')[-1]:<28} n={len(pool):>3} " +
              " ".join(f"{k}={v:.3f}" for k, v in sc.items()) + f"  best={best}")

    # 5. collective exponent with frequency covariate (Bob)
    print("\n=== 5. log(b0_hat) ~ p*log(c/h) + q*log(f_u) + per-log FE (Bob) ===")
    ib.MOTOR_MIN = 48.0
    rows = []
    for f, ax in BOB:
        try:
            d = ib.load(f, ax)
        except Exception:
            continue
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1.0 / np.median(np.diff(t))
        u = np.clip(d[f"axisP[{ax}]"] + d[f"axisI[{ax}]"] + d[f"axisD[{ax}]"], -500, 500)
        ub = ib.bandpass(u, fs)
        _, wins = ib.identify(f, ax, "")
        for (tc, coll, b0h, r2, urms) in wins:
            s = int((tc - ib.WIN_S / 2) * fs)
            sl = slice(s, s + int(ib.WIN_S * fs))
            x = ub[sl]
            w = np.hanning(len(x))
            X = np.fft.rfft((x - x.mean()) * w)
            fr = np.fft.rfftfreq(len(x), 1 / fs)
            fpk = fr[np.argmax(np.abs(X) ** 2)]
            if fpk <= 0:
                continue
            rows.append((np.log(coll / 22.0), np.log(fpk), np.log(b0h), f))
    files = sorted(set(r[3] for r in rows))
    X = np.array([[r[0], r[1]] + [1.0 if r[3] == f else 0.0 for f in files] for r in rows])
    yv = np.array([r[2] for r in rows])
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    print(f"n={len(rows)} collective exponent p={beta[0]:.2f} (shipped law implies 2 below cap), "
          f"frequency exponent q={beta[1]:.2f}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fit @jmsweng's Air65 stand data and turn it into a schedule-shape proxy.

Model selection is done on residual structure and information criteria, not on
prediction-interval overlap. The reported quantity is the local slope
dT/dcmd normalised to a hover command, i.e. a static roll/pitch proxy for the
shape of a b0 schedule -- not an identification of this implementation's b0
(which is defined on omega_ddot and absorbs actuator dynamics), and not
applicable to yaw at all.

Usage: python3 fit_bench.py Air65_throttle_vs_thrust.csv
"""

import csv
import sys

import numpy as np

CMD_MIN, CMD_MAX = 1000.0, 2000.0
HOVERS_PCT = [25.0, 29.0, 31.0, 35.0]


def load(path):
    cmd, thrust = [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            cmd.append(float(row["Throttle"]))
            thrust.append(float(row["Thrust (g)"]))
    o = np.argsort(cmd)
    return np.asarray(cmd)[o], np.asarray(thrust)[o]


def aicc(resid, k):
    n = len(resid)
    rss = float(np.sum(resid ** 2))
    ll = -n / 2 * (np.log(2 * np.pi * rss / n) + 1)
    return -2 * ll + 2 * k + (2 * k * (k + 1)) / (n - k - 1)


def runs_test(resid):
    """Wald-Wolfowitz runs test on residual signs: z far from 0 => structure."""
    s = np.sign(resid)
    s = s[s != 0]
    n1 = int((s > 0).sum())
    n2 = int((s < 0).sum())
    runs = 1 + int((s[1:] != s[:-1]).sum())
    mu = 2 * n1 * n2 / (n1 + n2) + 1
    var = (2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    return runs, mu, (runs - mu) / np.sqrt(var)


def main(path):
    cmd, T = load(path)
    x = (cmd - CMD_MIN) / (CMD_MAX - CMD_MIN)          # 0..1 normalised command
    print(f"{len(cmd)} points, command {cmd.min():.0f}-{cmd.max():.0f}, "
          f"thrust {T.min():.0f}-{T.max():.0f} g\n")

    fits = {}
    # affine: T = a*x + b   -> dT/dx = a (FIXED)
    p1 = np.polyfit(x, T, 1)
    fits["affine (T = a·x + b)"] = (np.polyval(p1, x), 2,
                                    lambda xx: np.full_like(xx, p1[0]))
    # quadratic: T = a*x^2 + b*x + c -> dT/dx = 2a*x + b
    p2 = np.polyfit(x, T, 2)
    fits["quadratic"] = (np.polyval(p2, x), 3,
                         lambda xx: 2 * p2[0] * xx + p2[1])
    # pure power law through a dead command x0: T = a*(x - x0)^n, fitted in logs
    best = None
    for x0 in np.linspace(-0.2, 0.25, 181):
        m = x > x0 + 1e-6
        if m.sum() < len(x) - 2:
            continue
        A = np.polyfit(np.log(x[m] - x0), np.log(np.maximum(T[m], 1e-3)), 1)
        pred = np.zeros_like(T)
        pred[m] = np.exp(A[1]) * (x[m] - x0) ** A[0]
        rss = float(np.sum((T - pred) ** 2))
        if best is None or rss < best[0]:
            best = (rss, x0, A[0], np.exp(A[1]), pred)
    _, x0, n, a, pred_pl = best
    fits[f"power law (n = {n:.2f}, x0 = {x0:+.3f})"] = (
        pred_pl, 3, lambda xx: a * n * np.maximum(xx - x0, 1e-6) ** (n - 1))

    print(f"{'model':34s} {'RSS':>8s} {'sd':>7s} {'AICc':>8s}  runs test (z)")
    for name, (pred, k, _) in fits.items():
        r = T - pred
        runs, mu, z = runs_test(r)
        print(f"{name:34s} {np.sum(r**2):8.1f} {np.std(r):7.2f} {aicc(r, k):8.1f}"
              f"  {runs} vs {mu:.1f} expected (z = {z:+.2f})")

    print("\nlocal slope dT/dcmd normalised to hover (schedule-shape proxy)")
    print(f"{'hover':>6s}  {'model':34s} " + "".join(f"{f'{p}%':>8s}" for p in (40, 50, 60, 80, 100)))
    for hov in HOVERS_PCT:
        for name, (_, _, dfun) in fits.items():
            base = float(dfun(np.array([hov / 100.0]))[0])
            cells = "".join(f"{float(dfun(np.array([p/100.0]))[0])/base:8.2f}"
                            for p in (40, 50, 60, 80, 100))
            print(f"{hov:5.0f}%  {name:34s} {cells}")
        print()

    print("what the laws would apply (hover 29 %):")
    print(f"{'thr%':>5s} {'FIXED':>7s} {'SQRT':>7s} {'LINEAR':>7s} {'QUAD':>7s} {'QUAD@3':>7s}")
    for p in (40, 50, 60, 80, 100):
        r = p / 29.0
        q = max(1.0, r * r)
        print(f"{p:5d} {1.00:7.2f} {max(1.0, np.sqrt(r)):7.2f} {max(1.0, r):7.2f} "
              f"{q:7.2f} {min(q, 3.0):7.2f}")

    # How much rise do these 25 points actually allow? Bootstrap the most
    # permissive of the three shapes (the quadratic, whose slope is free to
    # grow) and read off the interval on the slope ratio.
    print("\nbootstrap on the quadratic fit (4000 resamples, seed 7):")
    rng = np.random.default_rng(7)

    def ratio(xx, yy, hov, at):
        p = np.polyfit(xx, yy, 2)
        return (2 * p[0] * at + p[1]) / (2 * p[0] * hov + p[1])

    for hov in HOVERS_PCT:
        h = hov / 100.0
        for at in (0.60, 1.00):
            base = ratio(x, T, h, at)
            bs = []
            for _ in range(4000):
                i = rng.integers(0, len(x), len(x))
                if len(np.unique(x[i])) < 6:
                    continue
                bs.append(ratio(x[i], T[i], h, at))
            bs = np.asarray(bs)
            print(f"  hover {hov:.0f} % -> {at*100:.0f} %: slope ratio {base:.2f}, "
                  f"5-95 % [{np.percentile(bs,5):.2f}, {np.percentile(bs,95):.2f}]")


main(sys.argv[1] if len(sys.argv) > 1 else "Air65_throttle_vs_thrust.csv")

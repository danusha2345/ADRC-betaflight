#!/usr/bin/env python3
"""Robustness checks quoted in ANALYSIS.md (added after external review):

1. Law-scoring stability: leave-one-flight-out refits and a flight-level
   bootstrap of the pooled scoring in b5_ab.law_scores (which scores
   candidate schedule shapes against pooled plant-gain windows — not
   per-arm flight accuracy).
2. Ring incidence under the ORIGINAL committed ring_sensitivity.py window
   criterion (mean-motor > 68, loudest-axis test) for comparison with
   b5_ab.py's stricter gate (min-motor > 50, first-axis test).

Run from this directory after blackbox_decode --debug --unit-frame-time us *.bbl.
"""
import sys
import numpy as np

sys.path.insert(0, ".")
import b5_ab as B
import identify_b0 as ib


def pooled_with_files():
    rows = []
    for fname, law in B.LOGS:
        for axis in (0, 1):
            _, r = ib.identify(fname, axis, fname)
            rows += [(fname, w[1], w[2]) for w in r]
    return rows


def score(coll, b0h):
    out = {}
    for name, f in B.LAWS.items():
        s = f(coll)
        b0 = np.exp(np.median(np.log(b0h / s)))
        out[name] = np.sqrt(np.mean(np.log(b0h / (b0 * s)) ** 2))
    return out


def main():
    rows = pooled_with_files()
    files = [f for f, _, _ in rows]
    arr = np.array([(c, b) for _, c, b in rows])
    full = score(arr[:, 0], arr[:, 1])
    print("full corpus:", {k: round(v, 3) for k, v in full.items()})

    wins = {}
    for fname, _ in B.LOGS:
        m = np.array([f != fname for f in files])
        sc = score(arr[m, 0], arr[m, 1])
        w = min(sc, key=sc.get)
        wins[w] = wins.get(w, 0) + 1
    print("leave-one-flight-out winners:", wins)

    rng = np.random.default_rng(0)
    ufiles = sorted(set(files))
    fidx = {f: np.where(np.array(files) == f)[0] for f in ufiles}
    boot = {}
    for _ in range(2000):
        pick = rng.choice(ufiles, len(ufiles), replace=True)
        idx = np.concatenate([fidx[f] for f in pick])
        sc = score(arr[idx, 0], arr[idx, 1])
        w = min(sc, key=sc.get)
        boot[w] = boot.get(w, 0) + 1
    print("flight bootstrap x2000 winners:", boot)

    print("\nring incidence, ORIGINAL ring_sensitivity.py criterion:")
    print(f"{'log':<28} {'law':<10} {'win':>4} {'ring':>4} {'%':>5}")
    for fname, law in B.LOGS:
        d = B.loadcols(fname, ["time (us)", "rcCommand[3]", "gyroADC[0]",
                               "gyroADC[1]", "debug[7]", "motor[0]",
                               "motor[1]", "motor[2]", "motor[3]"])
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1 / np.median(np.diff(t))
        thr = (d["rcCommand[3]"] - 1000) / 10
        gate = d["debug[7]"] > 0
        mot = np.mean([d[f"motor[{i}]"] for i in range(4)], axis=0) > 68
        win = int(fs)
        n = ring = 0
        for s in range(0, len(t) - win, win // 2):
            sl = slice(s, s + win)
            if not (gate[sl].all() and mot[sl].all()):
                continue
            if not (10 <= thr[sl].mean() <= 35):
                continue
            n += 1
            fR, aR, frR = B.ring_tone(d["gyroADC[0]"][sl], fs)
            fP, aP, frP = B.ring_tone(d["gyroADC[1]"][sl], fs)
            fq, a, fr = (fR, aR, frR) if aR >= aP else (fP, aP, frP)
            if a > 5 and fr > 0.5 and 18 <= fq <= 32:
                ring += 1
        print(f"{fname:<28} {law:<10} {n:>4} {ring:>4} {100*ring/max(n,1):>4.0f}%")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""ADRC-021/024/025 A/B analysis of the 2026-07-19 b5 flights (adrc_b0_law).

12 flights, one craft (SPEEDYBEEF7MINIV2, hover 22 %), defaults 60/100/2000 in
every profile, ONLY adrc_b0_law differs. Methods identical to the committed
pr15400-doublets pipeline (identify_b0 / z3_check / ring_sensitivity /
punches); this script only re-groups the outputs by law arm.

Run from this directory after blackbox_decode *.bbl.
"""
import csv as csvmod
import os
import sys
import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pr15400-doublets"))
import identify_b0 as ib


def _robust_ib_load(path, axis):
    """ib.load with invalid_raise=False: b5 CSVs carry truncated tail rows."""
    cols = ["time (us)", f"setpoint[{axis}]", f"gyroADC[{axis}]",
            f"axisP[{axis}]", f"axisI[{axis}]", f"axisD[{axis}]",
            "rcCommand[3]", "debug[7]",
            "motor[0]", "motor[1]", "motor[2]", "motor[3]"]
    d = loadcols(path, cols)
    return d


ib.load = _robust_ib_load

HOVER = 22.0
Z3SCALE = 16.0
SCALE_MAX = 3.0

# (csv, law) — law from the .bbl header adrc_b0_law, cross-checked vs diff all
LOGS = [
    ("btfl_pack1_001_p1.01.csv", "SQRT"),
    ("btfl_pack2_003_p1.01.csv", "SQRT"),
    ("btfl_pack3_002_p1.01.csv", "SQRT"),
    ("btfl_pack1_002_p2.01.csv", "FIXED"),
    ("btfl_pack1_003_p3.01.csv", "QUADRATIC"),
    ("btfl_pack2_001_p3.01.csv", "QUADRATIC"),
    ("btfl_pack2_004_p3.01.csv", "QUADRATIC"),
    ("btfl_pack3_003_p3.01.csv", "QUADRATIC"),
    ("btfl_pack1_004_p4.01.csv", "LINEAR"),
    ("btfl_pack2_002_p4.01.csv", "LINEAR"),
    ("btfl_pack2_003_p4.01.csv", "LINEAR"),
    ("btfl_pack3_001_p4.01.csv", "LINEAR"),
]

LAWS = {
    "FIXED": lambda c: np.ones_like(c),
    "SQRT": lambda c: np.clip(np.sqrt(np.maximum(c, 0) / HOVER), 1.0, SCALE_MAX),
    "LINEAR": lambda c: np.clip(c / HOVER, 1.0, SCALE_MAX),
    "QUADRATIC": lambda c: np.clip((c / HOVER) ** 2, 1.0, SCALE_MAX),
}
COLL_BINS = [(10, 16), (18, 27), (30, 40), (40, 60)]


def loadcols(path, cols):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    d = np.genfromtxt(path, delimiter=",", skip_header=1,
                      usecols=[idx[c] for c in cols], invalid_raise=False)
    good = ~np.isnan(d).any(axis=1)
    return {c: d[good, k] for k, c in enumerate(cols)}


def sanity_scale():
    """debug[7]/100 must follow the arm's law — proves which law was active."""
    print("== sanity: applied b0 scale (|debug[7]|/100) vs law prediction ==")
    print(f"{'log':<28} {'law':<10} " + " ".join(f"{lo}-{hi}%" for lo, hi in COLL_BINS))
    for fname, law in LOGS:
        d = loadcols(fname, ["debug[7]", "motor[0]", "motor[1]", "motor[2]", "motor[3]"])
        gate = d["debug[7]"] > 0
        scale = np.abs(d["debug[7]"]) / 100.0
        motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
        coll = (motors.mean(axis=0) - 48) / (2047 - 48) * 100
        cells = []
        for lo, hi in COLL_BINS:
            m = gate & (coll >= lo) & (coll < hi)
            if m.sum() < 50:
                cells.append("   -  ")
                continue
            med = np.median(scale[m])
            pred = np.median(LAWS[law](coll[m]))
            cells.append(f"{med:4.2f}/{pred:4.2f}")
        print(f"{fname:<28} {law:<10} " + " ".join(cells))
    print("(cells: measured/predicted median scale per collective bin)\n")


def pooled_windows():
    """identify_b0 windows over all logs+axes, tagged with the arm."""
    allrows = []
    for fname, law in LOGS:
        for axis in (0, 1):
            try:
                _, rows = ib.identify(fname, axis, fname)
            except Exception as e:
                print(f"  !! {fname} axis{axis}: {e}")
                continue
            for r in rows:
                allrows.append((law, r[1], r[2]))  # (law, coll%, b0_hat)
    return np.array([(c, b) for _, c, b in allrows]), [l for l, _, _ in allrows]


def law_scores(arr):
    """Same scoring as fit_b0_law.py: RMS log-error, per-law best-fit hover b0."""
    print("== law scoring on pooled b5 windows (plant is law-independent) ==")
    coll, b0h = arr[:, 0], arr[:, 1]
    for name, f in LAWS.items():
        s = f(coll)
        b0_hover = np.exp(np.median(np.log(b0h / s)))
        rms = np.sqrt(np.mean(np.log(b0h / (b0_hover * s)) ** 2))
        print(f"  {name:<10} b0_hover*={b0_hover:6.0f}  RMS(log-err)={rms:.3f}")
    print(f"  bins: ", end="")
    for lo, hi in COLL_BINS:
        m = (coll >= lo) & (coll < hi)
        if m.sum() >= 3:
            print(f"{lo}-{hi}%: n={m.sum()} med={np.median(b0h[m]):.0f}", end="  ")
    print("\n")


def z3_by_arm():
    """THE A/B discriminator: z3~u slope per collective bin per arm.
    Correct law => slope ~0 across collective; over-scaling => negative high."""
    print("== z3~u slope by arm (roll deb[2] + pitch deb[5], x16) ==")
    print(f"{'law':<10} {'coll bin':>8} {'n':>5} {'slope med':>10} {'p25':>8} {'p75':>8}")
    per_arm = {law: [] for law in LAWS}
    for fname, law in LOGS:
        cols = ["time (us)", "debug[2]", "debug[5]", "debug[7]",
                "axisP[0]", "axisI[0]", "axisD[0]",
                "axisP[1]", "axisI[1]", "axisD[1]",
                "motor[0]", "motor[1]", "motor[2]", "motor[3]"]
        d = loadcols(fname, cols)
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1 / np.median(np.diff(t))
        gate = d["debug[7]"] > 0
        motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
        coll = (motors.mean(axis=0) - 48) / (2047 - 48) * 100
        noclip = (motors.min(axis=0) > 60) & (motors.max(axis=0) < 1950)
        bl, al = butter(2, 25 / (fs / 2), "low")
        bh, ah = butter(2, 1.5 / (fs / 2), "high")
        for axis, deb in ((0, "debug[2]"), (1, "debug[5]")):
            u = np.clip(d[f"axisP[{axis}]"] + d[f"axisI[{axis}]"] + d[f"axisD[{axis}]"], -500, 500)
            z3 = d[deb] * Z3SCALE
            railed = np.abs(d[deb]) >= 32700
            ub = filtfilt(bh, ah, filtfilt(bl, al, u))
            z3b = filtfilt(bh, ah, filtfilt(bl, al, z3))
            win = int(0.4 * fs)
            for s in range(0, len(t) - win, win // 2):
                sl = slice(s, s + win)
                if not (gate[sl].all() and noclip[sl].all()) or railed[sl].any():
                    continue
                if ub[sl].std() < 8:
                    continue
                den = np.dot(ub[sl] - ub[sl].mean(), ub[sl] - ub[sl].mean())
                slope = np.dot(ub[sl] - ub[sl].mean(), z3b[sl] - z3b[sl].mean()) / den
                per_arm[law].append((coll[sl].mean(), slope))
    for law, rows in per_arm.items():
        rows = np.array(rows)
        if not len(rows):
            continue
        for lo, hi in COLL_BINS:
            m = (rows[:, 0] >= lo) & (rows[:, 0] < hi)
            if m.sum() < 3:
                continue
            q25, med, q75 = np.percentile(rows[m, 1], [25, 50, 75])
            print(f"{law:<10} {lo:>3}-{hi:<4} {int(m.sum()):>5} {med:>10.0f} {q25:>8.0f} {q75:>8.0f}")
    print()


def ring_by_arm():
    """ADRC-024 signature per arm: 1 s Hann windows, hover band, 18-32 Hz tone."""
    print("== ring incidence by arm (hover band, 18-32 Hz tone) ==")
    print(f"{'log':<28} {'law':<10} {'win':>4} {'ring':>4} {'%':>5} {'worst f/rms':>12}")
    for fname, law in LOGS:
        cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]",
                "debug[7]", "motor[0]", "motor[1]", "motor[2]", "motor[3]"]
        d = loadcols(fname, cols)
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1 / np.median(np.diff(t))
        thr = (d["rcCommand[3]"] - 1000) / 10
        gate = d["debug[7]"] > 0
        motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
        on = motors.min(axis=0) > 50
        win = int(fs)
        tot = ring = 0
        worst = (0.0, 0.0)
        for s in range(0, len(t) - win, win // 2):
            sl = slice(s, s + win)
            if not (gate[sl].all() and on[sl].all()):
                continue
            if not (10 <= thr[sl].mean() <= 35):
                continue
            tot += 1
            for axis in (0, 1):
                f0, tr, frac = ring_tone(d[f"gyroADC[{axis}]"][sl], fs)
                if 18 <= f0 <= 32 and tr > 5 and frac > 0.5:
                    ring += 1
                    if tr > worst[1]:
                        worst = (f0, tr)
                    break
        pct = 100 * ring / tot if tot else 0
        w = f"{worst[0]:.0f}Hz/{worst[1]:.0f}" if ring else "-"
        print(f"{fname:<28} {law:<10} {tot:>4} {ring:>4} {pct:>4.0f}% {w:>12}")
    print()


def ring_tone(x, fs, flo=10, fhi=40):
    w = np.hanning(len(x))
    X = np.fft.rfft((x - x.mean()) * w)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    psd = np.abs(X) ** 2 / (fs * (w ** 2).sum())
    band = (f >= flo) & (f <= fhi)
    pk = np.argmax(psd * band)
    df = f[1] - f[0]
    tr = np.sqrt(psd[(f >= f[pk] - 2) & (f <= f[pk] + 2)].sum() * df * 2)
    tot = np.sqrt(psd[(f >= 5) & (f <= 100)].sum() * df * 2)
    return f[pk], tr, tr / tot if tot > 0 else 0


def punches_by_arm():
    """ADRC-025 events per arm (same criteria as punches_20260715.py)."""
    print("== punch->chop rebounds by arm (calm-stick, 0.6 s window) ==")
    print(f"{'law':<10} {'n':>3} {'median':>7} {'max':>6}  (deg/s, worst axis)")
    per = {law: [] for law in LAWS}
    for fname, law in LOGS:
        cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]",
                "debug[7]", "setpoint[0]", "setpoint[1]"]
        d = loadcols(fname, cols)
        t = d["time (us)"] * 1e-6
        t -= t[0]
        fs = 1 / np.median(np.diff(t))
        thr = (d["rcCommand[3]"] - 1000) / 10
        gate = d["debug[7]"] > 0
        n = len(t)
        i = 0
        while i < n - int(fs):
            if thr[i] > 40 and gate[i]:
                pk = i
                while pk < n - 1 and thr[pk] >= 15:
                    pk += 1
                if (t[pk] - t[i]) < 4.0 and thr[pk] < 15:
                    k2 = min(n, pk + int(0.6 * fs))
                    spmax = max(np.abs(d["setpoint[0]"][pk:k2]).max(),
                                np.abs(d["setpoint[1]"][pk:k2]).max())
                    if spmax < 60:
                        reb = max(np.abs(d["gyroADC[0]"][pk:k2]).max(),
                                  np.abs(d["gyroADC[1]"][pk:k2]).max())
                        per[law].append(reb)
                    i = k2
                    continue
                i = pk
                continue
            i += 1
    for law, evs in per.items():
        if evs:
            print(f"{law:<10} {len(evs):>3} {np.median(evs):>7.0f} {max(evs):>6.0f}")
        else:
            print(f"{law:<10}   0")
    print()


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sanity_scale()
    arr, laws = pooled_windows()
    print(f"pooled identify_b0 windows: {len(arr)} "
          f"({', '.join(f'{l}:{laws.count(l)}' for l in LAWS)})\n")
    if len(arr):
        law_scores(arr)
    z3_by_arm()
    ring_by_arm()
    punches_by_arm()


if __name__ == "__main__":
    main()

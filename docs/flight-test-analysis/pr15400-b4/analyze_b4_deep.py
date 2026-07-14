#!/usr/bin/env python3
"""Time-resolved context for the residual 26 Hz tone + loosened punch-chop detector."""
import csv as csvmod
import numpy as np

def load(path):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]",
            "debug[2]", "debug[5]", "debug[7]",
            "motor[0]", "motor[1]", "motor[2]", "motor[3]",
            "setpoint[0]", "setpoint[1]", "setpoint[2]", "vbatLatest (V)"]
    data = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=[idx[c] for c in cols])
    return {c: data[:, k] for k, c in enumerate(cols)}

def tone(x, fs):
    n = len(x)
    w = np.hanning(n)
    X = np.fft.rfft((x - x.mean()) * w)
    f = np.fft.rfftfreq(n, 1 / fs)
    psd = np.abs(X) ** 2 / (fs * (w ** 2).sum())
    df = f[1] - f[0]
    band = (f >= 15) & (f <= 35)
    pk = np.argmax(psd * band)
    tone_rms = np.sqrt(psd[(f >= f[pk] - 2) & (f <= f[pk] + 2)].sum() * df * 2)
    tot_rms = np.sqrt(psd[(f >= 5) & (f <= 100)].sum() * df * 2)
    return f[pk], tone_rms, tot_rms

BASE = "/home/danik/Projects_and_coding/ADRC-betaflight/blackbox/bvandevliet/"
for path, lab in [("b4/btfl_002.01.csv", "b4 log2"), ("b4/btfl_003.01.csv", "b4 log3"),
                  ("b4/btfl_004.01.csv", "b4 log4"), ("btfl_AIR2.01.csv", "b3 AIR2")]:
    d = load(BASE + path)
    t = d["time (us)"] * 1e-6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000) / 10
    gate = np.sign(d["debug[7]"])
    b0s = np.abs(d["debug[7]"]) / 100
    mot = np.stack([d[f"motor[{i}]"] for i in range(4)])
    mfloor = (mot <= mot.min() + 30).mean(0)     # доля моторов у нижнего упора
    spR = d["setpoint[0]"]; spP = d["setpoint[1]"]
    win = int(fs); hop = win // 2
    print(f"\n===== {lab} (fs={fs:.0f}) =====")
    print("  t(s) thr%  f(Hz) toneR tone% |sp|p90 mFloor% b0scl vbat  z3P(k)")
    rows = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if gate[sl].mean() < 0.9:
            continue
        fpk, tr, tot = tone(d["gyroADC[0]"][sl], fs)
        frac = tr / tot * 100 if tot > 0 else 0
        rows.append((t[s], thr[sl].mean(), fpk, tr, frac,
                     np.percentile(np.abs(np.concatenate([spR[sl], spP[sl]])), 90),
                     mfloor[sl].mean() * 100, b0s[sl].mean(),
                     d["vbatLatest (V)"][sl].mean(),
                     np.abs(d["debug[5]"][sl] * 16).max() / 1000))
    rows.sort(key=lambda r: -r[3])
    for r in rows[:8]:
        print("  %5.1f %4.0f  %5.1f %5.1f %4.0f%% %7.0f %6.0f%% %5.2f %5.1f %6.0f" % r)
    calm = [r for r in rows if r[5] < 40]
    rage = [r for r in rows if r[3] > 8]
    print(f"  windows: {len(rows)} total, {len(rage)} raging(>8deg/s), of which calm-stick: "
          f"{sum(1 for r in rage if r[5] < 40)}")
    if rage:
        print(f"  raging: thr {min(r[1] for r in rage):.0f}-{max(r[1] for r in rage):.0f}%, "
              f"mFloor med {np.median([r[6] for r in rage]):.0f}%, "
              f"vbat med {np.median([r[8] for r in rage]):.1f}")
    quiet = [r for r in rows if r[3] < 3]
    if quiet:
        print(f"  quiet:  mFloor med {np.median([r[6] for r in quiet]):.0f}%, "
              f"vbat med {np.median([r[8] for r in quiet]):.1f}")

    # loosened punch->chop
    print("  punch->chop (thr>40% -> <15%):")
    n = len(t); i = 0; found = 0
    while i < n - int(fs):
        if thr[i] > 40 and gate[i] > 0:
            pk = i
            while pk < n - 1 and thr[pk] >= 15:
                pk += 1
            if (t[pk] - t[i]) < 4.0 and thr[pk] < 15:
                k2 = min(n, pk + int(0.6 * fs))
                pkR = np.abs(d["gyroADC[0]"][pk:k2]).max()
                pkP = np.abs(d["gyroADC[1]"][pk:k2]).max()
                spmax = max(np.abs(spR[pk:k2]).max(), np.abs(spP[pk:k2]).max())
                z3p = np.abs(d["debug[5]"][pk:k2] * 16).max() / 1000
                b0drop = b0s[max(0, pk - int(0.3 * fs)):k2]
                print(f"    t={t[pk]:5.1f}s thrmax={thr[i:pk].max():3.0f}%  peakR/P={pkR:5.0f}/{pkP:5.0f} "
                      f"sp_max={spmax:4.0f} z3P|{z3p:4.0f}k| b0scl {b0drop.max():.2f}->{b0drop.min():.2f}")
                found += 1
                i = k2
                continue
            i = pk
        i += 1
    if not found:
        print("    нет событий")

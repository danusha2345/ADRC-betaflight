#!/usr/bin/env python3
"""jmsweng 2026-07-15 b4 logs (DAKEFPVF405, 2300 kV 5"): ring characterization,
gate epochs, takeoff detail, hover collective, z3 debug-rail episodes.

Usage: analyze_jmsweng.py <csv> [label]
Same tone metric as pr15400-b4/analyze_b4.py (1 s Hann, 50% overlap, dominant
PSD peak 10-40 Hz, tone RMS = peak +-2 Hz, fraction of 5-100 Hz RMS).
Motor range on this board: motorOutput 158..2047.

The wide-band section scans gyroUnfilt up to 200 Hz in calm windows; NOTE the
log rate is ~988 Hz with no anti-alias decimation, so high-frequency peaks may
be aliases of content above Nyquist (e.g. motor harmonics) - frequencies there
identify "a strong high-frequency line exists", not its true frequency.
"""
import csv as csvmod
import sys
import numpy as np

MOTOR_MIN, MOTOR_MAX = 158.0, 2047.0

def load(path):
    with open(path) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
            "gyroUnfilt[0]", "gyroUnfilt[1]",
            "setpoint[0]", "setpoint[1]",
            "debug[0]", "debug[1]", "debug[2]", "debug[3]", "debug[4]", "debug[5]", "debug[7]",
            "motor[0]", "motor[1]", "motor[2]", "motor[3]",
            "accSmooth[2]", "vbatLatest (V)"]
    use, names = [], []
    for c in cols:
        if c in idx:
            use.append(idx[c]); names.append(c)
    data = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=use)
    return {c: data[:, k] for k, c in enumerate(names)}

def tone_in_window(x, fs, flo=10.0, fhi=40.0):
    n = len(x)
    if n < 256:
        return np.nan, np.nan, np.nan
    w = np.hanning(n)
    X = np.fft.rfft((x - x.mean()) * w)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    psd = (np.abs(X) ** 2) / (fs * (w ** 2).sum())
    band = (f >= flo) & (f <= fhi)
    pk = np.argmax(psd * band)
    fpk = f[pk]
    df = f[1] - f[0]
    tone = (f >= fpk - 2) & (f <= fpk + 2)
    tone_rms = np.sqrt(psd[tone].sum() * df * 2)
    tot = (f >= 5) & (f <= 100)
    tot_rms = np.sqrt(psd[tot].sum() * df * 2)
    return fpk, tone_rms, tot_rms

def main():
    path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else path
    d = load(path)
    t = d["time (us)"] * 1e-6
    t -= t[0]
    fs = 1.0 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000.0) / 10.0
    gate = np.sign(d["debug[7]"])
    motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    coll = (motors.mean(axis=0) - MOTOR_MIN) / (MOTOR_MAX - MOTOR_MIN) * 100.0
    motors_on = motors.mean(axis=0) > MOTOR_MIN + 20
    print(f"########## {label}  fs={fs:.0f} Hz  dur={t[-1]:.1f}s ##########")

    flips = np.where(np.diff(gate) != 0)[0]
    print(f"gate: start={'OPEN' if gate[10] > 0 else 'closed'}, flips={len(flips)}, "
          f"open {(gate > 0).mean()*100:.0f}%: "
          + ", ".join(f"{t[i]:.1f}s({'open' if gate[i+1] > 0 else 'CLOSE'})" for i in flips[:8]))

    # hover collective: steady-stick, level-ish, gate-open windows
    sp_ok = (np.abs(d["setpoint[0]"]) < 30) & (np.abs(d["setpoint[1]"]) < 30)
    win = int(fs); hop = win // 2
    hovers = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if gate[sl].mean() > 0.99 and sp_ok[sl].all() and thr[sl].std() < 2 and motors_on[sl].all():
            hovers.append(coll[sl].mean())
    if hovers:
        print(f"steady-stick collective: median {np.median(hovers):.1f}% "
              f"(p25 {np.percentile(hovers,25):.1f} / p75 {np.percentile(hovers,75):.1f}, n={len(hovers)})")

    # tone by throttle bin + worst windows
    rows = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if gate[sl].mean() < 0.9 or not motors_on[sl].all():
            continue
        fR, aR, totR = tone_in_window(d["gyroADC[0]"][sl], fs)
        fP, aP, totP = tone_in_window(d["gyroADC[1]"][sl], fs)
        a, fq, tot = (aR, fR, totR) if aR >= aP else (aP, fP, totP)
        rows.append((t[s], thr[sl].mean(), fq, a, a / tot if tot > 0 else 0))
    rows = np.array(rows)
    print("\n-- tone by throttle bin (airborne windows) --")
    print(f"{'thr bin':>8} {'n':>4} {'f med':>6} {'amp med':>8} {'amp p90':>8} {'frac med':>8}")
    for lo in range(0, 80, 10):
        m = (rows[:, 1] >= lo) & (rows[:, 1] < lo + 10)
        if m.sum() < 3:
            continue
        print(f"{lo:>4}-{lo+10:<4} {int(m.sum()):>4} {np.median(rows[m,2]):>6.1f} "
              f"{np.median(rows[m,3]):>8.2f} {np.percentile(rows[m,3],90):>8.2f} {np.median(rows[m,4]):>8.2f}")
    print("-- worst 8 windows by tone amp --")
    for r in rows[np.argsort(-rows[:, 3])[:8]]:
        print(f"  t={r[0]:6.1f}s thr={r[1]:4.0f}% f={r[2]:5.1f}Hz amp={r[3]:7.2f} frac={r[4]:.2f}")

    # takeoff detail: first 4 s after gate opens
    if len(flips):
        i0 = flips[0] + 1
        sl = slice(i0, min(i0 + int(4 * fs), len(t)))
        fR, aR, _ = tone_in_window(d["gyroADC[0]"][sl], fs)
        fP, aP, _ = tone_in_window(d["gyroADC[1]"][sl], fs)
        print(f"\n-- takeoff (4 s after gate open @ {t[i0]:.1f}s): roll {aR:.1f} deg/s @ {fR:.1f} Hz, "
              f"pitch {aP:.1f} deg/s @ {fP:.1f} Hz; thr {thr[sl].mean():.0f}%")

    # z3 debug-rail episodes (roll deb[2], pitch deb[5])
    for ch, ax in (("debug[2]", "roll"), ("debug[5]", "pitch")):
        if ch not in d:
            continue
        railed = np.abs(d[ch]) >= 32700
        if not railed.any():
            print(f"z3 {ax}: no debug-rail samples")
            continue
        # group into episodes
        idxs = np.where(railed)[0]
        gaps = np.where(np.diff(idxs) > fs * 0.2)[0]
        starts = np.r_[idxs[0], idxs[gaps + 1]]
        ends = np.r_[idxs[gaps], idxs[-1]]
        print(f"z3 {ax}: {railed.mean()*100:.2f}% samples at debug rail, {len(starts)} episodes:")
        for s0, e0 in list(zip(starts, ends))[:10]:
            gy = np.abs(d["gyroADC[0 ]".replace(" ", "")][s0:e0+1]).max() if ax == "roll" else np.abs(d["gyroADC[1]"][s0:e0+1]).max()
            print(f"  t={t[s0]:6.1f}-{t[e0]:.1f}s thr={thr[s0:e0+1].mean():3.0f}% "
                  f"|gyro_{ax}|max={gy:5.0f} deg/s acc_z_min={d['accSmooth[2]'][s0:e0+1].min()/2048:.2f}g")

    # wide-band scan of gyroUnfilt in calm windows (see aliasing note in the docstring)
    calm = (np.abs(d["setpoint[0]"]) < 40) & (np.abs(d["setpoint[1]"]) < 40)
    wrows = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if not (gate[sl] > 0).all() or not calm[sl].all():
            continue
        out = [t[s], thr[sl].mean()]
        for ax in (0, 1):
            x = d[f"gyroUnfilt[{ax}]"][sl]
            w = np.hanning(len(x))
            X = np.fft.rfft((x - x.mean()) * w)
            f = np.fft.rfftfreq(len(x), 1 / fs)
            psd = np.abs(X) ** 2 / (fs * (w ** 2).sum())
            band = (f >= 10) & (f <= 200)
            pk = np.argmax(psd * band)
            df = f[1] - f[0]
            out += [f[pk], np.sqrt(psd[(f >= f[pk]-3) & (f <= f[pk]+3)].sum() * df * 2)]
        wrows.append(out)
    wrows = np.array(wrows)
    if len(wrows):
        print("\n-- wide-band gyroUnfilt (calm windows, 10-200 Hz; aliasing caveat applies) --")
        for r in wrows[np.argsort(-wrows[:, 3])[:6]]:
            print(f"  t={r[0]:6.1f}s thr={r[1]:4.0f}% roll {r[2]:6.1f}Hz/{r[3]:5.2f} "
                  f"pitch {r[4]:6.1f}Hz/{r[5]:5.2f}")
        print(f"  median peak f: roll {np.median(wrows[:,2]):.0f} Hz, "
              f"pitch {np.median(wrows[:,4]):.0f} Hz over {len(wrows)} windows")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""b4 verification-flight analysis vs b3 and the pre-remediation baseline.

Metrics per log:
  1. Oscillation: sliding-window PSD of gyro roll/pitch, dominant tone in
     10-40 Hz, amplitude (RMS deg/s) and frequency, binned by throttle %.
  2. b0-scale (debug[7]/100) modulation in steady-stick windows (ADRC-019).
  3. Punch->chop rebound: peak |gyro| in the 0.6 s after a throttle chop.
  4. Zero-throttle segments: gyro RMS + tone amplitude while gate open.
  5. Gate epochs: debug[7] sign at start, mid-air sign flips (ADRC-017/020).
"""
import csv as csvmod
import sys
import numpy as np

def load(path):
    with open(path) as f:
        rdr = csvmod.reader(f)
        hdr = [h.strip() for h in next(rdr)]
    idx = {name: i for i, name in enumerate(hdr)}
    cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
            "gyroUnfilt[0]", "gyroUnfilt[1]", "debug[2]", "debug[5]", "debug[6]",
            "debug[7]", "motor[0]", "motor[1]", "motor[2]", "motor[3]",
            "setpoint[0]", "setpoint[1]", "setpoint[3]",
            "accSmooth[0]", "accSmooth[1]", "accSmooth[2]"]
    use = [idx[c] for c in cols]
    data = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=use)
    d = {c: data[:, k] for k, c in enumerate(cols)}
    return d

def tone_in_window(x, fs, flo=10.0, fhi=40.0):
    """Dominant tone in [flo,fhi]: (freq, rms_amplitude_of_tone_band, total_rms_5_100)"""
    n = len(x)
    if n < 256:
        return np.nan, np.nan, np.nan
    w = np.hanning(n)
    X = np.fft.rfft((x - x.mean()) * w)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    psd = (np.abs(X) ** 2) / (fs * (w ** 2).sum())
    band = (f >= flo) & (f <= fhi)
    if not band.any():
        return np.nan, np.nan, np.nan
    pk = np.argmax(psd * band)
    fpk = f[pk]
    df = f[1] - f[0]
    tone_band = (f >= fpk - 2) & (f <= fpk + 2)
    tone_rms = np.sqrt(psd[tone_band].sum() * df * 2)
    tot = (f >= 5) & (f <= 100)
    tot_rms = np.sqrt(psd[tot].sum() * df * 2)
    return fpk, tone_rms, tot_rms

def analyze(path, label):
    d = load(path)
    t = d["time (us)"] * 1e-6
    fs = 1.0 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000.0) / 10.0          # %
    gate = np.sign(d["debug[7]"])
    b0scale = np.abs(d["debug[7]"]) / 100.0
    motors_on = np.mean([d[f"motor[{i}]"] for i in range(4)], axis=0) > 150
    dur = t[-1] - t[0]
    print(f"\n########## {label}  fs={fs:.0f} Hz  dur={dur:.1f}s ##########")

    # 5. gate epochs
    flips = np.where(np.diff(gate) != 0)[0]
    open_frac = (gate > 0).mean()
    print(f"gate: start={'OPEN' if gate[10] > 0 else 'closed'}, sign flips={len(flips)}, open {open_frac*100:.0f}% of log")
    if len(flips):
        ft = [f"{t[i]-t[0]:.1f}s({'open' if gate[i+1]>0 else 'CLOSE'})" for i in flips[:8]]
        print("  flips at:", ", ".join(ft))

    # 1. oscillation vs throttle bins (airborne = gate open)
    win = int(fs * 1.0); hop = win // 2
    rows = []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if gate[sl].mean() < 0.9 or not motors_on[sl].all():
            continue
        th = thr[sl].mean()
        fR, aR, totR = tone_in_window(d["gyroADC[0]"][sl], fs)
        fP, aP, totP = tone_in_window(d["gyroADC[1]"][sl], fs)
        fU, aU, _ = tone_in_window(d["gyroUnfilt[0]"][sl], fs)
        rows.append((th, fR, aR, totR, fP, aP, totP, aU))
    rows = np.array(rows) if rows else np.zeros((0, 8))
    print(f"airborne windows: {len(rows)}")
    print("thr_bin |  n | roll: f(Hz) tone(deg/s) med/p90 | pitch: f(Hz) tone med/p90 | unfilt roll tone")
    for lo in range(0, 60, 5):
        m = (rows[:, 0] >= lo) & (rows[:, 0] < lo + 5) if len(rows) else np.array([], bool)
        if m.sum() < 3:
            continue
        r = rows[m]
        print(f"{lo:3d}-{lo+5:<3d} |{m.sum():3d} |"
              f"  {np.median(r[:,1]):5.1f}  {np.median(r[:,2]):6.2f}/{np.percentile(r[:,2],90):6.2f}    |"
              f"  {np.median(r[:,4]):5.1f}  {np.median(r[:,5]):6.2f}/{np.percentile(r[:,5],90):6.2f} |"
              f"  {np.median(r[:,7]):6.2f}")

    # 2. b0-scale modulation in steady windows
    stds, swings = [], []
    for s in range(0, len(t) - win, hop):
        sl = slice(s, s + win)
        if gate[sl].mean() < 0.9:
            continue
        if np.abs(d["setpoint[0]"][sl]).max() > 30 or np.abs(d["setpoint[1]"][sl]).max() > 30:
            continue
        if thr[sl].std() > 2.0:
            continue
        stds.append(b0scale[sl].std())
        swings.append(b0scale[sl].max() - b0scale[sl].min())
    if stds:
        print(f"b0-scale steady windows: n={len(stds)}, std med={np.median(stds):.3f} p90={np.percentile(stds,90):.3f}, "
              f"swing med={np.median(swings):.2f} p90={np.percentile(swings,90):.2f} max={max(swings):.2f}")

    # 3. punch->chop rebound
    events = 0
    print("punch->chop events (peak |gyro R/P| deg/s in 0.6s after chop):")
    i = 0
    n = len(t)
    while i < n - int(fs):
        if thr[i] > 50 and gate[i] > 0:
            j = i
            while j < n - 1 and thr[j] > 20:
                j += 1
            if thr[j] < 12 and (t[j] - t[i]) < 3.0:
                k2 = min(n, j + int(0.6 * fs))
                pkR = np.abs(d["gyroADC[0]"][j:k2]).max()
                pkP = np.abs(d["gyroADC[1]"][j:k2]).max()
                spR = np.abs(d["setpoint[0]"][j:k2]).max()
                spP = np.abs(d["setpoint[1]"][j:k2]).max()
                # только если пилот не командовал вращение
                if spR < 60 and spP < 60:
                    events += 1
                    z3p = d["debug[5]"][j:k2] * 16
                    print(f"  t={t[j]-t[0]:6.1f}s thr {thr[i-1]:.0f}->%.0f" % thr[j],
                          f" peakR={pkR:6.1f} peakP={pkP:6.1f}  z3_pitch max|{np.abs(z3p).max()/1000:.0f}k|")
                i = k2
            else:
                i = j
        i += 1
    if not events:
        print("  (не найдено чистых панч-чопов)")

    # 4. zero-throttle airborne segments
    zt = (thr < 3) & (gate > 0) & motors_on
    # сегменты >= 0.8 s
    segs = []
    s0 = None
    for i in range(len(zt)):
        if zt[i] and s0 is None:
            s0 = i
        elif not zt[i] and s0 is not None:
            if t[i] - t[s0] >= 0.8:
                segs.append((s0, i))
            s0 = None
    print(f"zero-throttle airborne segments >=0.8s: {len(segs)}")
    for s, e in segs[:6]:
        sl = slice(s, e)
        fR, aR, _ = tone_in_window(d["gyroADC[0]"][sl], fs)
        acc = np.sqrt(d["accSmooth[0]"][sl]**2 + d["accSmooth[1]"][sl]**2 + d["accSmooth[2]"][sl]**2) / 2048.0
        print(f"  t={t[s]-t[0]:5.1f}-{t[e]-t[0]:5.1f}s gyroR RMS={d['gyroADC[0]'][sl].std():5.1f} "
              f"tone {fR:4.1f}Hz {aR:5.1f} deg/s |acc|~{np.median(acc):.2f}g")

    # z3 clipping
    for ch, name in ((d["debug[2]"], "z3R"), (d["debug[5]"], "z3P"), (d["debug[6]"], "z3Y")):
        clip = (np.abs(ch) > 32000).mean()
        if clip > 0.001:
            print(f"z3 clip: {name} at rail {clip*100:.1f}% of samples")

BASE = "/home/danik/Projects_and_coding/ADRC-betaflight/blackbox/bvandevliet/"
logs = [
    ("b4/btfl_001.01.csv", "b4 log1 (1.8s)"),
    ("b4/btfl_002.01.csv", "b4 log2 (28s)"),
    ("b4/btfl_003.01.csv", "b4 log3 (41s)"),
    ("b4/btfl_004.01.csv", "b4 log4 (22s)"),
    ("btfl_AIR2.01.csv",   "b3 AIR2 (ref, 19s)"),
    ("btfl_ACRO2.01.csv",  "b3 ACRO2 (ref, 31s)"),
    ("btfl_002-ACRO.01.csv", "PRE-REMEDIATION baseline (71s)"),
]
for p, lab in logs:
    try:
        analyze(BASE + p, lab)
    except Exception as e:
        print(f"\n{lab}: FAILED {e}")

#!/usr/bin/env python3
"""8ksal8 Pavo20 Pro II (BETAFPVF405_ELRS, b5 543f1a5ff, SQRT law) — b0 sweep, 2026-07-24/25.

Sessions (headers): log1 b0 = 5000/5000/5000, log2 = 3000/3000/3000,
log3 = 2000/1500/2000. All three: pid_type = ADRC, debug_mode = ADRC,
adrc_b0_law = 1 (SQRT), wc = 40/40/40, wo = 120/120/100, hover 50, liftoff 52,
motor_poles = 12, motorOutput 198..2047, thrust_linear = 0.

Run after: for f in btfl_00*.bbl; do blackbox_decode --debug \
    --unit-frame-time us "$f"; done

Sections:
  1. per-log overview: gate, collective (from motor output, not stick), b0 scale
  2. tracking error, one windowed criterion for all axes
  3. the log3 oscillation: is it in the loop, and is the line real?
     - per-motor and yaw-differential band energy (the 4-motor MEAN cancels a
       yaw oscillation - that is the wrong signal to check it with)
     - per-segment peak frequency stability vs the local noise floor
     - 1x RPM from eRPM with the header's 12 poles, to rule out an RPM line
  4. latency: cross-spectral group delay with real magnitude-squared coherence
     (|H| is NOT coherence - conflating them was a review finding here)
  5. current draw at matched collective, and dose-response within log3
"""
import csv

import numpy as np

CFG = {1: "b0 5000/5000/5000", 2: "b0 3000/3000/3000", 3: "b0 2000/1500/2000"}
MIN_OUT, MAX_OUT, POLES = 198.0, 2047.0, 12
HOVER_SET, LIFTOFF_SET = 50.0, 52.0

WANT = ["time (us)", "rcCommand[3]", "debug[6]", "debug[7]",
        "gyroUnfilt[0]", "gyroUnfilt[1]", "gyroUnfilt[2]",
        "setpoint[0]", "setpoint[1]", "setpoint[2]",
        "axisP[0]", "axisI[0]", "axisD[0]", "axisP[1]", "axisI[1]", "axisD[1]",
        "axisP[2]", "axisI[2]", "axisD[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "eRPM[0]", "eRPM[1]", "eRPM[2]", "eRPM[3]",
        "amperageLatest (A)", "vbatLatest (V)"]


def load(fname):
    with open(fname) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        cols = [c for c in WANT if c in hdr]
        idx = [hdr.index(c) for c in cols]
        rows = []
        for line in r:
            try:
                rows.append([float(line[i]) for i in idx])
            except (ValueError, IndexError):
                pass
    a = np.array(rows)
    d = {c: a[:, j] for j, c in enumerate(cols)}
    t = d["time (us)"] / 1e6
    d["_t"] = t - t[0]
    d["_fs"] = 1 / np.median(np.diff(d["_t"]))
    airborne = d["debug[7]"] >= 0          # debug[7] sign = liftoff gate latch
    d["_open"] = airborne
    d["_sl"] = slice(int(np.argmax(airborne)),
                     len(airborne) - int(np.argmax(airborne[::-1])))
    mot = np.mean([d[f"motor[{i}]"] for i in range(4)], axis=0)
    d["_coll"] = (mot - MIN_OUT) / (MAX_OUT - MIN_OUT) * 100
    d["_thr"] = (d["rcCommand[3]"] - 1000) / 10
    return d


def band_rms(x, fs, f1, f2):
    """Amplitude-corrected RMS in [f1, f2] of one hanning-windowed block."""
    x = np.asarray(x, float)
    x = x - x.mean()
    X = np.fft.rfft(x * np.hanning(len(x)))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = (f >= f1) & (f <= f2)
    return np.sqrt(2 * np.sum(np.abs(X[m]) ** 2) * (8 / 3)) / len(x)


def med_band(x, fs, f1, f2, seconds=4.0):
    n = int(seconds * fs)
    x = np.asarray(x, float)
    segs = x[:len(x) // n * n].reshape(-1, n)
    return float(np.median([band_rms(s, fs, f1, f2) for s in segs]))


def calm_windows(d, axes=(0, 1, 2), sp_std=15.0, sp_max=20.0, hop=0.5):
    """Yield slices of 1 s where every listed axis had a quiet setpoint."""
    fs = d["_fs"]
    w = int(round(fs))
    for st in range(d["_sl"].start, d["_sl"].stop - w, int(hop * w)):
        ws = slice(st, st + w)
        if all(np.std(d[f"setpoint[{a}]"][ws]) < sp_std
               and np.max(np.abs(d[f"setpoint[{a}]"][ws])) < sp_max for a in axes):
            yield ws


D = {n: load(f"btfl_00{n}.01.csv") for n in (1, 2, 3)}

print("=== 1. overview: gate, collective from motor output, applied b0 scale ===")
print("    (collective = mean of 4 motors mapped through motorOutput 198..2047;")
print(f"     adrc_hover_throttle = {HOVER_SET:.0f}, adrc_liftoff_throttle = {LIFTOFF_SET:.0f})")
for n in (1, 2, 3):
    d = D[n]
    t, sl = d["_t"], d["_sl"]
    i0 = sl.start
    scale = np.abs(d["debug[7]"][sl]) / 100.0
    coll = d["_coll"][sl]
    print(f"  log{n} {CFG[n]}: airborne {(sl.stop - sl.start) / d['_fs']:5.1f} s | "
          f"gate opens {t[i0]:5.2f} s at stick {d['_thr'][i0]:4.1f} % | "
          f"collective med {np.median(coll):4.1f} % max {coll.max():4.1f} % | "
          f"b0 scale med {np.median(scale):.2f} max {scale.max():.2f}")
    if coll.max() < LIFTOFF_SET:
        print("      -> collective never reached adrc_liftoff_throttle: the gate can only "
              "have opened through the gyro path")
    if coll.max() < HOVER_SET:
        print("      -> collective never reached adrc_hover_throttle: the b0 schedule "
              "(SQRT here) never engaged, so this flight tests a FIXED b0")

print()
print("=== 2. tracking error, one criterion (1 s windows, per-axis calm gate) ===")
for n in (1, 2, 3):
    d = D[n]
    out = []
    for a, nm in ((0, "roll"), (1, "pitch"), (2, "yaw")):
        v = [np.sqrt(np.mean((d[f"gyroUnfilt[{a}]"][ws] - d[f"setpoint[{a}]"][ws]) ** 2))
             for ws in calm_windows(d, axes=(a,))]
        out.append(f"{nm} {np.median(v):5.1f} (n={len(v):3d})" if v else f"{nm} n/a")
    print(f"  log{n} {CFG[n]}: RMS dps  " + " | ".join(out))

print()
print("=== 3. the log3 oscillation ===")
print("  40-60 Hz band RMS (median over 4 s segments of the airborne stretch):")
for n in (1, 2, 3):
    d = D[n]
    fs, sl = d["_fs"], d["_sl"]
    m = [d[f"motor[{i}]"][sl] for i in range(4)]
    # QUAD_X order 0=RR(CCW) 1=FR(CW) 2=RL(CW) 3=FL(CCW): yaw torque = CCW - CW
    yawmix = (m[0] + m[3] - m[1] - m[2]) / 4
    print(f"  log{n} {CFG[n]}:")
    print("      motors " + " ".join(f"{med_band(x, fs, 40, 60):6.1f}" for x in m) +
          f" | 4-motor MEAN {med_band(np.mean(m, axis=0), fs, 40, 60):5.2f}"
          f" | yaw-mix {med_band(yawmix, fs, 40, 60):6.1f}")
    for a, nm in ((0, "roll"), (1, "pitch"), (2, "yaw")):
        print(f"      {nm:5s} gyro {med_band(d[f'gyroUnfilt[{a}]'][sl], fs, 40, 60):6.2f} dps | "
              f"axisP {med_band(d[f'axisP[{a}]'][sl], fs, 40, 60):6.2f} "
              f"axisI {med_band(d[f'axisI[{a}]'][sl], fs, 40, 60):6.2f} "
              f"axisD {med_band(d[f'axisD[{a}]'][sl], fs, 40, 60):6.2f}")

print("  is the line real? per 4 s segment: yaw peak in 35-65 Hz vs local floor")
for n in (1, 2, 3):
    d = D[n]
    fs, sl = d["_fs"], d["_sl"]
    nfft = int(4 * fs)
    x = d["gyroUnfilt[2]"][sl]
    segs = x[:len(x) // nfft * nfft].reshape(-1, nfft)
    f = np.fft.rfftfreq(nfft, 1 / fs)
    b = (f >= 35) & (f <= 65)
    pk, amp, snr = [], [], []
    for s in segs:
        S = np.abs(np.fft.rfft((s - s.mean()) * np.hanning(nfft)))
        i = int(np.argmax(S[b]))
        pk.append(f[b][i])
        amp.append(S[b][i] / nfft * 4)                      # hanning amplitude correction
        far = np.abs(f[b] - f[b][i]) > 3
        snr.append(S[b][i] / max(np.median(S[b][far]), 1e-9))
    er = np.mean([d[f"eRPM[{i}]"][sl] for i in range(4)], axis=0)
    mech = np.median(er) * 100 / (POLES / 2) / 60           # eRPM field = erpm/100
    print(f"  log{n}: peak med {np.median(pk):5.2f} Hz  p10-p90 {np.percentile(pk, 10):5.2f}-"
          f"{np.percentile(pk, 90):5.2f}  amp {np.median(amp):6.2f} dps  "
          f"peak/floor {np.median(snr):6.1f}x  |  1x RPM {mech:5.0f} Hz")

print("  how much of the airborne time is ringing? (1 s windows, yaw 40-60 Hz > 5 dps)")
for n in (1, 2, 3):
    d = D[n]
    fs, sl = d["_fs"], d["_sl"]
    w = int(round(fs))
    hits, tot, first, last = 0, 0, None, None
    for st in range(sl.start, sl.stop - w, w):
        ws = slice(st, st + w)
        tot += 1
        if band_rms(d["gyroUnfilt[2]"][ws], fs, 40, 60) > 5:
            hits += 1
            first = d["_t"][st] if first is None else first
            last = d["_t"][st] + 1
    span = f"{first:5.1f}-{last:5.1f} s" if hits else "-"
    print(f"  log{n}: {hits:3d}/{tot:3d} windows ({hits / tot * 100:3.0f} %)  span {span}")

print()
print("=== 4. latency: group delay 2-10 Hz with magnitude-squared coherence ===")
for n in (1, 2, 3):
    d = D[n]
    fs, sl = d["_fs"], d["_sl"]
    w = int(round(2 * fs))
    out = []
    for a, nm in ((0, "roll"), (1, "pitch")):
        sxx = syy = sxy = None
        used = 0
        for st in range(sl.start, sl.stop - w, w // 2):
            ws = slice(st, st + w)
            sp = d[f"setpoint[{a}]"][ws]
            if np.std(sp) < 40:                            # need real stick activity
                continue
            used += 1
            win = np.hanning(w)
            X = np.fft.rfft((sp - sp.mean()) * win)
            g = d[f"gyroUnfilt[{a}]"][ws]
            Y = np.fft.rfft((g - g.mean()) * win)
            sxx = np.abs(X) ** 2 if sxx is None else sxx + np.abs(X) ** 2
            syy = np.abs(Y) ** 2 if syy is None else syy + np.abs(Y) ** 2
            sxy = Y * np.conj(X) if sxy is None else sxy + Y * np.conj(X)
        if not used:
            out.append(f"{nm} n/a")
            continue
        f = np.fft.rfftfreq(w, 1 / fs)
        b = (f >= 2) & (f <= 10)
        coh = np.abs(sxy) ** 2 / np.maximum(sxx * syy, 1e-12)
        H = sxy / np.maximum(sxx, 1e-12)
        tau = -np.polyfit(f[b], np.unwrap(np.angle(H[b])), 1)[0] / (2 * np.pi) * 1000
        out.append(f"{nm} tau {tau:5.1f} ms (coh {np.median(coh[b]):.2f}, "
                   f"|H| {np.median(np.abs(H[b])):.2f}, n={used})")
    print(f"  log{n} {CFG[n]}: " + " | ".join(out))

print()
print("=== 5. current at matched collective (27-31 %) with calm sticks ===")
inside = []
for n in (1, 2, 3):
    d = D[n]
    fs = d["_fs"]
    amps, colls, rings, pw, times = [], [], [], [], []
    for ws in calm_windows(d):
        c = np.median(d["_coll"][ws])
        if not 27 <= c <= 31:
            continue
        a_ = float(np.mean(d["amperageLatest (A)"][ws]))
        v_ = float(np.mean(d["vbatLatest (V)"][ws]))
        amps.append(a_)
        pw.append(a_ * v_)
        colls.append(c)
        rings.append(band_rms(d["gyroUnfilt[2]"][ws], fs, 40, 60))
        times.append(d["_t"][ws.start])
    if not amps:
        print(f"  log{n}: no matched windows")
        continue
    print(f"  log{n} {CFG[n]}: n={len(amps):2d}  {np.mean(amps):5.2f} A  {np.mean(pw):5.1f} W  "
          f"at collective {np.mean(colls):4.1f} %  | yaw 40-60 Hz {np.median(rings):5.1f} dps")
    if n == 3:
        inside = (np.array(times), np.array(rings), np.array(amps), np.array(pw))

if len(inside):
    t3, r3, a3, p3 = inside

    def resid(y, x):
        k, b_ = np.polyfit(x, y, 1)
        return y - (k * x + b_)

    print("  within log3 (dose-response; battery sag co-varies, hence the partial):")
    print(f"      corr(ring, current) {np.corrcoef(r3, a3)[0, 1]:+.2f}  "
          f"corr(ring, power) {np.corrcoef(r3, p3)[0, 1]:+.2f}")
    print(f"      partial | time: current {np.corrcoef(resid(r3, t3), resid(a3, t3))[0, 1]:+.2f}  "
          f"power {np.corrcoef(resid(r3, t3), resid(p3, t3))[0, 1]:+.2f}  (n={len(r3)})")

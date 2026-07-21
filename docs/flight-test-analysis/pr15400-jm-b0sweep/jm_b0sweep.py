#!/usr/bin/env python3
"""jmsweng DAKEFPV, 2026-07-20: b0-law hover A/B (btfl_laws.bbl, 5 sessions)
and FIXED-law b0 sweep 1000..8000 (btfl_b0sweep.bbl, 11 sessions).

Run after decoding both files in this directory:
    blackbox_decode --debug --unit-frame-time us btfl_laws.bbl
    blackbox_decode --debug --unit-frame-time us btfl_b0sweep.bbl

Methods notes (corrections vs the first-pass analysis, after internal review):
- band RMS from a one-sided rfft of N samples is sqrt(2*sum|X_k|^2)/N — the
  first pass carried a spurious extra x2 (validated against a synthetic
  22 Hz / 64 dps sine: true band RMS 45.3, corrected formula 45.3);
- all sweep metrics are computed on the contiguous gate-open slice only,
  masked BEFORE any filtering, so pre-liftoff transients cannot leak into
  the gate-open numbers through a whole-log FFT;
- debug[7] (ADRC debug mode) = applied b0 scale x100, negative while gated.
"""
import csv
import numpy as np

FS_NOM = 988.0


def load(fname, cols):
    with open(fname) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        idx = [hdr.index(c) for c in cols]
        rows = []
        for line in r:
            try:
                rows.append([float(line[i]) for i in idx])
            except (ValueError, IndexError):
                pass
    a = np.array(rows)
    return {c: a[:, j] for j, c in enumerate(cols)}


def band_rms(x, fs, f1, f2):
    x = x - np.mean(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = (f >= f1) & (f <= f2)
    return np.sqrt(2 * np.sum(np.abs(X[m]) ** 2)) / len(x)


def highpass(x, fs, fc):
    X = np.fft.rfft(x - np.mean(x))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    X[f < fc] = 0
    return np.fft.irfft(X, len(x))


COLS = ["time (us)", "rcCommand[3]", "debug[7]", "gyroUnfilt[0]",
        "gyroUnfilt[1]", "setpoint[0]", "setpoint[1]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]"]


def calm_windows(d, s, fs):
    """1 s windows inside slice s with calm R/P setpoints (std < 30 dps both).
    Returns per-window max-axis 18-32 Hz band RMS values."""
    W = int(round(fs))
    vals = []
    for w in range((s.stop - s.start) // W):
        ws = slice(s.start + w * W, s.start + (w + 1) * W)
        if (np.std(d["setpoint[0]"][ws]) < 30 and
                np.std(d["setpoint[1]"][ws]) < 30):
            vals.append(max(band_rms(d["gyroUnfilt[0]"][ws], fs, 18, 32),
                            band_rms(d["gyroUnfilt[1]"][ws], fs, 18, 32)))
    return vals

print("=== btfl_laws.bbl: b0-law A/B (session1 = turtle-mode arm, ignore) ===")
LAWS = ["(turtle)", "QUADRATIC", "SQRT", "LINEAR", "FIXED"]
for n in range(1, 6):
    d = load(f"btfl_laws.{n:02d}.csv", COLS)
    t = d["time (us)"] / 1e6
    fs = 1 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000) / 10
    d7 = d["debug[7]"]
    op = d7[d7 >= 0]
    air = thr > 10
    if air.sum() < 300:
        print(f"log{n} {LAWS[n-1]:10s} dur {t[-1]-t[0]:5.1f}s  (too short / ground)")
        continue
    frac_above = (op > 100).mean() * 100
    print(f"log{n} {LAWS[n-1]:10s} dur {t[-1]-t[0]:5.1f}s  medThr {np.median(thr[air]):4.1f}%  "
          f"debug7 min/max {op.min():.0f}/{op.max():.0f}  >100: {frac_above:.2f}% "
          f"({(op > 100).sum()/fs:.2f}s)  gyro18-32 RMS "
          f"{max(band_rms(d['gyroUnfilt[0]'][air], fs, 18, 32), band_rms(d['gyroUnfilt[1]'][air], fs, 18, 32)):.1f} dps")

print()
print("=== btfl_b0sweep.bbl: FIXED law, wc40/wo100, metrics on contiguous gate-open slice ===")
B0 = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 5500, 6500, 7500]
res = []
for n in range(1, 12):
    d = load(f"btfl_b0sweep.{n:02d}.csv", COLS)
    t = d["time (us)"] / 1e6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    o = d["debug[7]"] >= 0
    thr = (d["rcCommand[3]"] - 1000) / 10
    i0 = int(np.argmax(o))
    i1 = len(o) - int(np.argmax(o[::-1]))
    s = slice(i0, i1)
    tr = np.diff(o.astype(int))
    n_open = int((tr == 1).sum())
    dur_open = (t[i1 - 1] - t[i0]) if o.any() else 0.0
    mm = (d["motor[0]"] + d["motor[1]"] + d["motor[2]"] + d["motor[3]"])[s] / 4
    g0, g1 = d["gyroUnfilt[0]"][s], d["gyroUnfilt[1]"][s]
    mdev = np.sqrt(np.mean(highpass(mm, fs, 5) ** 2))
    brms = max(band_rms(g0, fs, 18, 32), band_rms(g1, fs, 18, 32))
    spec = np.abs(np.fft.rfft((g0 - np.mean(g0)) * np.hanning(len(g0))))
    fr = np.fft.rfftfreq(len(g0), 1 / fs)
    b = (fr >= 5) & (fr <= 120)
    cw = calm_windows(d, s, fs)
    res.append((B0[n - 1], t[-1], n_open, t[i0], dur_open,
                thr[i0], np.median(thr[s]), mdev, brms,
                fr[b][np.argmax(spec[b])], cw))
for (b0, dur, n_open, t_open, dur_open, thr_open, thr_med, mdev, brms,
     fpk, cw) in sorted(res):
    cwtxt = (f"calmWin n={len(cw)} med {np.median(cw):4.1f} max {max(cw):4.1f}"
             if cw else "calmWin n=0")
    print(f"b0={b0:5d} log {dur:4.1f}s  opens={n_open} @{t_open:4.2f}s  open {dur_open:4.2f}s  "
          f"thr@open {thr_open:4.1f}% med {thr_med:4.1f}%  motorHP-RMS {mdev:6.1f}  "
          f"gyro18-32 RMS {brms:5.1f} dps  domPk {fpk:5.1f} Hz  {cwtxt}")

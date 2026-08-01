#!/usr/bin/env python3
"""Estimate the effective control-input gain b0 from a flown log (ADRC-021).

The observer's model is gyro_dot = b0 * u, with u = pidSum (P+I+D+F, before the
mixer's PID_MIXER_SCALING). The real loop adds actuator lag (DShot frame, ESC
and motor time constant), so a plain time-domain least squares fits ~0 even
when the two signals are strongly related: the lag rotates the regressor out of
phase. This script therefore estimates the transfer function

    H(f) = P_ug(f) / P_uu(f)   (Welch cross-spectrum)

and reports |H| (the gain, i.e. b0) together with the ordinary coherence and
the group delay implied by the phase. |H| alone is never evidence: rows with
low coherence are reported as such and must not be quoted as a b0 estimate.

Usage: python3 b0_ident.py <decoded.csv> [...]
"""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.signal import csd, welch, coherence, savgol_filter

AXES = ("roll", "pitch", "yaw")
BAND = (8.0, 35.0)          # closed-loop sanity band
IV_BAND = (1.5, 12.0)       # where a pilot command actually carries energy
COH_MIN = 0.6


def headers(path):
    hp = path.parent / (path.name[:-4] + ".headers.csv")
    out = {}
    if hp.exists():
        for row in csv.reader(hp.open()):
            if len(row) >= 2:
                out[row[0]] = row[1]
    return out


def load(path, names):
    with path.open() as f:
        head = [h.strip() for h in next(csv.reader(f))]
    idx = {n: i for i, n in enumerate(head)}
    use = [n for n in names if n in idx]
    arr = np.genfromtxt(path, delimiter=",", skip_header=1,
                        usecols=[idx[n] for n in use], invalid_raise=False)
    arr = arr[~np.isnan(arr).any(axis=1)]
    return {n: arr[:, i] for i, n in enumerate(use)}


def main(path):
    path = Path(path)
    h = headers(path)
    lo, hi = (int(v) for v in h.get("motorOutput", "48,1847").split(","))
    names = ["time (us)", "debug[7]"]
    for i in range(3):
        names += [f"axisP[{i}]", f"axisI[{i}]", f"axisD[{i}]", f"axisF[{i}]",
                  f"gyroUnfilt[{i}]", f"setpoint[{i}]"]
    names += [f"motor[{i}]" for i in range(4)]
    d = load(path, names)

    t = d["time (us)"] / 1e6
    fs = 1 / np.median(np.diff(t))
    motors = np.vstack([d[f"motor[{i}]"] for i in range(4)])
    collective = (motors.mean(axis=0) - lo) / (hi - lo) * 100
    gate = d["debug[7]"] > 0
    scale = np.abs(d["debug[7]"]) / 100
    ok = (gate & (collective > 12) & (motors.max(axis=0) < hi)
          & (motors.min(axis=0) > lo))
    if ok.sum() < fs * 3:
        print(f"{path.name}: not enough clean airborne data")
        return

    b0_set = [float(x) for x in h.get("adrcB0", "0,0,0").split(",")]
    smed = float(np.median(scale[ok]))
    print(f"\n=== {path.name} ===")
    print(f"  set b0 {h.get('adrcB0')} x b0-scale med {smed:.2f} -> "
          f"{', '.join(f'{b*smed:.0f}' for b in b0_set)} effective; "
          f"collective med {np.median(collective[ok]):.0f} %, "
          f"clean airborne {ok.sum()/fs:.0f} s")

    nper = int(min(8192, 2 ** np.floor(np.log2(ok.sum() / 8))))
    for a in range(3):
        u = (d[f"axisP[{a}]"] + d[f"axisI[{a}]"] + d[f"axisD[{a}]"]
             + d.get(f"axisF[{a}]", np.zeros_like(t)))[ok]
        g = d[f"gyroUnfilt[{a}]"]
        win = max(5, int(round(0.0025 * fs)) | 1)
        gdot = savgol_filter(g, win, 2, deriv=1, delta=1 / fs)[ok]

        # Closed-loop identity check: inside the loop u is computed FROM the
        # gyro, so P_ug/P_uu just returns the controller's own b0 and proves
        # nothing about the airframe. Kept only as a sanity readout.
        f_, pug = csd(u, gdot, fs=fs, nperseg=nper)
        _, puu = welch(u, fs=fs, nperseg=nper)
        _, cxy = coherence(u, gdot, fs=fs, nperseg=nper)
        band = (f_ >= BAND[0]) & (f_ <= BAND[1])
        cl = band & (cxy >= COH_MIN)
        cl_gain = (float(np.sum(np.abs((pug / puu)[cl]) * puu[cl]) / np.sum(puu[cl]))
                   if cl.sum() >= 3 else float("nan"))

        # Instrumental-variable estimate: the pilot's setpoint is exogenous to
        # gyro noise, so H_plant = P(r, gdot) / P(r, u) is not biased by the
        # feedback path. Restricted to bins where the command actually carries
        # energy into both signals.
        r = d[f"setpoint[{a}]"][ok]
        fr, prg = csd(r, gdot, fs=fs, nperseg=nper)
        _, pru = csd(r, u, fs=fs, nperseg=nper)
        _, crg = coherence(r, gdot, fs=fs, nperseg=nper)
        _, cru = coherence(r, u, fs=fs, nperseg=nper)
        ivband = (fr >= IV_BAND[0]) & (fr <= IV_BAND[1])
        good = ivband & (crg >= COH_MIN) & (cru >= COH_MIN)
        if good.sum() < 3:
            print(f"  {AXES[a]:5s} closed-loop |H| {cl_gain:6.0f} (identity, not the plant); "
                  f"IV: command coherence too low in {IV_BAND[0]}-{IV_BAND[1]} Hz "
                  f"(max gyro {crg[ivband].max():.2f} / u {cru[ivband].max():.2f})")
            continue
        Hiv = prg[good] / pru[good]
        w = np.abs(pru[good])
        b0_hat = float(np.sum(np.abs(Hiv) * w) / np.sum(w))
        ph = np.unwrap(np.angle(Hiv))
        slope = np.polyfit(fr[good], ph, 1)[0] if good.sum() >= 4 else float("nan")
        delay_ms = -slope / (2 * np.pi) * 1000
        print(f"  {AXES[a]:5s} b0_meas(IV) {b0_hat:6.0f} vs set*scale {b0_set[a]*smed:6.0f} "
              f"-> set/meas {b0_set[a]*smed/b0_hat:5.2f} | "
              f"band {fr[good].min():.1f}-{fr[good].max():.1f} Hz, n={good.sum()}, "
              f"coh_rg {np.mean(crg[good]):.2f}/coh_ru {np.mean(cru[good]):.2f}, "
              f"lag {delay_ms:5.1f} ms | closed-loop |H| {cl_gain:6.0f}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)

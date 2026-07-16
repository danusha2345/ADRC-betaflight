#!/usr/bin/env python3
"""Cascade-ESO experiment log (004, p3): sliding 1 s windows, dominant
10-40 Hz tone per axis; prints windows with tone RMS > 8 deg/s and the log
duration. Run from this directory after decoding the .bbl files.
"""
import csv as csvmod
import numpy as np

PATH = "btfl_004_p3_cascade_eso.01.csv"

def main():
    with open(PATH) as f:
        hdr = [h.strip() for h in next(csvmod.reader(f))]
    idx = {n: i for i, n in enumerate(hdr)}
    cols = ["time (us)", "rcCommand[3]", "gyroADC[0]", "gyroADC[1]"]
    d = np.genfromtxt(PATH, delimiter=",", skip_header=1,
                      usecols=[idx[c] for c in cols])
    D = {c: d[:, k] for k, c in enumerate(cols)}
    t = D["time (us)"] * 1e-6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    thr = (D["rcCommand[3]"] - 1000) / 10
    print(f"dur={t[-1]:.1f}s fs={fs:.0f}")
    win = int(fs)
    for s in range(0, len(t) - win, win // 2):
        sl = slice(s, s + win)
        for ax in (0, 1):
            x = D[f"gyroADC[{ax}]"][sl]
            w = np.hanning(len(x))
            X = np.fft.rfft((x - x.mean()) * w)
            f = np.fft.rfftfreq(len(x), 1 / fs)
            psd = np.abs(X) ** 2 / (fs * (w ** 2).sum())
            band = (f >= 10) & (f <= 40)
            pk = np.argmax(psd * band)
            df = f[1] - f[0]
            amp = np.sqrt(psd[(f >= f[pk]-2) & (f <= f[pk]+2)].sum() * df * 2)
            if amp > 8:
                print(f"t={t[s]:5.1f}s thr={thr[sl].mean():3.0f}% ax{ax} "
                      f"f={f[pk]:5.1f}Hz amp={amp:6.1f}")

if __name__ == "__main__":
    main()

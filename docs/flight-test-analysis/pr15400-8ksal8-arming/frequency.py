#!/usr/bin/env python3
"""Frequency of the ground oscillation, by three methods that fail differently.

Blackbox timestamps here are not uniformly spaced, so feeding them straight to
Welch silently assumes a grid that does not exist and quantises the answer to
the bin width. This script therefore reports:

  1. Welch on an explicitly resampled uniform grid, with the bin width printed
     and several nperseg values, so the quantisation is visible;
  2. Lomb-Scargle on the real timestamps, which needs no uniform grid;
  3. peak-to-peak spacing in the time domain, which needs no spectrum at all.

Agreement across the three is what licenses quoting a frequency at all, and the
spread across them is what sets how many digits may be quoted.
"""
import numpy as np
from scipy.signal import welch, find_peaks
from scipy.signal import lombscargle

from common import load, time_s, gyro, fs_nominal, resample_uniform

RUNAWAYS = ['b8_Airmode_on_ADRC_btfl_001', 'b9_Airmode_on_ADRC_btfl_002']
AXES = {0: 'roll', 1: 'pitch', 2: 'yaw'}


def growth_window(t, peak, level=20.0):
    idx = np.where(peak > level)[0]
    return t >= t[idx[0]] if idx.size else np.zeros_like(t, bool)


def welch_peak(t, x, fs, nperseg):
    tu, xu = resample_uniform(t, x, fs)
    f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(nperseg, len(xu)))
    band = (f > 5) & (f < 350)
    return f[band][np.argmax(P[band])], f[1] - f[0]


def lomb_peak(t, x, lo=5.0, hi=120.0):
    """Lomb-Scargle on the real timestamps; no resampling, no uniform grid."""
    freqs = np.linspace(lo, hi, 20001)
    w = 2 * np.pi * freqs
    xc = x - x.mean()
    P = lombscargle(t, xc, w, precenter=True, normalize=True)
    return freqs[np.argmax(P)]


def peak_spacing(t, x, min_intervals=8, max_spread=0.40):
    """Median spacing of prominent positive peaks, or None if the peaks do not
    describe a periodic signal.

    Prominence rejects the several local maxima that sit inside one cycle of a
    noisy waveform; without it this estimator reports harmonics of the true
    rate. The result is withheld unless there are enough intervals and they are
    tight enough (IQR/median below max_spread) to mean anything.
    """
    xc = x - x.mean()
    sd = np.std(xc)
    if sd == 0:
        return None
    idx, _ = find_peaks(xc, prominence=sd)
    if idx.size < 3:
        return None
    dt = np.diff(t[idx])
    dt = dt[(dt > 0.005) & (dt < 0.200)]          # 5-200 Hz
    if dt.size < min_intervals:
        return None
    q75, q25 = np.percentile(dt, [75, 25])
    spread = (q75 - q25) / np.median(dt)
    if spread > max_spread:
        return None
    return 1.0 / np.median(dt), dt.size, spread


def main():
    print('# Frequency of the ground oscillation\n')
    for stem in RUNAWAYS:
        d = load(stem)
        t = time_s(d)
        gu = gyro(d, filtered=False)
        peak = np.abs(gyro(d)).max(axis=0)
        win = growth_window(t, peak)
        fs = fs_nominal(d)

        dt = np.diff(d['time (us)'])
        print(f'== {stem}')
        print(f'   frames {d["_n"]}, span {t[-1]:.3f} s, mean rate {fs:.2f} Hz')
        print(f'   frame interval: median {np.median(dt)/1e3:.3f} ms, '
              f'min {dt.min()/1e3:.3f}, max {dt.max()/1e3:.3f} - NOT uniform')
        print(f'   growth window: {t[win][0]*1e3:.1f}..{t[-1]*1e3:.1f} ms, {int(win.sum())} frames')

        for ax in (0, 1, 2):
            x = gu[ax][win]
            tw = t[win]
            row = [f'   {AXES[ax]:5s}']
            for nper in (128, 256, 512):
                if len(x) < nper:
                    continue
                fpk, df = welch_peak(tw, x, fs, nper)
                row.append(f'Welch/{nper}: {fpk:5.2f} Hz (bin {df:.2f})')
            fl = lomb_peak(tw, x)
            row.append(f'Lomb: {fl:5.2f} Hz')
            ps = peak_spacing(tw, x)
            row.append(f'peaks: {ps[0]:5.2f} Hz (n={ps[1]}, IQR/med {ps[2]:.2f})'
                       if ps else 'peaks: inconclusive')
            print('  '.join(row))
        print()

    print('Read the spread across methods as the uncertainty. Quoting the Welch bin')
    print('centre to two decimals would be reporting the grid, not the signal.')
    print()
    print('Nyquist for these logs is about 400 Hz, so a low-frequency alias of some')
    print('unmeasured high-frequency content is not required to explain the tone - but')
    print('the blackbox stream is decimated (P interval 4) and cannot rule folding out.')


if __name__ == '__main__':
    main()

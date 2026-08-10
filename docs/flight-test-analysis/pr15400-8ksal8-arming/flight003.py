#!/usr/bin/env python3
"""The 96 s flight (log 003): what it does and does not establish.

It is the control that shows this tune flies. It is not a proof of signal
cleanliness: there is no matched baseline in this corpus, so band fractions
are reported with their absolute amplitudes next to them, and with the
segmentation and window spelled out, because a fraction alone is unreadable.
"""
import os

import numpy as np
from scipy.signal import welch

from common import (load, time_s, gyro, motors, clipped_frames, gate_open_state,
                    fs_nominal, resample_uniform, headers, DEBUG_CLIP, pidsum_limits)

STEM = 'b9_Airmode_switch_ADRC_btfl_003'
NPERSEG = int(os.environ.get('WELCH_NPERSEG', '1024'))
NPERSEG_ALT = NPERSEG // 2      # printed alongside, so the method sensitivity is visible
BAND = (18.0, 26.0)          # the roll/pitch band the ground oscillation sat in
REF = (8.0, 120.0)           # reference band for the fraction
MIN_RUN_S = 2.0              # continuous stretch required before a PSD is taken


def continuous_runs(t, mask, min_len_s, max_gap_s=0.010):
    """Index slices where mask holds continuously, with no timestamp gap."""
    runs, start = [], None
    for i in range(len(t)):
        broken = (not mask[i]) or (i > 0 and t[i] - t[i - 1] > max_gap_s)
        if mask[i] and start is None:
            start = i
        elif broken and start is not None:
            if t[i - 1] - t[start] >= min_len_s:
                runs.append((start, i))
            start = None if not mask[i] else i
    if start is not None and t[-1] - t[start] >= min_len_s:
        runs.append((start, len(t)))
    return runs


def run_psd(t, x, fs, nperseg):
    """PSD of one continuous run, on an explicitly resampled uniform grid."""
    tu, xu = resample_uniform(t, x, fs)
    if len(xu) < nperseg:
        return None
    f, P = welch(xu - xu.mean(), fs=fs, nperseg=nperseg)
    return f, P


def band_metrics(f, P):
    """Fraction of reference-band power inside BAND, and in-band RMS.

    Both come from the same (already averaged) PSD: averaging power first and
    taking the square root once is not the same as averaging per-run RMS.
    """
    band = (f >= BAND[0]) & (f <= BAND[1])
    ref = (f >= REF[0]) & (f <= REF[1])
    df = f[1] - f[0]
    return P[band].sum() / P[ref].sum(), np.sqrt(P[band].sum() * df)


def main():
    d = load(STEM)
    t = time_s(d)
    fs = fs_nominal(d)
    gu = gyro(d, filtered=False)
    m = motors(d)
    gate = gate_open_state(d)

    print(f'# Flight log 003\n')
    print(f'  frames {d["_n"]}, span {t[-1]:.3f} s, mean rate {fs:.2f} Hz')
    print(f'  gate first open at {t[np.argmax(gate)]:.3f} s; '
          f'open in {int(gate.sum())}/{d["_n"]} frames')
    print(f'  throttle stick {d["rcCommand[3]"].min():.0f}..{d["rcCommand[3]"].max():.0f}, '
          f'commanded collective setpoint[3] {d["setpoint[3]"].min():.0f}..{d["setpoint[3]"].max():.0f}')
    print(f'  vbat {d["vbatLatest (V)"].min():.2f}..{d["vbatLatest (V)"].max():.2f} V, '
          f'current max {d["amperageLatest (A)"].max():.2f} A '
          f'(sag compensation is off, so motorOutputRange is not moving)')
    for i, ax in enumerate('RPY'):
        print(f'  gyroUnfilt {ax}: RMS {np.sqrt(np.mean(gu[i]**2)):.2f}, '
              f'max |{np.abs(gu[i]).max():.0f}| deg/s')
    print(f'  frames with any motor at 2047: {int((m.max(axis=0) >= 2047).sum())} '
          f'({100*(m.max(axis=0) >= 2047).mean():.3f} %)')

    clips = clipped_frames(d)
    h = headers(STEM)
    b0 = [float(x) for x in h['adrcB0'].split(',')]
    lim_rp, lim_y = pidsum_limits(STEM)
    print(f'\n  z3 debug-channel clipping (ADRC-029): the field is lrintf(z3/16) in an')
    print(f'  int16, so the reconstructed value saturates at |z3| = {DEBUG_CLIP * 16}.')
    print(f'  That is a telemetry limit, not the controller\'s internal clamp. The')
    print(f'  internal clamp is pidsum_limit*b0, and both factors are recorded:')
    print(f'  pidsum_limit {lim_rp:.0f} / {lim_rp:.0f} / {lim_y:.0f} (yaw) against '
          f'b0 {b0[0]:.0f}/{b0[1]:.0f}/{b0[2]:.0f}, i.e.')
    print(f'  {lim_rp*b0[0]:.0f} / {lim_rp*b0[1]:.0f} / {lim_y*b0[2]:.0f} - '
          f'far above the telemetry endpoint:')
    for ax in 'RPY':
        print(f'    {ax}: {clips[ax]} frames ({100.0*clips[ax]/d["_n"]:.4f} %)')

    print(f'\n  Band content, {BAND[0]:.0f}-{BAND[1]:.0f} Hz as a fraction of '
          f'{REF[0]:.0f}-{REF[1]:.0f} Hz, gate open only.')
    print('  Taken only over continuous runs of at least '
          f'{MIN_RUN_S:.0f} s with no timestamp gap > 10 ms,')
    print('  each run resampled onto a uniform grid; the PSDs themselves are averaged')
    print('  across runs (duration-weighted), and the fraction and RMS are derived once')
    print('  from that average - averaging per-run RMS instead would not be the same.')
    print('  The absolute in-band RMS is printed beside the fraction because a large')
    print('  fraction of a small number is still a small number.\n')

    thr_pct = d['setpoint[3]'] / 10.0
    print(f'  {"throttle":>12s} {"runs":>5s} {"seconds":>8s} '
          + f'| nperseg {NPERSEG}: ' + ' '.join(f'{ax + " frac":>9s} {ax + " RMS":>8s}' for ax in 'RP')
          + f' | nperseg {NPERSEG_ALT}: ' + ' '.join(f'{ax + " frac":>9s} {ax + " RMS":>8s}' for ax in 'RP'))
    for lo, hi in ((0, 20), (20, 40), (40, 100)):
        mask = gate & (thr_pct >= lo) & (thr_pct < hi)
        runs = continuous_runs(t, mask, MIN_RUN_S)
        if not runs:
            print(f'  {f"{lo}-{hi}%":>12s} {"0":>5s}  (no continuous run >= '
                  f'{MIN_RUN_S:.0f} s)')
            continue
        secs = sum(t[b - 1] - t[a] for a, b in runs)
        cells = []
        for nper in (NPERSEG, NPERSEG_ALT):
          for ax in (0, 1):
            psds, weights, freqs = [], [], None
            for a, b in runs:
                r = run_psd(t[a:b], gu[ax][a:b], fs, nper)
                if r:
                    freqs, P = r
                    psds.append(P); weights.append(t[b - 1] - t[a])
            if psds:
                P_avg = np.average(np.vstack(psds), axis=0, weights=np.array(weights))
                frac, rms = band_metrics(freqs, P_avg)
                cells.append(f'{frac:9.2%} {rms:8.3f}')
            else:
                cells.append(f'{"-":>9s} {"-":>8s}')
        print(f'  {f"{lo}-{hi}%":>12s} {len(runs):5d} {secs:8.1f} | ' + ' '.join(cells[:2])
              + ' | ' + ' '.join(cells[2:]))
    print('\n  RMS is deg/s of gyroUnfilt inside the band.')
    print(f'  Both window lengths are printed so the method sensitivity is visible without')
    print(f'  a second run (override the first with WELCH_NPERSEG). The pitch fraction in')
    print(f'  particular moves with the choice, so it must not be quoted alone.')


if __name__ == '__main__':
    main()

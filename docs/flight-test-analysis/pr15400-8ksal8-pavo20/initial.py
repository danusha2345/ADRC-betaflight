#!/usr/bin/env python3
"""The pre-reduction Pavo20 log against the finished flight.

The tester supplied the log flown on the numbers he later reduced by 5 %
(wc/wo 115/115/135 over 150/150/161, b0 4750/3053/11721 - the header diff
below is programmatic). The question it can address: does anything
oscillation-like separate the two tunes, in particular in hard turns?

Instrument notes, stated up front:
  - both logs are single flights on different days/conditions, and they
    differ in more than the tune (RC deadbands 0 vs 3/10, thr_hover,
    altitude_prefer_baro; the finished flight contains a GPS rescue whose
    span is EXCLUDED from its windows here). Nothing below is a controlled
    single-variable comparison.
  - "turn windows" are 1-s windows whose |roll or pitch setpoint| exceeds
    300 deg/s at some point - commanded hard rotation. Inside such windows
    manoeuvre-tracking lag lives at low frequency, so the metric is the
    5-30 Hz band RMS of the tracking error (the propwash/oscillation band
    the earlier analysis found), not the raw error.
  - the quiet-setpoint oscillation test is the same one wobble.py runs,
    both thresholds.
"""
import numpy as np
from scipy.signal import welch

from common import STEMS, headers, load, motors, time_s, fs_nominal, text_column
from wobble import quiet_windows, union_s

INITIAL = 'Finished_initial_btfl_001'
FINAL = 'Finished_minus_5_percent_btfl_001'
PER_ARM = {'Firmware date', 'Log start datetime', 'vbatref',
           'rc_smoothing_active_cutoffs_ff_sp_thr', 'rc_smoothing_rx_smoothed'}
SP_TURN = 300.0
BAND = (5.0, 30.0)


def band_rms_seg(t, x, lo, hi):
    fs = (len(t) - 1) / (t[-1] - t[0])
    tu = np.arange(t[0], t[-1], 1.0 / fs)
    xu = np.interp(tu, t, x)
    f, P = welch(xu - xu.mean(), fs=fs, nperseg=min(512, len(xu)))
    m = (f >= lo) & (f < hi)
    return float(np.sqrt(P[m].sum() * (f[1] - f[0])))


def rescue_span(stem):
    ph = text_column(stem, 'failsafePhase')
    d = load(stem)
    t = time_s(d)
    idx = [i for i in range(1, len(ph)) if ph[i] != ph[i - 1]]
    if len(idx) >= 2 and ph[idx[0]] == '6':
        return float(t[idx[0]]), float(t[idx[1]])
    return None


def turn_windows(stem, exclude=None):
    d = load(stem)
    t = time_s(d)
    fs = fs_nominal(d)
    win = int(fs)
    out = []
    for ax, nm in ((0, 'roll'), (1, 'pitch')):
        sp = d[f'setpoint[{ax}]']
        err = sp - d[f'gyroADC[{ax}]']
        for i in range(0, len(t) - win, win // 2):
            if exclude and exclude[0] <= t[i] <= exclude[1]:
                continue
            if np.abs(sp[i:i + win]).max() > SP_TURN:
                seg_t, e = t[i:i + win], err[i:i + win]
                v = band_rms_seg(seg_t, e, *BAND)
                fs2 = (len(seg_t) - 1) / (seg_t[-1] - seg_t[0])
                tu = np.arange(seg_t[0], seg_t[-1], 1 / fs2)
                eu = np.interp(tu, seg_t, e)
                f, P = welch(eu - eu.mean(), fs=fs2, nperseg=min(512, len(eu)))
                m = (f > 4) & (f < 100)
                out.append((v, float(t[i]), nm, float(f[m][np.argmax(P[m])])))
    return out


def main():
    print('# The pre-reduction log\n')
    import common
    print(f'SHA-256 of the decompressed .bbl:')
    print(f'  {INITIAL}.bbl  {common.sha256_gz(INITIAL)}')

    hi_, hf = headers(INITIAL), headers(FINAL)
    print('\nEvery header key that differs from the finished flight (union of')
    print('keys, per-arm measurement keys excluded):')
    for k in sorted(set(hi_) | set(hf)):
        if k in PER_ARM:
            continue
        if hi_.get(k) != hf.get(k):
            print(f'  {k}: {hi_.get(k)} -> {hf.get(k)}')
    print('  (initial -> finished; the adrc_* trio is the 5 % step, the deadbands')
    print('  and hover/baro settings changed alongside - see the addendum text)')

    d = load(INITIAL)
    t = time_s(d)
    m = motors(d)
    hi_end = float(headers(INITIAL)['motorOutput'].split(',')[1])
    med, p90 = [], []
    for ax in range(3):
        e = np.abs(d[f'setpoint[{ax}]'] - d[f'gyroADC[{ax}]'])
        med.append(np.median(e))
        p90.append(np.percentile(e, 90))
    print(f'\nBasics: span {t[-1]:.1f}s, vbat {d["vbatLatest (V)"].min():.2f}-'
          f'{d["vbatLatest (V)"].max():.2f} V, motor-rail samples {int((m >= hi_end).sum())}, '
          f'err med {"/".join(f"{v:.0f}" for v in med)}, '
          f'p90 {"/".join(f"{v:.0f}" for v in p90)} deg/s')
    phases = set(text_column(INITIAL, 'failsafePhase'))
    print('No failsafe activity: ' + ('confirmed, failsafePhase is IDLE on every frame'
          if phases == {'IDLE'} else f'NOT confirmed - phases seen: {sorted(phases)}'))

    print('\nQuiet-setpoint oscillation test (same instrument and thresholds as')
    print('wobble.py):')
    for sp_quiet, gy_loud in ((20.0, 40.0), (40.0, 40.0)):
        hits = quiet_windows(d, sp_quiet, gy_loud)
        if not hits:
            print(f'  setpoint SD < {sp_quiet:.0f}, gyro SD > {gy_loud:.0f}: none')
            continue
        print(f'  setpoint SD < {sp_quiet:.0f}, gyro SD > {gy_loud:.0f}: {len(hits)} window(s)')
        for lo, hi2, nm, gs, pk in hits[:8]:
            print(f'     t={lo:6.1f}s {nm:5s} gyro SD {gs:5.1f} deg/s, peak {pk:.1f} Hz')

    print(f'\nTurn windows (|roll or pitch setpoint| > {SP_TURN:.0f} deg/s inside a 1-s')
    print(f'window), {BAND[0]:.0f}-{BAND[1]:.0f} Hz band RMS of the tracking error; the')
    print('finished flight\'s GPS-rescue span is excluded from its windows:\n')
    rs = rescue_span(FINAL)
    for label, stem, excl in (('initial', INITIAL, None), ('finished', FINAL, rs)):
        tw = turn_windows(stem, exclude=excl)
        vals = [v for v, *_ in tw]
        print(f'  {label:9s} n={len(vals):3d}  median {np.median(vals):5.1f}  '
              f'p90 {np.percentile(vals, 90):5.1f}  max {max(vals):5.1f} deg/s')
    print('\n  Worst five turn windows of each, with the error peak frequency:')
    for label, stem, excl in (('initial', INITIAL, None), ('finished', FINAL, rs)):
        tw = sorted(turn_windows(stem, exclude=excl), reverse=True)
        for v, tt, nm, pk in tw[:5]:
            print(f'  {label:9s} {v:6.1f} dps @ t={tt:6.1f}s {nm:5s} (err peak {pk:.1f} Hz)')

    print('\n  Reading. The observed median is lower in the finished flight; the')
    print('  distributions overlap; the single worst window belongs to the')
    print('  finished flight; and both flights\' worst turn content peaks in the')
    print('  same 6-10 Hz band. The windows are 50 %-overlapped and there is one')
    print('  flight per tune, so no formal comparison is attempted and nothing')
    print('  is attributable to the tune. On instability specifically, only a')
    print('  negative statement is available: these two logs provide no')
    print('  separating evidence that the 5 % step removed an instability - and')
    print('  none that one existed. Oscillation inside high-setpoint windows is')
    print('  invisible to the quiet-setpoint instrument by construction, and the')
    print('  turn-window metric does not separate propwash, manoeuvre lag and')
    print('  loop instability from each other.')


if __name__ == '__main__':
    main()

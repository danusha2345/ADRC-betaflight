#!/usr/bin/env python3
"""What the "wobble" log's error bursts are, and what the instrument can say.

A tracking-error burst is not an oscillation if the setpoint itself is
oscillating - and in this log it is: the worst windows have the logged
setpoint and the gyro moving together at ~2-3 Hz. TWO honesty limits bound
what that observation means:

  - the wobble flight ran in ANGLE mode (boxes.py), and in ANGLE mode the
    logged rate setpoint is the OUTPUT of the self-level loop (pid.c), not
    the stick. "Setpoint quiet" therefore does not literally mean "stick
    quiet" in that log - and because that setpoint is computed from
    attitude error inside a feedback loop, setpoint/gyro moving together
    does not establish direction: the rhythm could be pilot input or the
    level loop responding to a disturbance. What the data supports is
    narrower: the bursts COINCIDE with logged setpoint activity, and no
    window with a QUIET logged setpoint shows an oscillating gyro in this
    log.
  - the quiet-setpoint test's thresholds are choices, not measurements. It
    is run below at two settings; the stricter one finds nothing in the
    wobble or RTH logs and four windows in the finished flight, the looser
    one admits windows in every log - windows with moderate setpoint
    activity, where lag and oscillation cannot be told apart. Any genuine
    oscillation hiding INSIDE high-setpoint windows is invisible to this
    instrument by construction.
"""
import numpy as np
from scipy.signal import welch

from common import STEMS, load, time_s, fs_nominal, text_column

AXES = [(0, 'roll'), (1, 'pitch'), (2, 'yaw')]


def quiet_windows(d, sp_quiet, gy_loud):
    t = time_s(d)
    fs = fs_nominal(d)
    win = int(fs)
    hits = []
    for ax, nm in AXES:
        spx, gyx = d[f'setpoint[{ax}]'], d[f'gyroADC[{ax}]']
        for i in range(0, len(t) - win, win // 2):
            s = spx[i:i + win]
            g = gyx[i:i + win]
            if s.std() < sp_quiet and g.std() > gy_loud:
                f, P = welch(g - g.mean(), fs=fs, nperseg=min(1024, win))
                m = (f > 2) & (f < 200)
                # real timestamps, first to last sample of the window - the
                # saved frames are not uniform, so t[i] + win/fs would be a
                # synthetic nominal end
                hits.append((float(t[i]), float(t[i + win - 1]), nm,
                             float(g.std()), float(f[m][np.argmax(P[m])])))
    return hits


def union_s(intervals):
    """Total length of the union of (t0, t1) intervals."""
    total, cur_lo, cur_hi = 0.0, None, None
    for lo, hi in sorted(intervals):
        if cur_hi is None or lo > cur_hi:
            if cur_hi is not None:
                total += cur_hi - cur_lo
            cur_lo, cur_hi = lo, hi
        else:
            cur_hi = max(cur_hi, hi)
    if cur_hi is not None:
        total += cur_hi - cur_lo
    return total


def main():
    print('# Setpoint-coincident motion vs oscillation\n')

    print('The worst roll tracking-error windows of the wobble log, with what the')
    print('logged setpoint was doing (1-s windows, stepped 0.25 s, top 5 by error')
    print('RMS). The flight is in ANGLE mode, so this setpoint is the self-level')
    print('loop\'s output - see the docstring:\n')
    d = load('wobble_btfl_036')
    t = time_s(d)
    fs = fs_nominal(d)
    win = int(fs)
    sp, gy = d['setpoint[0]'], d['gyroADC[0]']
    err = sp - gy
    scores = []
    for i in range(0, len(t) - win, win // 4):
        e = err[i:i + win]
        scores.append((float(np.sqrt(np.mean(e ** 2))), i))
    scores.sort(reverse=True)
    print(f'  {"t":>7s} {"err RMS":>8s} {"setpoint SD":>12s} {"gyro SD":>8s} {"err peak Hz":>12s}')
    for s, i in scores[:5]:
        seg = slice(i, i + win)
        e = err[seg]
        f, P = welch(e - e.mean(), fs=fs, nperseg=min(1024, len(e)))
        m = (f > 2) & (f < 200)
        pk = float(f[m][np.argmax(P[m])])
        print(f'  {t[i]:6.1f}s {s:8.1f} {sp[seg].std():12.1f} {gy[seg].std():8.1f} {pk:12.1f}')
    print('\n  The setpoint SD matches the gyro SD in every one of them: the gyro')
    print('  and the logged setpoint move together, gyro lagging. Direction is')
    print('  not established by that - the ANGLE-mode setpoint is itself loop')
    print('  output, so pilot rhythm and level-loop response to a disturbance')
    print('  are equally compatible with these traces.')

    print('\nThe quiet-setpoint test at two threshold settings (1-s windows,')
    print('any axis; sensitivity to the threshold is part of the finding):\n')
    finished_hits_strict = None
    for sp_quiet, gy_loud in ((20.0, 40.0), (40.0, 40.0)):
        print(f'  setpoint SD < {sp_quiet:.0f} deg/s AND gyro SD > {gy_loud:.0f} deg/s:')
        for stem in STEMS:
            hits = quiet_windows(load(stem), sp_quiet, gy_loud)
            if stem.startswith('Finished') and sp_quiet == 20.0:
                finished_hits_strict = hits
            if not hits:
                print(f'     {stem}: none')
                continue
            print(f'     {stem}: {len(hits)} window(s)')
            for lo, hi, nm, gs, pk in hits[:10]:
                print(f'        t={lo:6.1f}s {nm:5s} gyro SD {gs:5.1f} deg/s, peak {pk:.1f} Hz')
            if len(hits) > 10:
                print(f'        ... and {len(hits) - 10} more')
        print()

    print('At the strict setting the only surviving windows are in the finished')
    print('flight; the union of their real timestamp spans is:')
    u = union_s([(lo, hi) for lo, hi, *_ in finished_hits_strict])
    print(f'  {u:.2f} s total (the four windows overlap - they are two clusters)')

    print('\nContext for those windows: the finished flight contains a GPS rescue')
    print('(failsafePhase = 6; overview.py prints its bounds), and all four sit')
    print('inside it or at its exit. The "quiet setpoint" there is the rescue')
    print('autopilot flying while the simulated RX loss holds the sticks out of')
    print('the loop (boxes.py):\n')
    d = load('Finished_minus_5_percent_btfl_001')
    t = time_s(d)
    ph = text_column('Finished_minus_5_percent_btfl_001', 'failsafePhase')
    idx = [i for i in range(1, len(ph)) if ph[i] != ph[i - 1]]
    r_in, r_out = t[idx[0]], t[idx[1]]
    thr = d['rcCommand[3]']
    from common import motors
    m = motors(d)
    for lo, hi in ((181.5, 184.0), (188.5, 191.0)):
        w = (t >= lo) & (t < hi)
        where = ('inside the rescue' if hi <= r_out else
                 'straddling the rescue exit' if lo <= r_out else 'after the rescue')
        print(f'  t={lo:.1f}-{hi:.1f}s ({where}; rescue {r_in:.2f}-{r_out:.2f}s): '
              f'throttle reads {thr[w].min():.0f}-{thr[w].max():.0f}, '
              f'motor max {m[:, w].max():.0f}, vbat min {d["vbatLatest (V)"][w].min():.2f} V')
    print('\n  So at the strict setting the only oscillation-like content of the')
    print('  set is roll at 7-11 Hz, ~50 deg/s SD, during autopilot rescue flight')
    print('  on a pack sagged below 10 V and at the moment control returns.')
    print('  Whether anything here relates to what the tester felt in tight turns')
    print('  is not decidable from these logs: tight-turn windows have an active')
    print('  setpoint by definition, and this instrument discards them.')


if __name__ == '__main__':
    main()

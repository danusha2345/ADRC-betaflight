#!/usr/bin/env python3
"""Would Betaflight's runaway takeoff prevention have caught the ground events?

RTP's trigger (fc/core.c, subTaskPidController): any axis |pidData.Sum| >= 600
AND any gyro axis above its limit (15 deg/s roll/pitch, 50 yaw), held for a
CONTINUOUS 75 ms - the timer resets the moment the condition drops
(`else runawayTakeoffTriggerUs = 0`).

This script measures, for each ground-event log, the longest continuous stretch
where (a) the |Sum| condition alone holds and (b) the full trigger condition
holds, against that 75 ms requirement.

The full precondition list (all must hold for the check to run at all, and a
failure of any of them also resets the timer): armed, not fixed-wing,
runaway_takeoff_prevention enabled (default), runawayTakeoffCheckDisabled
false (it latches off for the battery after a detected takeoff), no Crash
Flip / temporary MSP disable / GPS Rescue, and motors considered running
(motor stop off, or Airmode enabled, or throttle not LOW).

Honesty notes, printed per log:
  - Sum is reconstructed as the sum of the LOGGED axis terms (P, I, D, F where
    present). RTP reads the same unclamped total (pidSum = P+I+D+F+S is
    assigned to pidData[].Sum before the mixer's pidSumLimit clamp; S is zero
    on a multirotor). Blackbox stores each term through lrintf, so the integer
    reconstruction can differ from the float Sum by a few units near the
    threshold; a 596..604 threshold sweep is printed to show the results do
    not hinge on that.
  - Term completeness varies BY LOG and is printed: dedlike's ADRC-028 arm and
    groundloop log 1 lack axisD[2] (blackbox gated it on the legacy yaw
    D-gain of 0), and a missing SIGNED term makes the yaw sum neither a lower
    nor an upper bound - those rows cannot support a runtime-RTP conclusion.
    Groundloop log 2 HAS all terms (the tester set yaw D = 1 exactly so the
    field would be logged).
  - A first-true-to-last-true stretch is NOT an upper bound on the runtime
    condition (it may have begun before the first saved true frame and ended
    after the last). The proper conservative upper bound printed below runs
    from the false sample preceding each true run to the false sample
    following it, and separately reports the largest inter-frame gap, inside
    which an entirely unsaved run could hide.
  - Whether the check was ENABLED at event time is not recoverable from any of
    these logs (neither the setting nor runawayTakeoffCheckDisabled is
    logged). This script answers "could the trigger condition have held",
    not "was the check enabled".
"""
import csv
import os
import sys

import numpy as np

# Usage: rtp_oscillation_check.py <decoded.csv> [<decoded.csv> ...]
# CSVs come from blackbox_decode (betaflight/blackbox-tools); see README.md in
# this directory for the exact fetch-and-decode commands for the three logs
# the accompanying issue cites.
LOGS = None  # filled from argv in __main__

SUM_THR = 600.0
GYRO_RP = 15.0
GYRO_YAW = 50.0
HOLD_MS = 75.0


def load(path):
    with open(path, newline='') as fh:
        rows = list(csv.DictReader(fh, skipinitialspace=True))
    d = {}
    for key in rows[0]:
        name = key.strip()
        try:
            d[name] = np.array([float(r[key]) for r in rows])
        except (ValueError, TypeError):
            continue
    return d


def bounded_run_ms(t_ms, mask):
    """Conservative UPPER bound on any run containing saved true frames: from the
    false sample before the run to the false sample after it. Returns
    (bound_ms, censored): censored is True when a run touches the capture edge,
    where no bracketing false sample exists and the bound is not a bound."""
    best, prev_false, censored = 0.0, None, False
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if prev_false is None or j >= n:
                censored = True
            lo = t_ms[prev_false] if prev_false is not None else t_ms[0]
            hi = t_ms[j] if j < n else t_ms[-1]
            best = max(best, hi - lo)
            i = j
        else:
            prev_false = i
            i += 1
    return best, censored


def accumulated_ms(t_ms, mask):
    """Sample-and-hold total condition-time: each true frame contributes the
    interval to the next saved frame. The zero-leak accumulator baseline."""
    total = 0.0
    for i in range(len(mask) - 1):
        if mask[i]:
            total += t_ms[i + 1] - t_ms[i]
    return total


def main():
    print('# Would RTP have fired? Trigger: any-axis |Sum| >= 600 AND gyro above')
    print(f'# limits (RP {GYRO_RP:.0f}, yaw {GYRO_YAW:.0f} deg/s), CONTINUOUS for {HOLD_MS:.0f} ms')
    print('# (a hair more in practice - the deadline check runs on the next PID loop).\n')
    hdr = (f'{"log":42s} {"terms":>6s} {"span":>7s} {"|Sum|max":>9s} '
           f'{"frames>=600":>12s} {"run<=":>9s} {"accum":>10s} {"maxgap":>8s} {"fires?":>7s}')
    print(hdr)
    for path in LOGS:
        label = os.path.basename(path)[:40]
        d = load(path)
        t_ms = (d['time (us)'] - d['time (us)'][0]) / 1e3
        gaps = np.diff(t_ms)

        sums = []
        terms_by_axis = []
        for ax in range(3):
            s = np.zeros(len(t_ms))
            used = ''
            for term in 'PIDF':
                key = f'axis{term}[{ax}]'
                if key in d:
                    s += d[key]
                    used += term
            terms_by_axis.append(used)
            sums.append(np.abs(s))
        complete = all(set('PIDF') <= set(u) for u in terms_by_axis)
        sum_peak = np.max(np.vstack(sums), axis=0)

        gyro_cond = ((np.abs(d['gyroADC[0]']) > GYRO_RP)
                     | (np.abs(d['gyroADC[1]']) > GYRO_RP)
                     | (np.abs(d['gyroADC[2]']) > GYRO_YAW))
        full = (sum_peak >= SUM_THR) & gyro_cond

        ub, censored = bounded_run_ms(t_ms, full)
        acc = accumulated_ms(t_ms, full)
        terms_str = ('/'.join(sorted(set(terms_by_axis)))
                     if len(set(terms_by_axis)) > 1 else terms_by_axis[0])
        if not complete:
            verdict = 'n/a*'
        elif censored:
            verdict = 'cens.'
        else:
            verdict = 'no' if ub < HOLD_MS else 'maybe'
        print(f'{label:42s} {terms_str:>6s} {t_ms[-1]/1e3:6.2f}s '
              f'{sum_peak.max():9.0f} {int((sum_peak >= SUM_THR).sum()):5d} '
              f'({100*(sum_peak >= SUM_THR).mean():4.1f}%) '
              f'{ub:7.1f}ms {acc:8.1f}ms {gaps.max():6.1f}ms {verdict:>7s}')

        # threshold sensitivity: the lrintf-per-term reconstruction can differ from the
        # float Sum by a few units, so show the bound is stable across 596..604
        ubs = []
        for thr in (596.0, 600.0, 604.0):
            m = (sum_peak >= thr) & gyro_cond
            ubs.append(bounded_run_ms(t_ms, m)[0])
        print(f'{"":42s} {"":6s} threshold 596/600/604 -> run<= '
              + ' / '.join(f'{u:.1f}' for u in ubs) + ' ms')

    print('\nReading the table. "run<=" is a conservative upper bound: the interval from')
    print('the saved false frame before each true run to the saved false frame after it,')
    print('so unsaved PID iterations inside it are accounted for; "maxgap" is the largest')
    print('inter-frame interval anywhere in the log, inside which an entirely unsaved run')
    print('could hide; "accum" is the sample-and-hold TOTAL condition-time over the whole')
    print('log - what a zero-leak accumulate-instead-of-hold variant of the detector')
    print('would collect. For rows with complete terms the bound is directly comparable')
    print('to the 75 ms requirement; "cens." marks a run touching the capture edge,')
    print('where no bound exists. Rows marked n/a* lack the yaw D term')
    print('(signed, so the reconstructed yaw sum bounds nothing) and support no')
    print('runtime-RTP conclusion; log 1 is additionally the quiet control arm, not an')
    print('event. Half-periods for scale: 1/(2*21 Hz) = 23.8 ms, 1/(2*34 Hz) = 14.7 ms -')
    print('but the defensible claim is only what is measured above, not a theorem that no')
    print('oscillation can ever hold the condition (an axis hand-off or a DC-biased')
    print('oscillation could).')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().split('\n')[0]
                 + '\nusage: rtp_oscillation_check.py <decoded.csv> [...]')
    LOGS = sys.argv[1:]
    main()

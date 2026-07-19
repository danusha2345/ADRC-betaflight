#!/usr/bin/env python3
"""Per-flight anomaly screen (added after the PR author's observation that
the pipelines never flagged the pathological FIXED flight).

The estimators use stick throttle only as a window *selector* (ring windows
require mean stick 10-35 %, punches 40 %->15 %), so a flight whose problem
lives at zero stick throttle silently contributes "0 windows" instead of an
alarm. This screen looks at every gate-open sample unconditionally:

1. zero-stick motor elevation: p90 of mean motor output over samples with
   stick throttle < 5 % - oscillation-driven thrust shows up here (the
   FIXED flight's ring holds ~660 at zero stick vs ~250 quiet);
2. sustained calm-stick ring: >= 2 consecutive 1 s windows (>= 1.5 s) whose
   dominant 10-40 Hz peak lands in 18-32 Hz with tone RMS > 20 deg/s, tone
   fraction > 0.5, AND calm roll/pitch setpoint (RMS < 30 deg/s both axes)
   - no throttle-band gate, so zero-throttle pathology is not excluded, but
   commanded maneuvers (which legitimately put energy at these frequencies)
   are.

Flag *BAD* on (1) only — thrust the pilot didn't command is unambiguous
(the FIXED flight sits at 993 vs <= 469 everywhere else). (2) is reported
as a diagnostic, not a flight-level flag: sustained calm-stick ring windows
exist in most b5 flights (the episodic ADRC-024 ignitions), so flagging on
them would mark healthy-but-ringing flights bad. Running this screen also
exposed a bias in b5_ab.py's ring table: its all-motors-above-floor gate
drops exactly the windows where the ring is deep enough to floor a motor,
so its "worst tone" column understates amplitude (e.g. SQRT pack1_001:
70 deg/s at 28 % stick throttle vs 12 in the gated table). Incidence
rankings are unaffected (the same gate applies to numerator and
denominator, and the original criterion agrees); amplitude claims must use
this screen's numbers. Thresholds are craft-calibrated for this corpus
(idle ~250), not universal.

Run from this directory after blackbox_decode --debug --unit-frame-time us *.bbl.
"""
import sys
import numpy as np

sys.path.insert(0, ".")
import b5_ab as B

MOTOR_P90_LIMIT = 500.0
TONE_LIMIT = 20.0
SP_CALM = 30.0


def screen(fname):
    d = B.loadcols(fname, ["time (us)", "rcCommand[3]", "gyroADC[0]",
                           "gyroADC[1]", "setpoint[0]", "setpoint[1]",
                           "debug[7]", "motor[0]", "motor[1]", "motor[2]",
                           "motor[3]"])
    t = d["time (us)"] * 1e-6
    t -= t[0]
    fs = 1 / np.median(np.diff(t))
    thr = (d["rcCommand[3]"] - 1000) / 10
    gate = d["debug[7]"] > 0
    meanmot = np.mean([d[f"motor[{i}]"] for i in range(4)], axis=0)

    zs = gate & (thr < 5)
    mot_p90 = np.percentile(meanmot[zs], 90) if zs.sum() > int(fs) else float("nan")

    win = int(fs)
    hits = []          # start times of calm-stick ring windows
    worst_tone = worst_f = 0.0
    for s in range(0, len(t) - win, win // 2):
        sl = slice(s, s + win)
        if not gate[sl].all():
            continue
        if max(np.sqrt(np.mean(d["setpoint[0]"][sl] ** 2)),
               np.sqrt(np.mean(d["setpoint[1]"][sl] ** 2))) > SP_CALM:
            continue
        for axis in (0, 1):
            f0, tone, frac = B.ring_tone(d[f"gyroADC[{axis}]"][sl], fs)
            if 18 <= f0 <= 32 and tone > TONE_LIMIT and frac > 0.5:
                hits.append(t[s])
                if tone > worst_tone:
                    worst_tone, worst_f = tone, f0
                break
    # sustained = two window starts within one hop (0.5 s) + margin
    hits.sort()
    sustained = any(b - a < 0.75 for a, b in zip(hits, hits[1:]))
    return mot_p90, sustained, len(hits), worst_f, worst_tone


def main():
    print(f"{'log':<28} {'law':<10} {'0-stick mot p90':>15} "
          f"{'calm-ring win':>13} {'worst':>10} {'flag':>6}")
    for fname, law in B.LOGS:
        mot_p90, sustained, nwin, f0, tone = screen(fname)
        bad = mot_p90 > MOTOR_P90_LIMIT
        w = f"{f0:.0f}Hz/{tone:.0f}" if nwin else "-"
        print(f"{fname:<28} {law:<10} {mot_p90:>15.0f} "
              f"{nwin:>10}{'(s)' if sustained else '   '} {w:>10} "
              f"{'*BAD*' if bad else 'ok':>6}")


if __name__ == "__main__":
    main()

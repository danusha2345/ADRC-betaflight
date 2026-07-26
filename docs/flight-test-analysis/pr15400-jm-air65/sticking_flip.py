#!/usr/bin/env python3
"""jmsweng Air65 II (BETAFPVG473_V2 / BMI270), 2026-07-25 — the inverted
"sticking" episode in flight 1 of the final-tune log (ADRC-027).

Headers (all 12 sessions identical): 543f1a5ff = b5 tag, pid_type = ADRC,
debug_mode = ADRC, wc 55 / wo 75 / b0 5000 (all axes), adrc_b0_law = 2
(LINEAR), hover 35, liftoff 40, motor_poles = 14, blackbox rate 402 Hz.

Pilot's sync: "visible ~12 s into the video, about six seconds in on the
blackbox for flight 1".

Run after: blackbox_decode --debug --unit-frame-time us air65_final_tune.bbl
Then: python3 sticking_flip.py   (reads the .01 csv = flight 1)
"""
import csv
import glob

import numpy as np

CSV = sorted(glob.glob("*.01.csv"))[0]
COLS = ["time (us)", "rcCommand[3]", "setpoint[1]", "setpoint[2]",
        "gyroUnfilt[1]", "motor[0]", "motor[1]", "motor[2]", "motor[3]",
        "debug[5]", "debug[7]"]

with open(CSV) as f:
    r = csv.reader(f)
    hdr = [h.strip() for h in next(r)]
    idx = [hdr.index(c) for c in COLS]
    rows = []
    for line in r:
        try:
            rows.append([float(line[i]) for i in idx])
        except (ValueError, IndexError):
            pass
a = np.array(rows)
d = {c: a[:, j] for j, c in enumerate(COLS)}
t = d["time (us)"] / 1e6
t -= t[0]
fs = 1 / np.median(np.diff(t))
mot = [d[f"motor[{i}]"] for i in range(4)]
thr = (d["rcCommand[3]"] - 1000) / 10

print(f"flight 1: fs {fs:.0f} Hz, dur {t[-1]:.1f} s")
print()
print("0.1 s windows through the flip (t = 5.2..6.3 s):")
print("   t   | sp_pitch gyro_pitch | thr%  | b0scale | z3_pitch")
W = int(0.1 * fs)
for st in range(int(5.2 * fs), int(6.3 * fs), W):
    ws = slice(st, st + W)
    print(f" {t[st]:5.2f} | {np.mean(d['setpoint[1]'][ws]):+8.0f} {np.mean(d['gyroUnfilt[1]'][ws]):+10.0f} | "
          f"{np.median(thr[ws]):5.1f} | {np.median(np.abs(d['debug[7]'][ws])) / 100:7.2f} | "
          f"{np.mean(d['debug[5]'][ws]) * 16:+9.0f}")

sl = (t >= 5.3) & (t <= 6.3)
sp1, gy1, tt = d["setpoint[1]"][sl], d["gyroUnfilt[1]"][sl], t[sl]
ipk = int(np.argmin(gy1))
print()
print(f"flip-entry overshoot: gyro peak {gy1[ipk]:+.0f} dps at t={tt[ipk]:.2f} "
      f"vs setpoint {sp1[ipk]:+.0f} at the same instant "
      f"(sp peak {sp1.min():+.0f})")
print(f"integrated pitch rotation 5.3-6.3 s: {np.trapezoid(gy1, tt):.0f} deg")

stall = (t >= 5.75) & (t <= 6.10)
sp_s, gy_s = d["setpoint[1]"][stall], d["gyroUnfilt[1]"][stall]
print(f"stall window 5.75-6.10 s ({stall.sum() / fs * 1000:.0f} ms): "
      f"sp med {np.median(sp_s):+.0f}, gyro med {np.median(gy_s):+.0f}, "
      f"deficit med {np.median(sp_s - gy_s):+.0f} dps")
sat = [(m[stall] >= 2040).mean() * 100 for m in mot]
print(f"motor time at 2047 during stall, per motor: {['%.0f%%' % x for x in sat]}"
      f"  (no motor at the idle floor)")
z5 = d["debug[5]"][stall]
print(f"z3_pitch at the debug log rail (|z3/16| >= 32700): {(np.abs(z5) >= 32700).mean() * 100:.0f}% "
      f"of stall samples - the LOG channel clip at +/-524k, not the controller clamp "
      f"(pidsum_limit x b0_eff ~ 5.9e6 here)")
print(f"yaw was not commanded through the event: max |sp_yaw| = "
      f"{np.abs(d['setpoint[2]'][sl]).max():.0f} dps")

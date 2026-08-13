# Pavo20 Pro II: the finished tune, two GPS rescues, and what "wobble" recorded

**Data**: three flight logs by @8ksal8 on a retuned Pavo20 Pro II (F405, 8k gyro / 4k PID, 3S,
b9 firmware `919116fed`), posted 2026-08-11 in PR #15400. Tune identical in all three headers:
`wc 109/109/128`, `wo 143/143/153`, `b0 4988/3206/12307`. Every number below is printed by
`overview.py`, `wobble.py` or `boxes.py`; none is hand-copied.

## Tracking metrics

| log | span | tracking err median R/P/Y (deg/s) | p90 | motor-rail frames |
|---|---|---|---|---|
| Finished_minus_5_percent | 320.5 s | 2/1/2 | 7/6/8 | 1401 |
| Return_to_home | 229.1 s | 2/1/1 | 5/5/8 | 0 |
| wobble | 126.7 s | 6/4/2 | 54/54/38 | 0 |

The finished-tune flight holds a 1–2 deg/s median over five minutes of real flying. Its 1401 rail
frames (0.1 % of motor samples) cluster in punch/chop moments and inside the rescue below. The
wobble row is not comparable to the other two: that flight ran in **ANGLE mode without airmode**
(`boxes.py` — mask ARM|ANGLE throughout, against acro + airmode box in the other two flights), so
its logged setpoint is the self-level loop's output and its error numbers measure a different
control chain.

## Both GPS rescues are on the record

The tester reported "a couple Fail safes / GPS rescues", and both are in the logs
(`overview.py`, `boxes.py`): the Return_to_home log records `failsafePhase` = 6
(`FAILSAFE_GPS_RESCUE`) from **61.03 s to 85.59 s** — a 24.6 s rescue — and the finished-tune
flight records a second one, **145.04 s to 189.98 s** (44.9 s). Both follow `BOXFAILSAFE` box
activity — a switch-simulated RX loss — with the box going active about **1.5 s before** each
phase-6 entry (the failsafe state machine walks its rx-loss stages in between; both timestamps
are printed by `boxes.py`). `BOXGPSRESCUE` never appears in the mask. The simulated loss is
also why `rcCommand` reads throttle 1000 inside the rescues: the sticks are not being read.
The RTH rescue never puts a motor at the upper endpoint; the finished-flight rescue does
briefly, where the next section's windows live. The masks also show POSHOLD/ALTHOLD box
activity after each rescue.

## What the "wobble" log's bursts are — and what the instrument can and cannot say

The log's worst tracking-error windows (roll error RMS up to 70.3 deg/s) all have **setpoint SD
matching gyro SD** (195.4–234.7 deg/s across those windows) at ~2–3 Hz: the gyro and the logged
setpoint move together, gyro lagging. Because this flight is in ANGLE mode, that logged
setpoint is the self-level loop's output, computed from attitude error inside a feedback loop —
so these traces cannot establish direction: a pilot rhythm and a level-loop response to a
disturbance look the same here. What the data does support: the bursts coincide with logged
setpoint activity, and no quiet-setpoint window in this log shows an oscillating gyro.

The oscillation test — a 1-s window with the logged setpoint quiet and the gyro not — is run at
two threshold settings (`wobble.py`), because the answer depends on them and that dependence is
part of the finding. At the strict setting (setpoint SD < 20, gyro SD > 40 deg/s) there are
**zero** such windows in the wobble log, zero in the RTH log, and four in the finished flight.
At the loose setting (setpoint SD < 40) windows appear in every log; the windows it admits
beyond the strict four all peak at 2–3 Hz — moderate-setpoint manoeuvre lag, not resolvable as
oscillation. Any genuine oscillation hiding inside high-setpoint windows (tight turns included)
is invisible to this instrument by construction, so the tight-turn report is untestable from
this set.

The four strict-setting windows (t ≈ 182.3 and 189.3 s, roll peaking at 7.0–11.0 Hz, gyro SD
~50 deg/s, union of their real timestamp spans 3.02 s of a 320.5 s flight) all sit **inside the
finished flight's GPS rescue or at its exit**: autopilot flight on a pack sagged below 10 V, a
motor sample at the rail, and the handback moment — after which the phase returned to IDLE and
the flight continued.

Worth knowing: the wobble log's header carries the **same ADRC numbers** as the two acro+Airmode flights.
The pre/post −5 % retune the tester described is not what these logs record; between the wobble
flight and the finished flight the headers change only RC deadbands (`deadband` 0 → 3,
`yaw_deadband` 0 → 10), `thr_hover` 30 → 27, `altitude_prefer_baro` — plus the ANGLE-vs-acro
difference above. If a log on the pre-reduction numbers exists, the tight-turn comparison could
be run against it.

## The yaw z3 telemetry rail (ADRC-029) is very visible on this craft

With `b0` yaw = 12307, the yaw z3 debug channel saturates its b9 int16 rail in **5.5 / 8.3 /
14.2 %** of frames across the three logs (`overview.py`). The controller's own clamp sits at
`pidsum_limit_yaw · b0` = 4 922 800 — everything between 524 272 and that is invisible in a b9
log. This is the exact case ADRC-029 (the `adrc_z3_log_scale` header line, shipping in b10) was
built for; on b10 these logs would decode with a per-craft scale and no rail.

## Addendum (2026-08-13): the pre-reduction log

The tester supplied the flight flown on the numbers he later reduced by 5 %
(`Finished_initial_btfl_001`, analysed by `initial.py`). The header diff against the finished
flight shows the tune step (`wc/wo` 115/115/135 over 150/150/161 → 109/109/128 over
143/143/153, `b0` up 5 %) **plus** the deadbands (0 → 3 / 0 → 10), `thr_hover`,
`altitude_prefer_baro`, `ap_hover_throttle` and a `d_max` value — so, as with the wobble log,
nothing here is a single-variable comparison, and the two flights are different days and
conditions besides.

What the log shows: a 338.2 s acro+airmode flight, no failsafe activity, tracking medians
1/1/1 deg/s (p90 5/4/6) — the same rounded headline numbers as the finished flight. The strict
quiet-setpoint test finds **zero** oscillation-like windows (the loose setting admits nine, all
peaking at 2–3 Hz — manoeuvre lag). The turn-window comparison (1-s windows with |roll or pitch
setpoint| > 300 deg/s; 5–30 Hz band RMS of the tracking error; the finished flight's rescue
span excluded):

| flight | n | median | p90 | max (deg/s) |
|---|---|---|---|---|
| initial | 25 | 19.3 | 29.8 | 32.7 |
| finished | 40 | 12.1 | 26.2 | 35.4 |

The observed median is lower in the finished flight; the distributions overlap; the single
worst window belongs to the finished flight; both flights' worst turn content peaks in the same
6–10 Hz band. The windows are 50 %-overlapped and there is one flight per tune, so no formal
statistical comparison is attempted, and nothing is attributable to the tune. On instability
specifically only a negative statement is available: **these two logs provide no separating
evidence that the −5 % step removed an instability — and none that one existed.** Oscillation
inside high-setpoint windows is invisible to the quiet-setpoint instrument by construction, and
the turn-window metric does not separate propwash, manoeuvre lag and loop instability.

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 overview.py
python3 wobble.py
python3 boxes.py     # numeric mode mask via --unit-flags raw
python3 initial.py   # the pre-reduction log (addendum)
python3 summaries.py --check
```

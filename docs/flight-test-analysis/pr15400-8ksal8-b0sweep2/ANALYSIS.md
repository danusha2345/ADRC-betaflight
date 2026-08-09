# @8ksal8's two b0-law sweeps on the AIR65 R, and what they do and do not show

**Craft:** AIR65 R, BETAFPVG473_V2 (STM32G47X), 1S whoop.
**Firmware:** `c40f1e096` = the b8 tag, in **both** sweeps — i.e. **without** the `z3` fix that
landed in `3c85c4b5a`.
**Config common to both:** `vbat_sag_compensation 0`, `dyn_idle_min_rpm 0`, `dshot_bidir 1`,
`motorOutput 158,2047`, `pid_process_denom 1`, `adrc_liftoff_throttle 40`,
`airmode_activate_throttle 25`, `P interval 4` (~805 saved frames/s, 74.5 % of iterations
decimated).

Two sweeps of four laws each, posted 2026-08-08:

| | `wc` R/P/Y | `wo` R/P/Y | `b0` R/P/Y | `adrc_hover_throttle` |
|---|---|---|---|---|
| old (`oldtune_*`) | 87 / 87 / 190 | 112 / 112 / 130 | 6500 / 4000 / 22000 | 30 |
| new (`newtune_*`) | 80 / 80 / 96 | 103 / 103 / 125 | 7007 / 4312 / 5848 | 27 |

Because `vbat_sag_compensation = 0` and dynamic idle is off, the static
`(mean(motor) − 158) / 1889` normalisation is exact on this craft — unlike the 6S bench craft in
[`pr15400-mamba-applied-path/`](../pr15400-mamba-applied-path/), where it is not.

## 1. The decoder hides the Airmode transition; the FC recorded it every time

The pilot reported that it "sometimes feels like it's still in Acro after switching to Airmode".
Read through the ordinary decoder, the mode column looks frozen — which is a decoder defect, not
an absent switch.

The firmware does not write runtime `flightModeFlags` into that field. It writes the low 32 bits
of `rcModeActivationMask` (`c40f1e096:src/main/blackbox/blackbox.c:983-1015`), in which `BOXARM`
is bit 0 and `BOXAIRMODE` is bit 24 (`rc_modes.h:29-62`). The decoder maps bit 0 to `ANGLE_MODE`,
knows only bits 0–9, and silently discards bit 24 (`blackbox_fielddefs.c:3-15`,
`parser.c:896-935`).

Decoded raw, the transition `1 → 16777217` (`0x01000001`) appears in **all eight logs**:

| sweep | FIXED | LINEAR | QUADRATIC | SQRT |
|---|---|---|---|---|
| old | 6.8056 s | 5.7104 s | 4.9683 s | 6.2895 s |
| new | 4.3230 s | 4.6452 s | 5.7741 s | 3.6781 s |

The header feature mask `268697608` does not contain global `FEATURE_AIRMODE` (bit 22), so this
box transition is what changes `isAirmodeEnabled()`. Note also that `airmode_activate_throttle`
does not enable airmode; it only latches `throttleRaised` afterwards (`core.c:829-849`).

So a missed switch is ruled out. What the logs do **not** explain is the subjective report after
a successfully registered transition; that needs a pilot-marked occurrence and the same
low-throttle manoeuvre either side of the switch.

## 2. The retune: descriptive statistics only

Whole-log tracking-error p90, °/s:

| law | yaw old→new | roll old→new | pitch old→new |
|---|---|---|---|
| FIXED | 16 → 13 | 22 → 19 | 25 → 17 |
| LINEAR | 23 → 19 | 21 → 26 | 15 → 21 |
| QUADRATIC | 32 → 17 | 25 → 29 | 18 → 22 |
| SQRT | 21 → 16 | 19 → 23 | 15 → 19 |

Yaw p90 is lower in all four new logs; roll/pitch p90 is higher in six of eight axis/law
comparisons. Frames with a motor at or above 2040 went 4.2–4.9 % → 4.8–6.6 % (on the exact
endpoint 2047 the ranges are 4.1–4.9 % → 4.8–6.5 %).

**The "flown harder" alternative was checked and does not hold**: setpoint p90 is *lower* in seven
of eight roll/pitch comparisons in the new logs, and the share of `|setpoint| ≥ 300 °/s` on pitch
is lower in all four.

**It still does not establish a tuning effect.** Eight unrandomised flights; yaw setpoint p90 also
fell in three of four new logs, which alone can move whole-flight yaw error; and stratifying by
setpoint bin gives no consistent picture — LINEAR yaw in the 50–100 °/s bin goes 10 → 15 °/s while
the whole-flight number goes 23 → 19. Decimation is not the limiting problem here: splitting saved
frames by `loopIteration` residue moves p90 by at most 3 °/s.

Attribution is blocked at the configuration level too. Four ADRC settings changed independently
between sweeps — including roll and pitch `b0` **up 7.8 %**, which is easy to miss next to the
3.76× yaw reduction, and the `adrc_hover_throttle` 30 → 27 that moves the b0 schedule reference
for every axis.

What would settle it: randomised old/new repeats of each law with the same scripted setpoint
sequence, compared in matched command bins.

## 3. The pre-gate `z3` blind interval, reproduced eight times

Both sweeps run b8, where `inhibitZ3Growth = !liftoff && throttleAtIdle`
(`c40f1e096:src/main/flight/adrc.c:599-609`). Once the final commanded collective clears the
`0.5 × adrc_liftoff_throttle` = 20 % idle floor, the inhibit lifts while the gate is still shut —
and the gate is simultaneously forcing `b0·u = 0` (`adrc.c:584-597`). Any angular acceleration
from the already-running motors must therefore be attributed to disturbance `z3`, with the known
actuator input excluded from the observer's model. `3c85c4b5a` changes the condition to
`!liftoff` and removes the interval.

The sequence is identical in all eight logs (commanded taken as `setpoint[3]`, not the stick):

| sweep | law | commanded clears 20 % | `z3` > 100 | gate opens | interval | max logged `z3` |
|---|---|---|---|---|---|---|
| old | FIXED | 2.718 s | 2.720 s | 2.785 s | 67 ms | 32767 (rail) |
| old | LINEAR | 2.703 | 2.703 | 2.780 | 77 ms | 32767 (rail) |
| old | QUADRATIC | 2.212 | 2.213 | 2.262 | 50 ms | 23495 |
| old | SQRT | 2.738 | 2.740 | 2.786 | 48 ms | 20353 |
| new | FIXED | 1.483 | 1.484 | 1.509 | 26 ms | 32767 (rail) |
| new | LINEAR | 1.523 | 1.524 | 1.556 | 33 ms | 32767 (rail) |
| new | QUADRATIC | 1.042 | 1.044 | 1.068 | 26 ms | 32767 (rail) |
| new | SQRT | 1.298 | 1.298 | 1.355 | 57 ms | 28292 |

`z3` starts growing within one saved frame of the interlock lifting, in every log. **Five of the
eight** reach the telemetry rail (`ADRC_DEBUG_LIMIT`, i.e. `|z3| ≥ 524 272` after the ×16 log
scale) before the gyro path opens the gate 25.9–76.5 ms later.

It reaches the control command: `|axisI| = |z3/b0|` is **55–123** at the opening frame and peaks
at **77–251** within the following 100 ms, decaying to 11–30 by the end of that window.

**What this is not.** These logs do not demonstrate a flight-quality penalty. No motor reaches the
upper endpoint in the 300 ms after opening; one motor sits at the lower endpoint for 8.6–28.4 % of
the first 100 ms; worst-axis tracking-error p90 in that window is 60–154 °/s but against mostly
small setpoints, and a takeoff transient is a strong confounder. The BBL carries no altitude,
range or contact field, so the moment of liftoff inside a 26–77 ms interval is not resolvable —
`commanded > 20 %` is not a measurement of being airborne.

So: a real execution of the defective estimator path on a third craft, with a measurable
contribution to the control command, and **no isolated harm**. The closing measurement would be
randomised matched launches on b8 versus a build containing `3c85c4b5a`, with a contact marker and
full-rate logging of the internal collective and unclipped `z3`.

## 4. Reproduction

```
gunzip -k *.bbl.gz
for f in *.bbl; do blackbox_decode "$f"; done
python3 k8.py    # per-axis tracking error, saturation, gate time, both sweeps
python3 k8b.py   # pre-gate phase: interlock crossing, z3 growth, gate
python3 sw.py    # yaw-only summary
python3 sw2.py   # spectra in calm windows (see the caveat below)
```

`sw2.py` selects "calm" windows by setpoint magnitude and, on these logs, still admits
manoeuvring — its 5–7 Hz peaks are flight dynamics, not a ring. It is kept because it is what was
run, not because the window selection is right.

`CLAIMS_FOR_REVIEW.md` is what went for adversarial review; `CODEX_REVIEW.md` is the verdict,
which refuted the original claim in §1 outright and narrowed §2 and §3 to the wording used here.

# @dedlike, 2026-08-09 — a command-triggered ground-contact roll oscillation

**Not** a second occurrence of [ADRC-028](../../ADRC_REMEDIATION_TRACKER.md), and
**not an established ADRC defect** on this data. The supportable description is:

> a command-triggered ground-contact roll oscillation under ACRO + AIRMODE,
> with mixer-induced collective lift.

**Reporter:** @dedlike, PR #15400, 2026-08-09. Props on, craft on the ground
resting on its battery pack, by his description.
**Craft (his description):** 5", X, 612 g with battery, 4S, 2400 kv, 2207 motors,
4.7" Cyclone T5047 props. Note the blackbox header carries `motor_kv = 1960`,
so the kv figure is his statement, not header-confirmed.
**Firmware:** `6317fe2aa`, unchanged from his previous report — the PR branch head,
gate-wise b6-level, **without** the `3c85c4b5a` z3 fix.
**Tune:** `adrcWC 60,60,60`, `adrcWO 100,100,80`, `adrcB0 2000,2000,**4000**`.
The only ADRC-tune change from 2026-08-06 is `adrc_b0_yaw = 4000`, which he applied on my
recommendation. Separately, legacy yaw D was changed from 0 to 1 in log 2/2 only, solely to
make `axisD[2]` appear in blackbox — see §9.
**Config:** `vbat_sag_compensation 0`, `dyn_idle_min_rpm 0`, `thrust_linear 0`,
`motorOutput 158,2047`, `pid_process_denom 2`, `P interval 4`,
`adrc_liftoff_throttle 40`. Full CLI state in `craft_config.txt`.

Two sessions in `groundloop_btfl_all.bbl.gz`:

| log | duration | gate | outcome |
|---|---|---|---|
| 1/2 | 15.168 s | never opens | uneventful |
| 2/2 | 6.246 s | opens 5.656 s | **the event** |

**All times below are measured from the first saved data frame**, not from
arming.

## 1. ACRO, not ANGLE — and how that nearly went wrong

Raw mode-mask decoding gives only `0` and `1` in both sessions: `BOXARM` bit 0,
with `BOXANGLE` bit 1 never set. **These are acro flights.**

This is worth recording because the first pass of this analysis said ANGLE, and
built an explanation on it — that the ±197/+275 °/s figures came from the
levelling controller. The source of the error was the decoder: it labels bit 0
`ANGLE_MODE`, which is the defect being filed upstream, and reading the
formatted column instead of the raw mask reproduces it faithfully. The setpoints
are rate-controller setpoints from RC input and rate mapping.

Airmode is confirmed independently and by a different route than on @8ksal8's
craft: here the header feature mask `272958600` contains
`FEATURE_AIRMODE = 1 << 22`, so airmode is on by feature, not by box — which is
why no `BOXAIRMODE` bit-24 transition appears.

## 2. The collective lift is the mixer working as designed

With airmode and the legacy mixer, `throttle = constrainf(throttle,
-normalizedMotorMixMin, …)` (`6317fe2aa:src/main/flight/mixer.c:681-701`) raises
the collective so the negative part of the axis mix does not fall through the
motor floor. Axis sums are limited and divided by 1000 (`mixer.c:731-750`); with
a roll/pitch `pidsum_limit` of 500 a single saturated axis occupies ±0.5 of the
mixer range. **So ~50 % applied collective at 0 % commanded collective is the
arithmetic of that algorithm**, not a throttle command from nowhere.

Verified rather than asserted: reconstructing the lower-clamp collective from
the logged `axisP+I+D+F`, the QUAD X coefficients (`mixer_init.c:84-89`) and the
axis limits reproduces the motor-derived collective across the whole
pre-throttle stretch (5589 saved rows) to **p99 = 0.1766 pp, max 0.2762 pp**.

The static-endpoint normalisation `(mean(motor) − 158)/1889` is valid here:
`vbat_sag_compensation = 0` leaves `motorRangeMax` at the static endpoint, and dynamic idle
and thrust linearisation are off. Motor fields are logged as integers, so it is not exact —
the reconstruction residual above is itself that quantisation.

## 3. Sequence

| event | t |
|---|---|
| collective first exceeds 2 % (an earlier pitch pulse) | 1.829850 s |
| main negative pitch pulse begins | 4.677603 s |
| pitch setpoint −197 °/s | 4.786593 s |
| **first upper motor rail** | **5.024572 s** |
| opposite pitch setpoint **+275 °/s** | 5.132562 s |
| zero-setpoint tail begins | 5.280548 s |
| first positive commanded collective (pilot's throttle) | 5.588517 s |
| commanded crosses the 20 % idle floor | 5.630513 s |
| logged `z3` reaches the telemetry rail | 5.647512 s |
| gate opens | 5.655511 s |

The pilot wrote that it began "a few ms" before he added power. The **ordering**
is confirmed; the interval is not a few ms — the pitch pulse leads his throttle
by **911 ms** and the first rail by **564 ms**.

**The trigger is a commanded reversal, not a single input**: −197 °/s followed
by +275 °/s.

**The first rail is a roll-axis event driven by the D-equivalent term.** In that
frame (motors `[179, 158, 2047, 2027]`) the raw roll sum `P+I+D+F` is **+544**,
of which `axisD[0]` is **+439**, while the pitch sum is **+6**.

The large full-session excursions — pitch gyro −1998 °/s, roll +1141 °/s,
`axisP[1]` +1662 — occur **after** the throttle input and the gate opening, and
do not evidence a pre-throttle cause.

## 4. What is not settled

**Whether the tail is self-sustaining.** After the R/P/Y setpoints return to
nearly zero, roll oscillation and near-rail occupancy continue for **0.306972 s** at Hann peaks of 19.48
and 20.83 Hz in two short windows. At 0.307 s the spectral resolution is only 3.3–3.5 Hz, so
read those as "about 20 Hz", not to two decimals. That the onset was command-triggered is
established; that the following regime could not sustain itself is not.

**Whether classic PID would do the same.** There is no matched A/B with the same
−197 → +275 reversal. The tester's earlier PID logs show classic PID with
airmode also lifting the collective at zero throttle, but their pitch pulses
reach only 118 °/s and contain no reversal, so no outcome ratio can be drawn
from them.

Closing measurement: a restrained or HIL A/B, classic PID versus ADRC, same
scripted reversal at zero throttle, automatic cutoff, and the highest log rate
the target sustains without dropped iterations, with identical fields and
settings in both arms.

## 5. `z3`, precisely

`z3` is exactly zero for the whole pre-throttle stretch. A logged zero alone
would only bound `|z3| < 8` (the field is `lrintf(z3/16)`), but the code closes
the gap: the arm reset sets `z3 = 0` (`adrc.c:174-188, 374-385`) and while the
gate is shut with commanded collective below the 20 % floor the inhibit rejects
any growth (`adrc.c:427-449, 523-537`).

Therefore `3c85c4b5a` would **not** have changed the onset or the first rail.

It **would** have changed the window **5.631–5.656 s**: once the pilot's
throttle crosses the idle floor while the gate is still shut, the b6/b8 inhibit
condition lifts and `z3` runs to the telemetry rail before the gate opens. So the blind spot is **not the cause of the onset or the first rail**. It is live later in
this same record, and its contribution after 5.631 s is not isolated by these data.

## 6. Why this is not ADRC-028

| | 2026-08-06 (ADRC-028) | 2026-08-09 |
|---|---|---|
| R/P/Y setpoints before onset | exactly 1 / 0 / 0 °/s | several pitch commands, incl. −197 → +275 |
| dominant axis | yaw | roll |
| frequency | 34.1 Hz (Hann) / 37.0 Hz (envelope fit) | 19.5–20.8 Hz in the zero-setpoint tail |
| first rail | 127.025 ms after the first saved frame | 5.024572 s after the first saved frame |

Shared: one craft, one firmware, ground contact, airmode, lower-clamp collective
lift, closed gate and `z3 = 0` in the pre-throttle portion. A common ADRC
ground-loop susceptibility remains a reasonable hypothesis. Different trigger,
axis, frequency family and timing mean this does **not** count as a second
observation of ADRC-028.

## 7. The recommendation that did not work, and why

`adrc_b0_yaw = 4000` was live (header `adrcB0:2000,2000,4000`) and did not
prevent the event, because the event is not on yaw. The axis was chosen from the
2026-08-06 log, where yaw was what grew. A targeting error on my part, not a
testing error on his.

Related correction: raising `b0` scales the instantaneous P/D/I terms by `1/b0`
for a fixed observer state, but `b0` also enters the observer's `b0·u` feedback
and the z3 bound, so "halves the authority" was too clean.

## 8. Log 1/2 as a control

Useful but **weak**: 15.168 s, `setpoint[3] = 0` throughout, gate never opens,
`z3 = 0`, applied collective max 14.981 %, motor max 706, yaw gyro
−112…+230 °/s. However its R/P/Y commands are not zero either (max
166 / 109 / 326 °/s) and it contains no −197 → +275 reversal, so it does not
isolate the trigger.

## 9. An instrumentation note worth copying

The tester set the legacy `yawPID` D-term to 1 in log 2/2, which makes
`axisD[2]` start logging on a build without the fork's blackbox patch — a
practical workaround for the gap described in
[`pr15400-mamba-applied-path/`](../pr15400-mamba-applied-path/). It works: the
field is present in log 2/2 only, spanning −82…+107 with a population SD of
7.058 against `axisP[2]`'s 4.746, a ratio of 1.487. That is a whole-session
composition statistic, not a causal attribution.

## 10. Reproduction

```
gunzip -k groundloop_btfl_all.bbl.gz
blackbox_decode groundloop_btfl_all.bbl                      # formatted
blackbox_decode --unit-flags raw groundloop_btfl_all.bbl     # for the mode mask
python3 d2.py     # per-session summary, gate, z3, axisD[2]
python3 d2b.py    # event timeline and 0.5 s windows
python3 d2c.py    # the pre-throttle phase in detail
```

Two notes on the scripts. `d2c.py` takes the pre-throttle phase as the continuous prefix
before the first positive commanded collective; an earlier version selected every frame with
zero commanded collective, which also swept in the return to zero *after* the gate opened,
and so reported a non-zero `z3` and an open gate inside what it called the pre-throttle
phase. And the motor-rail counters use `>= 2040`, a near-rail threshold: here 402 saved rows
meet it against 400 at exactly 2047, and the first timestamp coincides, but the criteria are
not the same.

Read the mode field from the **raw** decode. The formatted output labels
`BOXARM` as `ANGLE_MODE` and will tell you these are ANGLE flights; they are not.

`CLAIMS_FOR_REVIEW.md` is what was submitted for adversarial review;
`CODEX_REVIEW.md` is the verdict on the analysis and `CODEX_REVIEW_REPLY.md` the
verdict on the reply, the second of which is what caught the ANGLE error.

# 8ksal8 Pavo20 Pro II, 2026-07-24/25 — b0 sweep on b5 (SQRT selected)

Source: PR [betaflight#15400] comment of 2026-07-24 (`b0.zip` attachment; the
three `.bbl` originals are preserved here verbatim). Reproduce: decode all with
the pinned `blackbox_decode` (`--debug --unit-frame-time us`), then
`python3 b0_sweep.py`.

**Provenance** (headers, identical across the three sessions): firmware
`543f1a5ff` = exactly the b5 tag, STM32F405 (`BEFH BETAFPVF405_ELRS`),
`pid_type = 1` (ADRC), `debug_mode = 102` (ADRC), `adrc_b0_law = 1` (SQRT),
`adrc_wc = 40/40/40`, `adrc_wo = 120/120/100`, `adrc_hover_throttle = 50`,
`adrc_liftoff_throttle = 52`, `motor_poles = 12`, `motorOutput 198..2047`,
`thrust_linear = 0`, looptime 125 µs. The swept parameter is `adrc_b0`:

| log | `adrc_b0` roll/pitch/yaw | airborne | note |
|---|---|---|---|
| 1 | 5000 / 5000 / 5000 | 53.1 s | clean |
| 2 | 3000 / 3000 / 3000 | 55.9 s | clean |
| 3 | 2000 / **1500** / 2000 | 97.7 s | persistent ~48.8 Hz yaw oscillation |

These are the first logs from this pilot actually flown on ADRC — the earlier
set in the same thread was `pid_type = 0` (CLASSIC), so the `adrc_*` values
had no effect there.

## Result 1 — the b0 schedule never engaged, so this is a fixed-b0 sweep

`debug[7]` (= `±b0ThrottleScale × 100`) stayed at exactly ±100 in all three
flights, i.e. the applied multiplier was ×1.00 throughout. The reason is in
the configuration, not the code: `adrc_hover_throttle = 50` while the
**collective** — recovered from the mean of the four motor outputs through
`motorOutput 198..2047`, valid here because nothing saturated and
`thrust_linear = 0` — sits at 27.9–30.9 % in hover and peaks at 32.1 / 38.2 /
45.5 %. Since `b0` is only scaled *above* hover (`constrainf(rawScale, 1.0f,
maxB0Scale)` in `adrc.c`), the SQRT law was selected but never exercised.

Consequence for the ADRC-021 law A/B: **this dataset compares fixed b0 values,
not throttle-schedule shapes.** For the law to be testable on this craft,
`adrc_hover_throttle` needs to be ≈29 (its measured hover collective).

The same collective trace settles which liftoff path opened the gate: the peak
collective (45.5 %) never reached `adrc_liftoff_throttle = 52`, so the throttle
confirmation could not fire in any of the three flights and the gate opened
through the **gyro path** every time (5.86 / 5.04 / 7.42 s, at 15–21 % stick
throttle). That is unremarkable at takeoff, but it means the throttle path was
effectively disabled by the setting — worth pairing with ADRC-026, where the
gyro path is the one that can false-trigger on the ground.

## Result 2 — tracking error, one criterion for all axes

1 s windows, 50 % hop, per-axis calm gate (`std(setpoint) < 15` and
`max|setpoint| < 20` dps), median RMS of `gyroUnfilt − setpoint`:

| log | roll | pitch | yaw |
|---|---|---|---|
| 1 (b0 5000) | 10.3 (n=32) | 7.2 (n=41) | 6.3 (n=73) |
| 2 (b0 3000) | 8.6 (n=34) | 6.9 (n=43) | 6.4 (n=72) |
| 3 (b0 2000/1500) | 7.9 (n=98) | 6.5 (n=89) | **23.7 (n=130)** |

A per-sample calm mask instead of a windowed one inflates logs 1–2 to 19 and
13 dps by admitting fast zero-crossings of the yaw stick — the windowed
numbers above are the ones to quote.

## Result 3 — log3 carries a persistent closed-loop yaw oscillation

Median 40–60 Hz band RMS over 4 s segments of the airborne stretch:

| log | motors (each) | 4-motor **mean** | yaw-mix | yaw gyro | yaw `axisP`/`axisI`/`axisD` |
|---|---|---|---|---|---|
| 1 | 2.7–3.6 | 0.29 | 0.8 | 0.27 dps | 0.12 / 0.15 / 0.36 |
| 2 | 4.9–8.4 | 0.32 | 2.7 | 0.59 dps | 0.29 / 0.46 / 1.11 |
| 3 | **119–198** | 0.29 | **155** | **23.0 dps** | **15.1 / 27.8 / 66.5** |

Two things worth keeping for anyone re-checking this: the **4-motor mean
cancels a yaw oscillation** (0.29 in all three logs — it is the wrong signal to
test with; use per-motor or the yaw-differential mix `(m0+m3−m1−m2)/4`), and the
energy lands in the ADRC terms with the `axisD` path (`−kd·z2/b0`) dominant,
which is what an over-gained loop looks like.

The line is real only in log3. Per 4 s segment, peak in 35–65 Hz:

| log | peak (median) | p10–p90 | amplitude | peak / local floor |
|---|---|---|---|---|
| 1 | 51.0 Hz | 49.3–53.8 | 0.12 dps | 4.1× |
| 2 | 51.5 Hz | 49.6–52.0 | 0.30 dps | 6.4× |
| 3 | **48.75 Hz** | **48.75–48.93** | **29.1 dps** | **269×** |

In logs 1–2 the "peak" wanders across the band at 4–6× the floor, i.e. it is
the noise floor, not a line: reading a frequency *shift* into 51.0 → 51.5 →
48.75 would be over-interpretation. It is sustained rather than episodic —
93 of 97 one-second windows exceed 5 dps in-band, from 7.4 s to the end of the
flight.

Not an RPM artifact: with the header's `motor_poles = 12`, the eRPM field puts
1×RPM at 348 / 341 / 344 Hz — essentially identical across the three flights,
while the 48.8 Hz line appears in only one of them. What is *not* excluded is a
structural mode of the frame setting the frequency at which the loop closes;
the evidence says the oscillation is in the control loop, not that its
frequency is purely controller-determined.

**Bracket, not threshold.** Clean at b0 3000, ringing at b0 2000 — and log3
lowered all three axes at once (yaw 3000→2000, roll 3000→2000, pitch
3000→1500), so the bracket applies to the configuration, not to yaw `b0`
alone. No threshold can be identified from three points.

## Result 4 — latency: direction only on roll, causality not established

Cross-spectral group delay, setpoint → `gyroUnfilt`, 2–10 Hz, over 2 s windows
with real stick activity (`std(setpoint) ≥ 40` dps):

| log | roll τ | roll coherence | pitch τ | pitch coherence |
|---|---|---|---|---|
| 1 (b0 5000) | 26.3 ms | 0.94 | 13.1 ms | 0.69 |
| 2 (b0 3000) | 15.5 ms | 0.95 | 19.0 ms | 0.89 |
| 3 (b0 2000/1500) | 11.9 ms | 0.98 | 12.8 ms | 0.97 |

Coherence is high, so these are meaningful per-flight estimates — which is
exactly why pitch's non-monotonic ordering is a real *absence* of a
relationship rather than measurement noise. Two cruder estimators
(cross-correlation argmax, raw and bandpassed/content-matched) put roll at
53.5 → 49.7 → 45.1 and 52.7 → 43.1 → 36.8 ms: same direction on roll, wildly
different absolutes, so no absolute latency figure should be quoted from this
dataset. These are three separate sessions, not a controlled A/B, and log3 is
already marginally stable — its "faster" response is measured on a ringing
loop. Note also `|H| ≈ 0.4` across all three: the achieved rate amplitude in
2–10 Hz is well below the commanded one. `|H|` is *not* coherence; conflating
the two was a review finding on the first pass of this analysis.

## Result 5 — extra electrical power, dose-dependent on the ring

Calm-stick windows with **matched collective** (27–31 %):

| log | n | current | power | collective | yaw 40–60 Hz |
|---|---|---|---|---|---|
| 1 | 14 | 3.67 A | 42.4 W | 29.2 % | 0.1 dps |
| 2 | 12 | 3.34 A | 36.4 W | 28.6 % | 0.3 dps |
| 3 | 36 | **4.82 A** | **55.4 W** | 28.3 % | 23.3 dps |

Within log3 the power tracks the ring amplitude: r = +0.90 (current +0.87),
and +0.77 after removing the flight-time trend — necessary because the battery
sags monotonically over the 98 s flight (corr(vbat, time) = −1.00) and the ring
decays with it. Motor temperature is not logged, so the honest statement is
extra electrical power that scales with the oscillation, consistent with the
pilot's report of heat — not a measured temperature.

## What to ask for next

1. `adrc_hover_throttle ≈ 29`, `adrc_liftoff_throttle ≈ 33–35` — then both the
   b0 schedule and the throttle path of the liftoff gate become live, and the
   law A/B is testable on this craft.
2. One axis at a time when hunting the stability edge, so a bracket attaches to
   a single `adrc_b0`.
3. b0 direction, for the record: `u = (kp·(sp − z1) − kd·z2 − z3)/b0`, so too
   *low* is over-gain (overshoot → oscillation, as measured here) and too
   *high* is soft but stable. Round up when unsure.

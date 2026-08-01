# Pavel_M., Air65 II and Meteor75 Pro, 2026-07-30 (part 2) — a two-craft b0 sweep, and what "sounds cleanest" actually costs

Source: two archives posted to the `FPV ADRC Development` Discord,
`#test-flights-and-logs`, threads "Air 65 Racing 0702 30000KV part 2" and
"Meteor 75 Pro 1102 22000KV part 2", both 2026-07-30 (23:57 / 00:38 MSK).

| archive | SHA-256 |
|---|---|
| `AIR65_tune_60_100_varied_b0.BBL.zip` | `64ceb13bd3276d6649ad5ba8a303ce3434e8ba3c06e2b2ed8bb3549fc19e297e` |
| `METEOR75_tune_60_100_varied_b0.BBL.zip` | `b3dc50e82601d278eed3d5968ce39008551d2ac53aa8d1ad6fc7c3c225a2b3dc` |

Both are Betaflight b5 (`543f1a5ff`, STM32G47X), `pid_type = ADRC`,
`debug_mode = ADRC`, `adrc_b0_law = 1` (SQRT), ~2 kHz logging,
`motorOutput 48-1847`, `adrc_gyro_lpf_hz = 150`.

**Provenance is clean this time** — unlike part 1, every session's raw headers
match the stated plan:

| craft | sessions | wc R/P/Y | wo | b0 | anchor `adrc_hover_throttle` |
|---|---|---|---|---|---:|
| Air65 II (BMI270) | 6 | 60/60/60 | 100/100/100 | 3200 ×2, 4800 ×2, 6400 ×2 | 35 |
| Meteor75 Pro (ICM42622P) | 7 | 60/60/**100** | 100/100/100 | 3200 ×2, 4800 ×3, 6400 ×2 | 40 |

Note the yaw difference: the Meteor runs `adrc_wc_yaw = 100`, the Air65 60. Yaw
is therefore not comparable across crafts; roll/pitch are.

Reproduce:

```bash
unzip -n AIR65_tune_60_100_varied_b0.BBL.zip
unzip -n METEOR75_tune_60_100_varied_b0.BBL.zip
blackbox_decode --unit-acceleration g --unit-frame-time us --save-headers \
  --output-dir dec-air65 AIR65_tune_60_100_varied_b0.BBL
blackbox_decode --unit-acceleration g --unit-frame-time us --save-headers \
  --output-dir dec-meteor75 METEOR75_tune_60_100_varied_b0.BBL
python3 ../pr15400-8ksal8-yawb0/analyze_round.py dec-*/*.0[0-9].csv
python3 ../pr15400-8ksal8-yawb0/hover_probe.py dec-*/*.0[0-9].csv
python3 motor_fault.py            # section 4
```

`|I| = |z3/b0|` is quoted rather than the raw debug z3 field: z3 absorbs the
`b0·u` model error and so grows with the configured b0 on its own, which makes
the "z3 at debug rail" percentage rise with b0 for purely scaling reasons. `|I|`
divides that out and is bounded by `pidSumLimit` (500 / 400 yaw). In every
session below `|I|` stays off its limit (≤ 0.02 % of samples), so nothing here is
an authority-saturation story.

## 1. The same trade-off on both crafts: b0 up → quieter, but worse tracking

Roll axis, airborne active phase. HF 20–80 Hz is the band the pilot hears as
chatter; tracking error is 15 Hz-lowpassed on commanded segments, quoted as a
fraction of the command's own standard deviation so different flying still
compares.

**Air65 II** (anchor 35):

| session | b0 | vbat med | roll HF 20–80 | motor-mean HF 20–80 | roll errRMS | roll `|I|` p95 |
|---|---:|---:|---:|---:|---:|---:|
| .01 | 3200 | 3.85 V | **10.0 dps** | 5.1 | 7.2 dps (10 %) | 85 |
| .02 | 3200 | 3.69 V | 7.2 | 3.5 | 6.0 dps (8 %) | 90 |
| .03 | 4800 | 3.84 V | 1.6 | 1.4 | 7.1 dps (9 %) | 73 |
| .04 | 4800 | 3.68 V | 2.1 | 1.4 | 11.9 dps (14 %) | 98 |
| .05 | 6400 | 3.46 V | **1.3** | 0.9 | 13.5 dps (18 %) | 99 |
| .06 | 6400 | 3.47 V | 1.3 | 1.1 | 15.0 dps (18 %) | 115 |

**Meteor75 Pro** (anchor 40):

| session | b0 | vbat med | roll HF 20–80 | motor-mean HF 20–80 | roll errRMS | roll `|I|` p95 |
|---|---:|---:|---:|---:|---:|---:|
| .01 | 3200 | 3.81 V | 1.8 dps | 3.9 | 6.9 dps (10 %) | 113 |
| .02 | 3200 | 3.65 V | 5.4 | 4.9 | 15.7 dps (22 %) | 118 |
| .03 | 4800 | 3.84 V | 1.0 | 2.7 | 25.4 dps (38 %) | 133 |
| .05 | 4800 | 3.70 V | 0.8 | 2.1 | 15.3 dps (22 %) | 154 |
| .06 | 6400 | 3.85 V | **0.7** | 1.9 | 25.8 dps (38 %) | 138 |
| .07 | 6400 | 3.71 V | 1.0 | 2.1 | **31.7 dps (42 %)** | 164 |

Both crafts move the same way: **raising b0 monotonically reduces the audible
band and monotonically degrades tracking**, with the standing disturbance
estimate rising alongside. The closed-loop gain (σ_gyro/σ_cmd) drifts the same
way on the Meteor: 1.04 → 1.22 → 1.19, i.e. increasing overshoot.

So the two crafts do **not** rank b0 in opposite directions on the instruments —
they rank it in opposite directions *by ear*, and the ear is only listening to
one of the two curves. On the Air65 the 3200 chatter was severe (10 dps of
20–80 Hz roll content, motor-mean 5.1) so the noise term dominated the pilot's
judgement; on the Meteor 3200 was already quiet (1.8 dps) so the tracking loss at
6400 dominated instead. Both subjective verdicts are correct about what they
measured.

Two confounders, stated plainly:

- The Air65's 6400 pair was flown on sagging packs (3.46/3.47 V versus 3.85 V at
  3200), so part of its tracking loss could be voltage rather than b0. The
  Meteor's `.06` breaks that tie: 6400 at a **full** 3.85 V pack still tracks at
  38 % error, versus 10 % for 3200 at 3.81 V.
- Wind was near zero on both days per the pilot, and none of the sessions
  saturated the motors meaningfully (≤ 0.26 %), so neither result is a
  saturation artefact.

## 2. Cross-craft: b0 is an airframe property, and these two differ several-fold

At the *same* setting (`b0 = 3200`, `wc 60`, `wo 100`, fresh pack) the Air65
shows **10.0 dps** of 20–80 Hz roll content and the Meteor **1.8 dps** — a 5.6×
difference in the noise-amplification term with an identical controller. The
Air65 (0702, 30000 KV, ~65 mm) simply has a much higher real control-input gain
than the Meteor (1102, 22000 KV, ~75 mm), so the same b0 buys a much higher
effective loop gain there.

That is the practical content of ADRC-021: b0 is not a taste setting, it is a
per-craft physical quantity, and the useful range on a 65 mm whoop sits well
above the range on a 75 mm one even though both are "tinywhoops".

## 3. The anchor cannot stay matched across a 1S pack

`adrc_hover_throttle` anchors the b0 throttle schedule, so what matters is the
offset between it and the collective the craft actually hovers at. Measured from
calm windows (gate open, no rail, |setpoint| < 50 dps, |gyro| < 120 dps,
|acc| 0.85–1.15 g):

| Air65 session | vbat med | measured hover | anchor − measured |
|---|---:|---:|---:|
| .01 (3200) | 3.90 V | 38.2 % | −3.2 |
| .02 (3200) | 3.71 V | 36.1 % | −1.1 |
| .03 (4800) | 3.87 V | 38.8 % | −3.8 |
| .04 (4800) | 3.62 V | 47.2 % | −12.2 |
| .05 (6400) | 3.50 V | 45.7 % | −10.7 |
| .06 (6400) | 3.47 V | 50.0 % | **−15.0** |

On a 1S whoop the hover collective climbs from ~36 % on a fresh pack to ~50 % at
the end of it. A single fixed anchor is therefore matched for at most part of a
flight — and the schedule notices: the measured b0-scale multiplier runs 1.05 at
the start of the sweep and 1.22 by the sagging sessions, i.e. ADRC is already
adding ~20 % effective b0 late in the pack, on top of whatever was configured.
The Meteor is milder (measured hover 36–45 % against anchor 40, offsets −5.3 to
+4.0), which fits its lower thrust-to-weight.

This matters for two open items: it is a second, independent route into the same
schedule-vs-actual mismatch @jmsweng reported from the *high* side (ADRC-027
sticking), and it is a candidate contributor to the throttle-transition
excursions Pavel described in part 1 (ADRC-025).

## 4. The "quad freaked out on arm" session was a dead motor, not a tune or gate problem

`METEOR75 .04` is 1.79 s long, 32.7 % of samples with a motor at the rail. It is
**not** an ADRC-026 event: the gate was closed at the first sample and only
opened after the pilot had already raised throttle past 24 %, and the setpoint
stays near zero (peak 73 dps) while the gyro reaches 1228 dps.

eRPM tells the story directly:

| t | motor 0 / 1 / 2 / 3 command | eRPM 0 / 1 / 2 / 3 |
|---|---|---|
| 0.50 s | 710 / 700 / 602 / 722 | 1010 / 720 / 1031 / **40** |
| 0.75 s | 784 / 498 / 406 / **1847** | 1339 / 696 / 798 / **70** |
| 1.00 s | 587 / 637 / 804 / **1847** | 1103 / 737 / 1296 / **128** |
| 1.25 s | 1074 / 1769 / 1148 / 1189 | 1579 / 1546 / 1754 / 1531 |

Motor 3 was commanded to the rail for ~0.5 s and produced essentially no
rotation (40–128 eRPM against 700–1300 on the others) before freeing itself at
t ≈ 1.25 s. That is a mechanically stuck motor — consistent with the pilot's
"probably a foreign object in a motor" — and the controller's rail is the correct
response to an axis that will not answer. Nothing to fix in ADRC here; worth
checking that bell for debris/damage.

## 5. Why these logs cannot pin the numeric b0, and what would

An attempt at closed-loop system identification on these sessions is in
`b0_ident.py`. Two results worth recording so the next person does not repeat it:

- Fitting `gyro_dot` against `u = pidSum` inside the loop returns a number
  proportional to the configured b0 (49 / 70 / 99 for 3200 / 4800 / 6400 on the
  Air65) with coherence 0.9+. That is the **controller's own identity**, not the
  airframe: `u` is computed from the gyro, and the D path dominates the band.
  It must not be quoted as a measurement.
- The unbiased route — using the pilot's setpoint as an instrument,
  `H = P(r, gyro_dot) / P(r, u)` — fails on these logs for lack of excitation:
  command-to-`u` coherence peaks at 0.29–0.46 in 1.5–12 Hz, below any usable
  threshold. Free flying does not put enough independent energy into the command
  channel.

This is exactly the gap the ADRC-021 doublet protocol exists to close: repeated
identical roll/pitch doublets at fixed collective bins, tune unchanged. With that
excitation the same estimator becomes usable and returns a per-craft b0 in
physical units instead of a preference.

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| Higher b0 lowers audible-band content on both crafts | POSITIVE | §1, monotone across 13 sessions | high |
| Higher b0 worsens tracking on both crafts | POSITIVE | §1; Meteor .06 controls for pack voltage | high |
| The two crafts rank b0 oppositely on instruments | NEGATIVE | same direction on both; only the ear differs | high |
| Air65 has a much higher real control gain than the Meteor | POSITIVE | 5.6× HF at identical settings | medium-high |
| Air65 6400 tracking loss is purely a voltage artefact | NEGATIVE | Meteor .06 at 3.85 V shows the same loss | high |
| Hover anchor drifts out of match within one 1S pack | POSITIVE | §3, six sessions, −1.1 → −15.0 | high |
| METEOR .04 is an ADRC-026 ground runaway | NEGATIVE | gate opened after throttle-up; motor 3 at 40 eRPM | high |
| A numeric per-craft b0 can be extracted from these logs | NEGATIVE | command coherence 0.29–0.46, §5 | high |

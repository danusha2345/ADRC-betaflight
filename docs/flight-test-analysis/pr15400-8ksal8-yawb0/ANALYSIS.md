# 8ksal8, 2026-07-30/31 — yaw b0 7k→13k→18k, the hover-anchor test, and why pitch is the twitchy axis

Source: four Blackbox logs attached to PR
[betaflight#15400](https://github.com/betaflight/betaflight/pull/15400) on
2026-07-30 and 2026-07-31. Same craft throughout (F405, 3S, ICM-class IMU,
b5 tag `543f1a5ff`, SQRT b0 law, `debug_mode = ADRC`, ~1972 Hz logging,
`motor_poles = 12`, `motorOutput 198-2047`).

| log | wc R/P/Y | b0 R/P/Y | anchor `adrc_hover_throttle` | vbat med | active |
|---|---|---|---:|---:|---:|
| `Acro_Air_Full_Throttle_Wind_btfl_002` | 125/125/125 | 4000/3000/**7000** | 29 | 10.98 V | 171.0 s |
| `Yawb0_13k` | 125/125/125 | 4000/3000/**13000** | 29 | 11.25 V | 175.0 s |
| `btfl_041` | 125/130/**220** | 4000/3000/**18000** | 29 | 11.89 V | 55.5 s |
| `yaw220wc_18kb0_HoverThrottle35` | 125/130/220 | 4000/3000/18000 | **35** | 10.02 V | 30.1 s |

Reproduce: decode each `.bbl` with the pinned `blackbox_decode`
(`--unit-acceleration g --unit-frame-time us --save-headers`), then
`python3 analyze_round.py <decoded.csv>` and `python3 hover_probe.py <decoded.csv>`.

Metric notes, because two of them are easy to misread:

- **`|I|` is the only b0-comparable view of the observer's disturbance state.**
  The `debug` z3 field is logged as `z3/16` and clips at 32767, i.e. `|z3| ≥ 524k`.
  z3 absorbs the `b0·u` model error, so its magnitude scales with the configured
  b0 — a larger b0 reaches the debug rail on its own, with no change in what the
  controller is doing. `pidData.I = −z3/b0` divides that back out, and the
  anti-windup bound is `|I| ≤ pidSumLimit`. Below, `|I|` is quoted, and in every
  log it stays far from its limit (≤ 0.24 % of samples at the rail).
- **Collective comes from the motor mean, not the throttle stick**, so it tracks
  what the craft actually needed.

## 1. yaw b0 7k → 13k: a clean A/B, and it moved every metric the right way

These two logs differ only in `adrc_b0_yaw`; same wc, same filters, same anchor,
both flown in wind on the same day. The two flights are not identical in
aggression (the 7k flight has 4.30 % of samples with a motor at the rail versus
0.68 %, and a higher p90 collective), so the yaw-only comparison is the one to
trust — roll/pitch numbers move with the flying, not with the change.

| metric (airborne, active) | yaw b0 7000 | yaw b0 13000 |
|---|---:|---:|
| yaw `|I|` p95 | 58 | **36** |
| yaw gyro RMS | 32.7 dps | 32.1 dps |
| yaw HF 20–80 Hz | 1.5 dps | **0.9 dps** |
| yaw tracking error RMS (15 Hz LP, commanded segments) | 9.9 dps (13 % of cmd sd) | **8.5 dps (12 %)** |
| yaw z3 at debug rail | 4.02 % | 4.77 % |

Reading: at 7k the yaw observer was carrying a systematically larger standing
correction (`|I|` p95 58 → 36) and more 20–80 Hz activity. Raising b0 lowered the
loop gain toward what the airframe actually is, and the tracking error went down
rather than up — the usual sign that the old value was on the too-low side, not
that the new one is too high. This supports the pilot's subjective "raising yaw
b0 helped, and it still feels controllable".

`btfl_041` (yaw b0 18000) is **not** a continuation of this A/B: `adrc_wc_yaw`
changed 125 → 220 in the same step, and it is a much calmer flight (p90
collective 29.5 %). Its yaw `|I|` p95 is 106 — three times the 13k value — and
its yaw z3 sits at the debug rail 30.2 % of the time. That could be the b0 step,
the wc step, or the different flight; with two variables moved at once the log
cannot separate them. If the goal is to find the yaw b0 ceiling, the next run
should hold `adrc_wc_yaw = 125` and only change b0.

## 2. Why roll is solid and pitch is twitchy: it is pitch, and it is not filtering

The asymmetry the pilot sees in the debug traces is real and reproducible across
all four logs, but it is a **low-frequency** asymmetry, not chatter:

| log | roll `|I|` p95 | pitch `|I|` p95 | yaw `|I|` p95 | roll errRMS | pitch errRMS |
|---|---:|---:|---:|---:|---:|
| yaw 7k (wind) | 64 | **125** | 58 | 8.2 dps (7 %) | **27.7 dps (11 %)** |
| yaw 13k (wind) | 43 | **105** | 36 | 6.0 dps (5 %) | **12.6 dps (7 %)** |
| btfl_041 | 31 | 49 | 106 | 33.0 dps | 28.2 dps |
| hover-35 test | 67 | **148** | 59 | 17.9 dps | 23.5 dps |

Pitch carries two to three times roll's standing disturbance estimate in every
log, and its tracking error is 1.5–3× roll's in the two wind flights — while its
20–80 Hz content is *lower* than roll's (3.4 vs 4.5, 2.1 vs 3.2 dps). A filtering
or noise problem would show up in the HF band; this shows up in the standing
correction, which is what a persistent physical asymmetry looks like.

Two candidates, both consistent with the same signature and both testable:

1. **Rear CG.** The pilot has already stated the battery is deliberately set back
   to counter camera weight ("guess it's a little too much" — 2026-07-24 report).
   A static pitch imbalance is exactly a constant disturbance the observer must
   hold, i.e. a raised `|I|` on pitch only.
2. **`adrc_b0_pitch = 3000` against `adrc_b0_roll = 4000`** on a frame whose roll
   and pitch inertias are similar. A too-low b0 raises the effective loop gain on
   that axis, which is the axis-specific "reacts to wind with twitches" the pilot
   describes.

Cheapest discriminator: move the battery forward until the pitch `|I|` p95 drops
toward roll's without touching the tune. If it does, it was CG. If it does not,
set `adrc_b0_pitch = 4000` (matching roll) and re-fly the same conditions.

## 3. The `adrc_hover_throttle = 35` run did not test @jmsweng's hypothesis

@jmsweng reported that setting `adrc_hover_throttle` **above** the craft's real
hover collective produces the inverted "sticking". @8ksal8 set 35 (his usual
value is 29) and saw no sticking. Measured from the logs, that run did not create
the offset the hypothesis needs:

| log | anchor | measured hover collective (calm windows) | offset (anchor − measured) | vbat med |
|---|---:|---:|---:|---:|
| yaw 7k | 29 | 32.4 % (n=518) | **−3.4** | 10.94 V |
| yaw 13k | 29 | 30.9 % (n=972) | **−1.9** | 11.22 V |
| btfl_041 | 29 | 28.6 % (n=76) | **+0.4** | 11.78 V |
| hover-35 test | 35 | 34.6 % (n=24) | **+0.4** | 10.56 V |

The hover-35 flight was flown on a sagging pack (10.02 V median, 10.56 V in the
calm windows, versus 11.78 V in `btfl_041`), and a sagging pack needs more
collective for the same hover. The anchor of 35 therefore landed within half a
point of where the craft was actually hovering: the run tested an
*anchor-matched* configuration, not an anchor-above-hover one. It is a valid
control, and it is consistent with @jmsweng rather than contradicting him.

Caveat on that row: only 24 calm windows survived (the flight is aggressive,
9.19 % of samples with a motor at the rail) and their spread is wide
(p10 28.1 %, p90 40.0 %), so treat the 34.6 % as approximate.

To actually test the hypothesis on this craft: fly a **fresh** pack, where the
measured hover is 28–30 %, with `adrc_hover_throttle = 40–42`. That is the
+10-point offset regime; 35 on a fresh pack would only be about +6.

## 4. Ranges the schedule actually visited

For anyone reproducing: the b0 throttle multiplier (debug[7]) stayed modest in
all four logs — median 1.00–1.11, p90 1.01–1.48, max 1.62–1.82 — so none of these
flights probed the `adrc_b0_scale_max = 3` ceiling. The gate was open ≥ 95 % of
each log; no ADRC-026 signature (no zero-throttle motor runaway) appears in any
of them.

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| yaw b0 7k → 13k improved yaw `|I|`, HF and tracking | POSITIVE | table in §1, same-tune pair | high |
| yaw b0 18k is better still | UNPROVEN | wc_yaw and flight conditions changed with it | high |
| pitch carries a standing asymmetry vs roll | POSITIVE | `|I|` p95 and errRMS across four logs | high |
| that asymmetry is CG rather than tune | UNTESTED | two candidates, no discriminating run yet | — |
| the hover-35 run refutes @jmsweng | NEGATIVE | measured offset was +0.4, not above hover | high |
| any ADRC-026 event in these logs | NEGATIVE | gate open ≥95 %, no zero-throttle runaway | high |

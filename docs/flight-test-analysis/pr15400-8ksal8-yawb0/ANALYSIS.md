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
  anti-windup bound is `|I| ≤ pidSumLimit`. Below, `|I|` is quoted; in every
  log it stays far from that limit (≤ 0.24 % of samples). Two things this does
  **not** say: the debug-field rail (`|z3| ≥ 524k`) is not the internal
  anti-windup rail (`pidSumLimit·b0` = 1.5–7.2 M for these tunes), and motor
  saturation is a separate matter — the two wind flights do rail a motor for
  4.30 % / 0.68 % of samples, and the hover-35 flight for 9.19 %.
- **Collective comes from the motor mean, not the throttle stick**, so it tracks
  what the craft actually needed.

## 1. yaw b0 7k → 13k: an encouraging association — every yaw metric moved the right way, but the flights differ

These two logs differ only in `adrc_b0_yaw` in configuration; same wc, same
filters, same anchor, both flown in wind on the same day. But the flights
themselves are not matched: the 7k flight is much more aggressive (4.30 % of
samples with a motor at the output rail versus 0.68 %, p90 collective 64.7 %
versus 42.9 %), and aggression alone moves every metric below. So this is an
association from two uncontrolled flights, not a controlled A/B — the yaw-only
comparison is the most meaningful part, and even it inherits the aggression
difference.

| metric (airborne, active) | yaw b0 7000 | yaw b0 13000 |
|---|---:|---:|
| yaw `|I|` p95 | 58 | **36** |
| yaw gyro RMS | 32.7 dps | 32.1 dps |
| yaw HF 20–80 Hz | 1.5 dps | **0.9 dps** |
| yaw tracking error RMS (15 Hz LP, commanded segments) | 9.9 dps (13 % of cmd sd) | **8.5 dps (12 %)** |
| yaw z3 at debug rail | 4.02 % | 4.77 % |

Reading: at 7k the yaw axis carried a larger standing correction (`|I|` p95
58 → 36) and more 20–80 Hz activity, and the tracking error did not get worse
when b0 went up (13 % → 12 % — within noise for two different flights). That
direction is *consistent with* 7000 having been low, and it matches the pilot's
"raising yaw b0 helped, and it still feels controllable" — but with the
aggression mismatch above it is support, not proof. A same-pack, similar-flying
repeat would settle it.

`btfl_041` (yaw b0 18000) is **not** a continuation of this A/B: `adrc_wc_yaw`
changed 125 → 220 in the same step, and it is a much calmer flight (p90
collective 29.5 %). Its yaw `|I|` p95 is 106 — three times the 13k value — and
its yaw z3 sits at the debug rail 30.2 % of the time. That could be the b0 step,
the wc step, or the different flight; with two variables moved at once the log
cannot separate them. If the goal is to find the yaw b0 ceiling, the next run
should hold `adrc_wc_yaw = 125` and only change b0.

## 2. The roll-solid / pitch-twitchy asymmetry is real, low-frequency, and physical-looking

The asymmetry the pilot sees in the debug traces is real and reproducible across
all four logs, but it is a **low-frequency** asymmetry, not chatter:

| log | roll `|I|` p95 | pitch `|I|` p95 | yaw `|I|` p95 | roll errRMS | pitch errRMS |
|---|---:|---:|---:|---:|---:|
| yaw 7k (wind) | 64 | **125** | 58 | 8.2 dps (7 %) | **27.7 dps (11 %)** |
| yaw 13k (wind) | 43 | **105** | 36 | 6.0 dps (5 %) | **12.6 dps (7 %)** |
| btfl_041 | 31 | 49 | 106 | 33.0 dps | 28.2 dps |
| hover-35 test | 67 | **148** | 59 | 17.9 dps | 23.5 dps |

Pitch carries a consistently larger standing disturbance estimate than roll —
1.6–2.4× across the four logs (125/64, 105/43, 49/31, 148/67) — and its tracking
error is 1.5–3× roll's in the two wind flights, while its 20–80 Hz content is
*lower* than roll's (3.4 vs 4.5, 2.1 vs 3.2 dps). Chatter-type noise would show
in the HF band; this shows in the standing correction, which is what a
persistent asymmetry (mechanical or tune) looks like. Low HF does not by itself
rule out every sensor or filtering cause, so the candidates below stay
candidates until a discriminating test is flown.

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

## 3. The `adrc_hover_throttle = 35` run is a weak control, not a refutation of @jmsweng

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
collective for the same hover. Taken at face value, the anchor of 35 landed
within half a point of the actual hover — i.e. the run most likely tested an
*approximately anchor-matched* configuration rather than the anchor-above-hover
regime the hypothesis needs. But the estimate itself is weak: only 24
heavily-overlapping calm windows survive this aggressive flight (9.19 % of
samples with a motor at the rail; hover spread p10 28.1 %, p90 40.0 %), so
"matched to +0.4" cannot be asserted with confidence. The honest statement:
this run is not a convincing refutation — and not a strong confirmation of
anything either.

To actually discriminate on this craft, make the offset the only variable: two
flights on equally-charged **fresh** packs (measured hover 28–30 %), anchor
**29** in one and **34–35** in the other, everything else unchanged. That
reproduces the same few-points-above offset @jmsweng reported the effect at,
without pack sag re-matching the anchor mid-experiment.

## 4. Ranges the schedule actually visited

For anyone reproducing: the b0 throttle multiplier (debug[7]) stayed modest in
all four logs — median 1.00–1.11, p90 1.01–1.48, max 1.62–1.82 — so none of these
flights probed the `adrc_b0_scale_max = 3` ceiling. The gate was open ≥ 95 % of
each log; no ADRC-026 signature (no zero-throttle motor runaway) appears in any
of them.

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| yaw b0 7k → 13k: yaw `|I|`, HF and tracking all moved favourably | POSITIVE (association) | table in §1; flights differ in aggression, not a controlled A/B | medium |
| yaw b0 18k is better still | UNPROVEN | wc_yaw and flight conditions changed with it | high |
| pitch carries a standing asymmetry vs roll (1.6–2.4× `|I|`) | POSITIVE | `|I|` p95 and errRMS across four logs | high |
| that asymmetry is CG rather than tune (or sensor path) | UNTESTED | candidates only, no discriminating run yet | — |
| the hover-35 run refutes @jmsweng | NEGATIVE | offset most likely ≈0; 34.6 % from 24 wide-spread windows | medium-high |
| any ADRC-026 event in these logs | NEGATIVE | gate open ≥95 %, no zero-throttle runaway | high |

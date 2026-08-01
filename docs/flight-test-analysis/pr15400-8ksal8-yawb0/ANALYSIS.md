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

## Follow-up (2026-08-01): the ground b0_yaw sweeps — including a logged ADRC-026 false-open — and the first 48k log

Source: `Yaw300wc_b0_36k_Max_sweep.zip` and `Yaw300wc_48kb0.zip` (PR comment
5151289371), same craft (pilot confirms it hovers at ~28–29 %, consistent with
§3's measured 28.6–32.4 %). The pilot's stated procedure: ground, 0 % throttle,
ANGLE on, sweeping yaw b0 to "flatten the saw teeth" PID Toolbox shows in the
yaw response curve, believing wo was maxed out.

**Inventory — the first ZIP holds two `.bbl` files, 14 ground sessions in
total, plus `btfl_045` in the second ZIP.** An earlier revision of this
section analysed only the ascending file and wrongly concluded "no ADRC-026
event"; the descending file contains one.

- `Yaw300wc_b0_36k_20k_sweep.bbl`: five sessions, yaw b0 36k → 32k → 28k →
  24k → 20k;
- `Yaw300wc_b0_36k_Max_sweep.bbl`: nine sessions, yaw b0 36k → 65535;
- all fourteen: `wc 125/130/300`, `wo 160/160/160`, roll/pitch b0 4000/3000.

**What the headers actually changed:** `adrc_wo_yaw` never moved — 160 in
every session (CLI ceiling 600, headroom remains). What hit ceilings is
`adrc_wc_yaw` = 300 (the CLI max) and, in the last ascending session,
`adrc_b0_yaw` = 65535 (the uint16 field max).

**The 20k arm is a logged ADRC-026 false-open at zero throttle.** In
`…20k_sweep.05` (b0_yaw = 20000) the liftoff gate opened **0.775 s after the
log starts, at 0 % stick throttle**, and stayed open for 69.2 % of the record.
After the open: |gyro| reaches 128 dps, a motor is driven to **1122** of the
198–2047 range (≈ 50 % of span), and yaw z3 sits at the debug clip 26.2 % of
the remaining record; the recording ends 1.74 s after the open (disarm). Not a
full runaway to the rail — but a false liftoff detection plus ground-contact
excitation and windup, squarely in the ADRC-026 family, at **wo 160**: the
26 entry recorded so far with the lowest wo. The neighbouring sessions bracket
the trigger: the 32k and 24k arms briefly touch 21 dps (above the 20 dps
threshold, evidently under the 25 ms hold), the ascending nine stay at
≤ 17 dps with the gate closed 100 % of the time. The mechanism is coherent:
the control output scales as 1/b0, so *lowering* b0_yaw raises the grounded
loop gain until the idle excitation crosses the gyro trigger — direct support
for the joint-loop-gain threshold reading in the tracker (wo, wc, b0 jointly,
not a wo-only property).

**Why the closed-gate sessions cannot tune the airborne yaw loop.** With the
gate closed the ESO deliberately runs without the `b0·u` term, and the control
law divides everything by b0 (`P = wc²·err/b0`, `D = 2wc·z2/b0`,
`I = −z3/b0`). On the ground, raising b0_yaw therefore mostly *attenuates* the
yaw output per unit error — a progressively flatter, cleaner-looking idle
response is the expected result of turning the loop gain down, regardless of
the airframe. The "saw teeth going away" measures that attenuation, not the
flight loop; a PID-Toolbox step response taken on the ground with the gate
closed is a different plant from the one that flies. (The one open-gate
session is not usable as tuning data either — it is a safety event.)

**First log at the swept-in tune (`btfl_045`, wc_yaw 300 / b0_yaw 48k,
118 s at hover collective, fresh pack, anchor offset +0.8):** descriptively
the yaw axis is the loosest of the three calm-flight configurations so far —
tracking errRMS 39.3 dps = 27 % of the command sd with σ_gyro/σ_cmd = 1.18
(a std-dev ratio on 15 Hz-lowpassed commanded segments, not a proper
closed-loop gain measurement), lag 9 ms — against 18 % / 1.12 for `btfl_041`
(wc 220 / 18k) and 12 % / 1.04 for the 13k wind flight. Yaw HF is very low
(0.3 dps): quiet but loose. These are different flights, so this is
consistent-with, not proof of, an authority loss. One reading that fits: the
**P-output coefficient** per unit error is `wc²/b0` — 1.20 for 125/13k, 2.69
for 220/18k, **1.88 for 300/48k** — so the final config's direct P path is
weaker than 220/18k's despite both knobs being higher (the closed loop also
involves the ESO, so this is indicative, not the whole stiffness). The yaw
"z3 dbg-rail 43.6 %" here is the §-intro logging-scale effect: at b0 48k the
debug clip corresponds to |I| ≥ 10.9 while actual |I| p95 is 81 (bound 400) —
the channel is clipped telemetry above that level, not evidence of
anti-windup saturation.

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| yaw b0 7k → 13k: yaw `|I|`, HF and tracking all moved favourably | POSITIVE (association) | table in §1; flights differ in aggression, not a controlled A/B | medium |
| yaw b0 18k is better still | UNPROVEN | wc_yaw and flight conditions changed with it | high |
| pitch carries a standing asymmetry vs roll (1.6–2.4× `|I|`) | POSITIVE | `|I|` p95 and errRMS across four logs | high |
| that asymmetry is CG rather than tune (or sensor path) | UNTESTED | candidates only, no discriminating run yet | — |
| the hover-35 run refutes @jmsweng | NEGATIVE | offset most likely ≈0; 34.6 % from 24 wide-spread windows | medium-high |
| any ADRC-026 event in the four flight logs | NEGATIVE | gate open ≥95 %, no zero-throttle runaway | high |
| ADRC-026 false-open in the ground b0_yaw sweeps | **POSITIVE** | `…20k_sweep.05`: gate opens at 0.775 s at 0 % throttle, motor to 1122, z3 clipped 26.2 % after open | high |
| the trigger is bracketed by b0_yaw in that sweep | POSITIVE | 20k opens; 24k/32k touch 21 dps without opening; ascending nine ≤ 17 dps closed | high |
| the closed-gate sessions measured the airborne yaw loop | NEGATIVE | gate closed → no b0·u in the ESO; output ∝ 1/b0 | high |
| wc_yaw 300 / b0_yaw 48k improved flight yaw | NEGATIVE (descriptive, so far) | btfl_045: 27 % err / σ-ratio 1.18 vs 18 % / 1.12 (btfl_041), 12 % / 1.04 (13k); different flights | medium |

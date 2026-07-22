# bvandevliet SPEEDYBEE, 2026-07-22 — the wc/wo 2×2 on SQRT (b5)

Source: PR [betaflight#15400] comment of 2026-07-22 (STACK share — expires,
so the 8 `.bbl` originals are preserved here verbatim). Reproduce: decode all
with the pinned `blackbox_decode` (`--debug --unit-frame-time us`), then
`python3 wcwo_2x2.py`.

**Provenance** (headers): all 8 sessions are `543f1a5ff` = exactly the b5
tag, STM32F7X2 (SPEEDYBEE), `adrc_b0_law = 1` (SQRT), b0 = 2000,
`debug_mode = ADRC`. Arm mapping by `adrcWC/adrcWO`: log1 = 60/100 (p1
baseline), log2 & log8 = 45/100 (p2), log3 = 60/150 (p3), logs 4–7 = 45/150
(p4 attempts).

## Result 1 — both wo = 150 arms failed on the ground, before flight

| log | wc/wo | dur | stick thr | motor sat | gate |
|---|---|---|---|---|---|
| 3 | 60/150 | 1.9 s | 0 % (max 3.3) | **23.7 %** | opened @ 0.17 s at **0 % throttle** |
| 4 | 45/150 | 0.6 s | 0 % | 12.7 % | opened @ 0.11 s at **0 % throttle** |
| 5 | 45/150 | 0.5 s | 0 % | 0 % | never opened (quick disarm) |
| 6 | 45/150 | 0.9 s | 0 % | 0 % | never opened (quick disarm) |
| 7 | 45/150 | 4.8 s | 0 % (max 100) | 6.2 % | opened @ 0.40 s at **0 % throttle** |

The failure signature is consistent across all three gate-opening attempts:
a **~28.3–28.8 Hz oscillation at idle on the ground** (gyro p2p 190–390
deg/s), which exceeds the `adrc_liftoff_gyro_dps = 20` / 25 ms liftoff
detector within 0.1–0.4 s of arming → **the gate opens with the craft on
the ground at zero stick throttle** → the ESO integrates ground-contact
dynamics it cannot model, z3 winds up, motors run up to saturation —
the "almost instant fly-away" the pilot reported. This is a **gate
robustness defect interacting with high wo** (tracked as ADRC-026), not an
in-air instability: the gyro-only liftoff path treats a self-induced idle
oscillation as liftoff. Logs 5/6 are disarms before the detector fired.
Consequence: the observer-lag lever was **never tested in the air** — the
2×2's high-wo column is empty of flight data, and wo = 150 must not be
re-flown on this craft without a firmware-side mitigation.

## Result 2 — the wc lever alone does not remove the ring

Flyable arms, hardened ring criterion (overlapping 1 s windows, 0.25 s hop,
setpoint std AND max < 30 dps, max-axis 18–32 Hz band RMS > 10 dps):

| log | wc/wo | ring windows | episodes | worst |
|---|---|---|---|---|
| 1 | 60/100 | 10/39 (26 %) | 3 | 33.9 dps @ 27 Hz |
| 2 | 45/100 | 14/81 (17 %) | 4 | 27.8 dps @ 27 Hz |
| 8 | 45/100 | 13/64 (20 %) | 3 | 30.8 dps @ 27 Hz |

Cutting wc 60 → 45 leaves incidence, episode count, tone frequency and peak
amplitude essentially unchanged. Under the pre-registered 2×2 predictions
this is the "wc lever does not quiet it" half of the **"neither lever"**
branch — with the caveat that the wo half was never airborne. Read jointly
with the b5 law A/B (quadratic's extra gain cut *does* suppress incidence),
the picture is: the mode's ignition is gain-sensitive, but the wc path alone
at wo = 100 does not reach it. This elevates the structural observer-path
candidates (the fork's z2-LPF `adrc-dterm-lpf` branch; observer redesign)
and de-prioritizes plain wc reduction as the ADRC-024 fix.

Also on record: the pilot flew these in ANGLE mode per the share's diff;
jmsweng raised an IMU-difference hypothesis (his ICM42688 crafts hover all
laws; this craft's target carries BMI270/MPU6000) — plausible as a
craft-difference factor, unproven from logs, and orthogonal to the
ground-gate defect above, which is fully explained by the liftoff detector's
gyro-only path.

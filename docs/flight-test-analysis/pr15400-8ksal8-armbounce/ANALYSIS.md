# 8ksal8, 2026-07-29 — indoor arm tests: ANGLE+airmode "basketball bounce" and a logged slow ground windup (ADRC-026 family)

Source: PR [betaflight#15400] comment of 2026-07-29
(`Airmode_Arm_Angle_Air_btfl_all.zip`, the `.bbl` original preserved here —
one file, three sessions, hotel room, no wind). Pilot's account: "With
Airmode and angle activated when arming, quad jumps off ground and bounces
like a basketball on the floor. With just Airmode on arm it starts
smoothly." Blackbox is on a switch, so every session starts mid-armed and
the gate-opening instants are (again) unrecorded. Reproduce: decode with
the pinned `blackbox_decode` (`--debug --unit-frame-time us`), then
`python3 bounce.py` (per-session timelines) and `deep3.py` (session-3
windup and takeoff).

**Provenance** (headers): `543f1a5ff` = b5 tag, 1972 Hz log,
`motor_poles = 12`, wc 125/125/125, wo 160/160/160,
**b0 4000/3500/10000** (yaw raised from 7000), `adrc_b0_law = 1` (SQRT),
hover 29, liftoff 34/20 dps/25 ms.

## Sessions 1–2 — the bounce, captured mid-event (ANGLE box + airmode at arm)

Both logs open with the gate ALREADY open (`debug[7]` = +128/+129,
i.e. scale ≈ 1.28 → LPF'd collective ≈ 47 %) at **0 % stick throttle**:
collective slams between ~3 % and ~48 %, all-motor saturation bursts to
2047, roll/pitch gyro peaks 431–1945 dps, and z3 swings to ±300k (debug
×16 units). Distinctive: **the setpoint is not zero** — roll/pitch
setpoints reach 118–446 dps at zero throttle, i.e. the ANGLE leveling loop
demands rates as the craft tilts on/off the floor. The loop reads: tilt →
ANGLE commands rate → motors respond at idle (`pid_at_min_throttle = ON`)
→ craft jumps/skids → new tilt — with the grounded ESO amplifying the
fight (z3 rail-to-rail against ground contact it cannot model). Note stock
Betaflight has a known (much milder) angle+airmode arm-jump too; how much
of the amplitude here is ADRC-specific needs a same-craft classic-PID A/B,
which these logs don't contain.

## Session 3 — airmode-only arm: a logged slow windup that self-limits

The "smooth" arm is not idle inside: gate open from the first sample
(first-100 ms gyro max is 34 dps on yaw — an arming jolt/skid on the
smooth floor is the plausible unrecorded trigger), setpoint zero, craft
quiet (roll/pitch gyro 5–13 dps) — and yet:

- z3-pitch climbs monotonically +14k → +146k (t = 0→2 s), z3-yaw ramps to
  **+437k by t = 4 s**, motors creep from ~480 to **858 (≈42 % of range) at
  0 % stick throttle**;
- then the airborne z3 leak (`adrc_sigma_decay = 3` → 0.3/s) bleeds it
  back over ~8 s (z3-yaw +437k → +38k by t = 12), motors settle to ~450;
- takeoff at t = 16.6 s is clean (gyro ≤ 27 dps through throttle-up) —
  by then the windup had drained.

This is the first *logged* confirmation of both halves of the ADRC-026
mechanism story: (a) an open gate on the ground does wind the observer
against ground contact even on a quiet craft; (b) the windup is
**self-limiting** here — the sigma-decay leak plus the z3 authority bound
outpace the accumulation at idle on a level floor. The full runaway
(wcwo2x2, wo 150 / b0 2000) needed the fight to outpace the leak;
with this craft's b0 4000/3500/10000 the loop gain (∝ 1/b0) is low enough
that it doesn't. Consistent with the joint-loop-gain threshold reading in
the tracker.

## Practical notes

- Arming with the ANGLE box active (plus airmode) on the ground is the
  strongest bounce recipe: the leveling loop provides a standing
  excitation source the rate loop alone doesn't have. Until ADRC-026 has
  a mitigation, arm in acro (angle box off at arm) on ADRC profiles.
- The pilot also confirmed the rear-CG reading from the previous dataset
  (battery deliberately set back to counter camera weight — "guess it's a
  little too much") and raised yaw b0 to 10000 in this tune.

Tracked under **ADRC-026** in the
[remediation tracker](../ADRC_REMEDIATION_TRACKER.md).

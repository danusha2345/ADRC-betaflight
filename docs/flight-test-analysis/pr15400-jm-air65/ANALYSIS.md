# jmsweng Air65 II, 2026-07-25 — inverted "sticking" in a flip (ADRC-027)

Source: PR [betaflight#15400] comment of 2026-07-25 (`Test flight with final
tune and some other garbage.zip`, preserved verbatim as
`air65_final_tune.bbl` — one file, 12 sessions). The pilot's sync
(2026-07-26 comment): the sticking is visible ~12 s into the video
(https://youtu.be/8ZT5vhYjKys) ≈ 6 s into blackbox flight 1. Reproduce:
decode with the pinned `blackbox_decode` (`--debug --unit-frame-time us`),
then `python3 sticking_flip.py`.

**Provenance** (headers, identical in all 12 sessions): `543f1a5ff` = b5 tag,
BETAFPVG473_V2 (BMI270), `pid_type = ADRC`, `debug_mode = ADRC`,
wc 55 / wo 75 / b0 5000, `adrc_b0_law = 2` (LINEAR), hover 35, liftoff 40.
Note the archive documents only this final tune — the wo sweep the pilot
describes in the thread is not in the data.

## The measured sequence (flight 1, t = 5.4–6.2 s)

1. **Flip entry, full collective** (5.4–5.7 s): pitch setpoint ramps to
   −585 dps at 100 % throttle; the LINEAR schedule holds the b0 multiplier
   at ×2.3–2.6 (LPF'd collective), so output-per-unit-error is cut ~2.4×
   vs the hover calibration.
2. **Entry overshoot**: gyro peaks at **−1428 dps against a −582 setpoint**
   at t = 5.71 — 2.5× over-rotation. z3-pitch dives to the −524k debug rail
   absorbing/braking it.
3. **The stall** (5.75–6.10 s, **356 ms** — the "sticking", inverted per
   the video): setpoint median −433 dps, gyro median **−99** dps, deficit
   −192 dps. Through it, z3-pitch swings **rail-to-rail** (−524k → +524k,
   a ≥1 M range inside 0.2 s; at the log rail 65 % of stall samples — the
   ±524k figure is the debug channel clip, not the controller clamp, which
   sits at `pidsum_limit · b0_eff` ≈ 5.9e6 here). Motor 1 (FR) rides 2047
   for **78 %** of the stall; no motor is at the idle floor.
4. **Exit**: throttle chop to 23 % (scale 2.44 → 1.1 within ~0.3 s), craft
   recovers, z3 decays.

Integrated pitch rotation across the event ≈ −218°: entry, inversion, hang.

## Reading

The event is a cluster of three co-occurring mechanisms, not "gravity as a
disturbance" (gravity acts through the CG and produces no torque about it,
so a rate loop — and therefore z3 — cannot see it directly on any axis;
this also explains "never on yaw" trivially, since yaw was not commanded:
max |sp_yaw| = 9 dps through the event):

- **z3 transient**: the rail-to-rail swing is the same observer-transient
  family as the punch→chop rebound (ADRC-025) and the 5″ law-session
  "sticking" of 2026-07-23 (z3-pitch pinned ~96 ms at t≈34.9 s of the
  linear log — same signature, different craft).
- **Authority saturation**: one motor pinned at 2047 for most of the stall
  at 100 % collective — differential pitch headroom is thin exactly there.
- **Scheduled under-gain**: ×2.35 b0 multiplier cuts the corrective output
  right when the deficit builds.

Which of the three dominates is not separable from this flight alone.
Discriminating test (cheap): repeat the same flip at ~60 % throttle
(scale ≈ 1.7, no saturation) and, separately, on FIXED vs LINEAR at the
same throttle — if the sticking disappears at lower collective/scale it is
saturation/schedule; if it persists, the observer transient leads.

Tracked as **ADRC-027** in the
[remediation tracker](../ADRC_REMEDIATION_TRACKER.md).

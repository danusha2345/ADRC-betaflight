# 8ksal8, 2026-07-28 — retune wc 125 / wo 160 (b5, SQRT), heavy wind

Source: PR [betaflight#15400] comment of 2026-07-28
(`Acro_Air_Full_Throttle_Wind_btfl_002.zip`, the `.bbl` original preserved
here verbatim). Follow-up to the
[hotel-tune flights](../pr15400-8ksal8-hoteltune/) after the pilot raised
wc "for the rubber-band feel". Reproduce: decode with the pinned
`blackbox_decode` (`--debug --unit-frame-time us`), then `python3 quick.py`,
`verify.py`, `feel.py` (same scripts as the hotel-tune dir, single-file
glob).

**Provenance** (headers): `543f1a5ff` = b5 tag, STM32F405, 1972 Hz log,
`motor_poles = 12`, wc 125/125/125, wo 160/160/160, b0 4000/3000/7000,
`adrc_b0_law = 1` (SQRT), hover 29, liftoff 34,
`airmode_activate_throttle = 25`. Conditions per the pilot: 15 mph wind
gusting 23; last segment is deliberate steady-stick wind rejection.

## Result

171 s airborne, collective med/p90/max 36/65/100 %. SQRT multiplier again
tracks the instantaneous bound √(collective/29): observed max 1.820 vs
1.838. Gate never closes while airborne; setpoint→gyro latency 3.5 ms on
both roll and pitch; no sticking-like stall even under the loose scan
(≥150 ms, |sp| > 100 dps).

Ring, narrowness-checked: 4 genuine narrow lines out of 264 calm windows —
10.5 dps @ 18 Hz (20× floor), 10.9 @ 19 (23×), 11.2 @ 18 pitch (120×),
11.3 @ 23 (114×) — plus one wind-skirt false flag discarded (9.5× floor).
Compared to the hotel tune (3/571 at 20–25 Hz), incidence is slightly
higher and the lines sit lower (18–19 Hz), but amplitudes stay ≈11 dps
and nothing self-sustains; the wind here was also much stronger. The
higher-wc tune did not open a margin problem.

Pilot's feel: better than the hotel tune; the remaining "rubber band" in
acro is **at zero throttle**, which is not a controller defect — at the
idle floor there is simply no differential authority left for any control
law (and airmode was off in the acro segments). His own practice
("leave a little throttle in") is the standard acro answer.

## Field report, unlogged — wind-induced false liftoff on the bench (ADRC-026 family)

Per the pilot: armed on a table with the Air-mode switch already on, in
turbulent wind, and "the quad jumped off the table when trying to
stabilize itself" (not logged — flash was full). Mechanically this is the
ADRC-026 gate false-trigger with **wind rocking as the gyro source**
instead of a high-wo self-oscillation: sustained ground rotation above
`adrc_liftoff_gyro_dps = 20` for 25 ms is indistinguishable from a toss
launch by design, the gate opens on the ground, and the grounded ESO winds
up against the constraint. Note Betaflight's airmode activation latch
(`airmode_activate_throttle = 25`) does not prevent this: with
`pid_at_min_throttle = ON` (default) the mixer applies corrections at idle
regardless. Recorded in the tracker as a broadening of ADRC-026's trigger
set; no log exists, so it stays a pilot report.

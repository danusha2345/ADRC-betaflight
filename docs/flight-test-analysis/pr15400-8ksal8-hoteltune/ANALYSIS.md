# 8ksal8, 2026-07-28 — first flights on the hand tune: SQRT b0 schedule live (b5)

Source: PR [betaflight#15400] comments of 2026-07-27/28 (`1st_Flights.zip`,
`1st_Flights_2.zip`, four `.bbl` originals preserved here verbatim; flight
video https://youtu.be/Y7GAv9V7wMI). Reproduce: decode with the pinned
`blackbox_decode` (`--debug --unit-frame-time us`), then `python3 quick.py`
(overview/ring/stall scan), `feel.py` (gate/latency), `verify.py`
(ring-peak narrowness, SQRT cap check, loose stall scan).

**Provenance** (headers, identical in all four): `543f1a5ff` = exactly the
b5 tag, STM32F405, `pid_type = ADRC`, `debug_mode = ADRC`, blackbox
1972 Hz (full-rate — no aliasing caveat this time), `motor_poles = 12`,
`thrust_linear = 0`. Tune: wc 69/76/133, wo 138/165/160,
b0 3750/3500/9000 (R/P/Y), **`adrc_b0_law = 1` (SQRT)**,
`adrc_hover_throttle = 29`, liftoff 34, `adrc_b0_scale_max = 3`.
Conditions per the pilot: very high winds. Pilot's feel: acro "bouncy
rubber band", Air mode much better, yaw solid, no uncommanded surprises,
no propwash noticed.

## Headline — the SQRT schedule ran live and tracked theory to <2 %

Previous 8ksal8 logs had `adrc_hover_throttle = 50` against an actual
28–31 % hover, pinning the multiplier at ×1.00. Here hover = 29 matches
the craft, and `debug[7]` shows the schedule working exactly as coded:

| flight | airborne | coll med/p90/max | b0 scale med/p90/max | ring windows | stalls |
|---|---|---|---|---|---|
| 1 Acro | 160 s | 31/41/100 % | 1.04/1.18/**1.83** | 3*/223 | none |
| 2 Acro+Air | 169 s | 33/49/100 % | 1.07/1.30/1.81 | 0/100 | none |
| 3 Wind | 167 s | 32/50/99 % | 1.05/1.30/1.80 | 0/190 | none |
| 4 FullThrottle | 126 s | 39/76/100 % | 1.16/1.58/1.83 | 0/58 | none |

Observed max multiplier vs the instantaneous bound √(collective/29): 1.830
vs 1.835, 1.810 vs 1.814, 1.800 vs 1.820, 1.830 vs 1.840 — the 2 Hz LPF
keeps the observed value just under the bound in every flight. This is the
first field confirmation of the SQRT law end-to-end.

\* Ring windows narrowness-checked (`verify.py`; the band-RMS-in-wind
pitfall is real here): of 4 flagged windows in flight 1, one (15.8 dps
@ 27 Hz) is a wide-band wind skirt (peak/floor 7.6×), three are genuine
narrow lines — 11.3 dps @ 20.0 Hz (288× floor), 12.6 dps @ 25.0 Hz (29×),
12.2 dps @ 24.0 Hz (11×). Brief, mild, and in the same 20–26 Hz family as
ADRC-024; nothing sustained, and flights 2–4 are clean including the
full-throttle one (collective p90 76 %).

## No inverted sticking in these logs (ADRC-027 status: not reproduced)

jmsweng read a hang at ~1:46 of the video as the inverted-sticking issue;
the pilot answered the stops were intentional (practicing inverted
holds). The logs agree with the pilot: no window ≥250 ms with
|setpoint| > 150 dps and gyro < 40 % of it, and even a loose scan
(≥150 ms, |sp| > 100) finds nothing in any of the four flights.

## The "rubber band" feel is not the gate

Gate closed <0.5 % of airborne time (0 % in flights 3–4);
setpoint→gyro cross-correlation latency 0.5–11 ms. The remaining suspect
is plain low bandwidth: roll/pitch wc 69/76 rad/s ≈ 11–12 Hz against yaw
wc 133 ("yaw felt solid" matches). The pilot's follow-up retune raises
wc to 125 on all axes — the right direction on this reading; logs on the
new tune pending.

## Side finding — Blackbox Explorer mislabels mode flags on 2026.6.0 logs

The pilot's note "the Airmode flag is actually Acro and the 3d flag is
Airmode" is a **stale Blackbox Explorer release**, not a firmware bug.
The log field `flightModeFlags` actually carries `rcModeActivationMask`
(box bits, `blackbox.c` "//was flightModeFlags"). Firmware 2026.6.0 added
`BOXAUTOPILOT` at bit 11, shifting every later box by one. The viewer
fixed its table in betaflight/blackbox-log-viewer#904 (merged 2026-04-08),
but the latest release 2025.12.1 (2026-02-14) predates the fix, so it
labels bit 23 (BLACKBOX switch — on all flight, hence "always on in acro")
as "AIRMODE" and bit 24 (the real AIRMODE) as "3D". Raw masks decoded from
these logs confirm: flight 1 = 0x800001 (ARM+BLACKBOX), flight 2 toggles
0x1800001 (+AIRMODE). Workaround until a viewer release ships: read
"AIRMODE" as BLACKBOX and "3D" as AIRMODE, or use the viewer built from
master.

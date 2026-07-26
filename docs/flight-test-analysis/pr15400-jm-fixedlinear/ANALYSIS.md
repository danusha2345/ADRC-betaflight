# jmsweng 5", 2026-07-25 — FIXED vs LINEAR b0 law A/B (b5)

Source: PR [betaflight#15400] comment of 2026-07-25 (`Fixed and linear law.zip`;
the two `.bbl` originals preserved here verbatim). Reproduce: decode with the
pinned `blackbox_decode` (`--debug --unit-frame-time us`), then
`python3 law_ab.py`.

**Provenance** (headers): both flights `543f1a5ff` = exactly the b5 tag,
DAKEFPVF405, `pid_type = ADRC`, `debug_mode = ADRC`, identical tune
wc 40 / wo 100 / b0 2000 (all axes), `adrc_hover_throttle = 28`,
`adrc_liftoff_throttle = 40`, `thrust_linear = 0`, `motor_poles = 14`.
The only intended difference: `Fixed.bbl` has `adrc_b0_law = 3` (FIXED),
`Linear.bbl` has `adrc_b0_law = 2` (LINEAR). Conditions per the pilot:
extremely windy, one replaced prop, others still damaged from earlier tests.

## Result — FIXED rings at high collective, LINEAR (schedule live) is clean

Hardened ring criterion (same as `pr15400-b5-wcwo2x2/wcwo_2x2.py`: 1 s
windows, 0.25 s hop, calm setpoint, 18–32 Hz max-axis band RMS > 10 dps):

| flight | airborne | thr med/max | b0 scale med/max | ring windows | worst |
|---|---|---|---|---|---|
| FIXED | 29.1 s | 32 % / 100 % | 1.00 / 1.00 | **2/35, 1 episode** | **41.4 dps @ 24.0 Hz** (roll) |
| LINEAR | 70.5 s | 48 % / 100 % | 1.71 / **3.00** | 0/19 | 4.6 dps |

The FIXED episode runs 4.8–6.0 s at collective ~61 % (p90 76 %).

Two observations beyond the headline:

- **This is the first dataset where a b0 schedule is confirmed live in
  flight**: with `adrc_hover_throttle = 28` matching the craft, LINEAR's
  `debug[7]` multiplier ran med 1.71 and hit the ×3.0 cap. Every previous
  law dataset (including the 8ksal8 sweep) had the multiplier pinned at
  ×1.00 by a too-high hover setting, i.e. effectively compared FIXED to
  FIXED.
- **Quantitative consistency**: at the episode's ~61 % collective with
  hover = 28 %, LINEAR commands scale ≈ 2.2 while FIXED holds 1.00 — a ~2×
  loop over-gain for FIXED right where it rings, and the ring sits at
  24 Hz, the same frequency family as ADRC-024's episodic ring (24–26 Hz).

## What this does and does not establish

Supports the *direction* that some upward b0 scheduling above hover is
needed on this craft — i.e. the FIXED law degrades loop stability margin at
high collective. It does **not** establish LINEAR as the true physical
b0(throttle) law (SQRT wasn't in this pair; identification is ADRC-021's
doublet protocol), and "FIXED is definitely incorrect" is stronger than one
unbalanced pair of flights supports: separate sessions (29 vs 70 s airborne,
median collective 32 vs 48 %), heavy wind, damaged props, no randomization.
Bracket-level evidence, consistent with the 2026-07-19 law A/B's rebound
ordering.

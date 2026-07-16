# 2026-07-15/16 flight-data analysis: b0 law (ADRC-021), ring sensitivity (ADRC-024), rebound (ADRC-025)

**Verdict up front**:

1. **ADRC-021, now on two crafts**: the shipped b0 throttle law
   (`scale = clamp((collective/hover)^2, 1, 3)`) **over-scales**. Measured
   plant-gain growth from hover to 40–60 % collective is **×1.3–1.7** on the
   PR author's SPEEDYBEE and **×1.4** on jmsweng's DAKEFPV — not the ×2.3–3
   the quadratic applies there; below hover (SPEEDYBEE) the true gain *falls*
   to ~×0.6 while the clamp holds ×1. On both crafts the quadratic law scores
   *worse than applying no schedule at all*; sqrt fits best on both. Both
   estimators (direct regression and the observer's own z3) agree the ESO
   over-estimates its control authority everywhere except right at hover.
2. **ADRC-024 has measured discriminators now**: at fixed b0 law the ring
   incidence/amplitude **grows with wc** (wc 85: 11 % of hover-band windows,
   up to 39 deg/s) and **collapses with higher wo** (wo 150: one window,
   5.4 deg/s) **and with the low-wc converted tune** (wc 37: one window,
   6.5 deg/s) — a phase-margin signature at the loop/observer level, matching
   jmsweng's independent "wc ≈ 40 quiets it" observation.
3. **ADRC-025 persists** (18 pooled calm punch→chop events on the base tune:
   median 60, max 135 deg/s, z3-pitch to the 524k debug rail on the biggest
   punch) — same picture as the b4 verification flight.
4. Hover-band absolute b0 confirms the defaults on **both crafts**
   (~2100–2300 SPEEDYBEE, ~1800–2100 DAKEFPV vs shipped 2000 and converter
   2252–2328).

## Data & provenance

Ten flights by @bvandevliet, 2026-07-15, SPEEDYBEEF7MINIV2 (craft
`NLDj4wldvf6akwve`, hover ≈ 22 % collective, `adrc_hover_throttle = 22`).
Build: `Betaflight 2026.6.0-alpha (norevision)`, built Jul 15 2026 19:37 =
`35adbf14e6` — PR #15400 head `eda3bb16eb` + one commit (opt-in cascade ESO;
inactive in p1/p2 profiles, `wo2 == 0` → exact single-stage behavior, see
`adrc.c`). Profiles (from the `diff all` in this directory): **p1** = defaults
60/100/2000, **p2** = converted stock tune 37-38/149-150/2252-2328, **p3** =
cascade experiment (excluded from identification — not PR code).

Original `.bbl` files and the `diff all` export are preserved in this
directory (the source share expires). Videos/OSD are archived offline.

Second craft: two logs by @jmsweng, 2026-07-15, preserved in `jmsweng/`
(from the PR comment attachment) — provenance and settings in the
second-craft section below.

## Method (`identify_b0.py`, `fit_b0_law.py`)

Model frame = the ESO's own (`adrc.c`): `omega_ddot = f + b0*u`,
`u = constrain(pidSum, ±500)` (= `axisP+axisI+axisD` for ADRC; the same
clamped Sum is fed back to the ESO via `adrcSetAppliedOutput()`).

- Decode: `blackbox_decode` defaults, fs = 1592 Hz, `gyro_scale = 1.0` (deg/s).
- Per 0.4 s window (50 % overlap): gate open (`debug[7] > 0`), no motor
  clipping (48..2047 range, guard 60/1950), band-limited (1.5–25 Hz,
  zero-phase Butterworth both signals) OLS slope of measured `omega_ddot`
  (double gradient of 25 Hz-low-passed gyro) on `u` → `b0_hat`; keep
  R² ≥ 0.5, slope > 0, excitation RMS ≥ 8 pidSum units.
- Collective = mean motor output normalized to 0–100 % (the mixer-collective
  the b0 schedule low-passes), window-mean.
- Law scoring: pooled windows, per-law best-fit `b0_hover` in log space, score
  = RMS of `log2(b0_hat / model)`.

## Results (159 windows, 9 logs, roll 81 / pitch 78)

Pooled bins (mixer-collective %, `fit_b0_law.py` output):

| bin % | n | b0_hat median | ratio to hover bin |
|---|---|---|---|
| 10–15 | 6 | 1223 | 0.56× |
| 15–20 | 22 | 2042 | 0.94× |
| 20–25 | 28 | 2170 | 1.00× |
| 25–30 | 30 | 2671 | 1.23× |
| 30–35 | 43 | 3326 | 1.53× |
| 35–40 | 15 | 2832 | 1.31× |
| 40–45 | 7 | 3524 | 1.62× |
| 45–50 | 3 | 3342 | 1.54× |
| 50–55 | 3 | 3670 | 1.69× |

Law scores (lower is better):

| law | best-fit b0_hover | RMS log2 |
|---|---|---|
| sqrt `(c/h)^0.5` | 2254 | **0.425** |
| linear `c/h` | 2016 | 0.453 |
| linear `clamp(c/h,1,3)` | 1917 | 0.456 |
| fixed `scale=1` | 2521 | 0.512 |
| **code** `clamp((c/h)^2,1,3)` | 1523 | 0.541 |
| quad uncapped `(c/h)^2` | 1613 | 0.757 |

The shipped quadratic law scores **worse than applying no schedule at all**;
sqrt and linear fit best. Hover-band (18–27 %) absolute medians: roll 2272,
pitch 2149 — no meaningful axis asymmetry, and both within ~10 % of the
default 2000 and ~5 % of the converter's 2252–2328.

## Cross-check: the observer's own z3 (independent estimator)

If `b0_eff = b0 * scale` is exactly right, z3 is uncorrelated with u. Measured
(z3 = `debug[2]`·16, roll, same windowing, rail-free windows only): the
z3-on-u slope is **negative in every collective bin of every log checked**
(001/006/010: −0.5 k to −2.0 k), i.e. `b0_eff > b0_true` across the band —
matching the direct estimator's sign everywhere, with the worst mismatch
above 30 % collective where the quadratic law applies ×2.3–3. (Magnitudes are
attenuated relative to the direct estimator's prediction, as expected from
the ESO's finite bandwidth; this check is qualitative.)

## Sensitivity & caveats

- **Law shape is robust**: hover→(40–60 %) growth stays 1.3–1.7× under
  LP 25→35 Hz, window 0.25/0.4/0.6 s, R² ≥ 0.35/0.5. The degenerate LP=15 Hz
  run (n=48, most of the `omega_ddot` band removed) is the one outlier.
- **Absolute b0_hat is band-dependent**: apparent gain rises with the analysis
  band (LP 15/25/35 Hz → hover ~470/2240/3610), consistent with the physical
  plant being closer to first-order in rate (prop drag) than the ESO's
  double-integrator frame. We therefore quote absolute values in the 1.5–25 Hz
  band, which covers the controller's operating region (wc = 60 rad/s ≈ 10 Hz,
  wo = 100 rad/s ≈ 16 Hz); the *relative* law is what ADRC-021 needs and it is
  band-stable.
- Motor-lag phase bias reduces slopes somewhat (direction: underestimate);
  it is common-mode across collective bins at fixed band.
- Single craft, single day, vbat not controlled per-bin (sag partially
  confounds the ≥45 % bins). p2-vs-p1 cross-tune agreement holds where both
  sample the same bin (30–35 %: 3942 vs 3326–3929) but p2 contributes few
  windows overall.
- 35–40 % bin dips (2832, wide IQR) — small n and mixed maneuvers; the
  neighboring bins bracket it.

## ADRC-021 on a second craft: jmsweng's b4 logs (`fit_b0_jmsweng.py`)

Two logs, 2026-07-15 (in `jmsweng/`): `42-100-2000.bbl` and
`Converted stock PID.bbl` (37-38/149-150/2252-2328). Provenance: both
`Betaflight 2026.6.0-alpha (08ad602ce) STM32F405`, built Jul 12 — **exactly
the b4 prebuilt release**. Board DAKE DAKEFPVF405, 2300 kV 5",
`motorOutput 158..2047`, log rate 988 Hz. `adrc_hover_throttle` left at the
default 35; measured steady-stick collective ≈ 31 % (median, first log) — the
default happens to be close on this craft.

Same estimator, 71 pooled windows (both logs, both axes):

| bin % | n | b0_hat median |
|---|---|---|
| 20–25 | 9 | 1816 |
| 25–30 | 6 | 1763 |
| 30–35 | 12 | 1809 |
| 35–40 | 21 | 2070 |
| 40–45 | 13 | 2108 |
| 45–50 | 4 | 2344 |
| 50–55 | 4 | 2530 |

Growth 20 %→55 % ≈ **×1.4** — even shallower than the SPEEDYBEE. Law scores
in this craft's frame (hover = 35): sqrt 0.294 < fixed 0.331 < code-quadratic
0.345 < linear 0.360 — on this craft even **no schedule at all beats the
shipped law**. Hover-band absolute ≈ 1800–2100: his `b0 = 2000` is spot-on,
the converter's 2252/2328 slightly high but within ~15 %.

## ADRC-024: ring sensitivity to wc/wo (`ring_sensitivity.py`)

Ring window = gate-open, 10–35 % stick throttle, dominant 18–32 Hz tone,
amp > 5 deg/s, tone fraction > 0.5 (the b4 ADRC-024 signature):

| variant | windows | ring n | ring % | amp max (deg/s) |
|---|---|---|---|---|
| base wc60/wo100 (001/005/006/010) | 324 | 15 | 2–9 % per log | 19.7–32.7 |
| **007 wc60/wo150** | 19 | 1 | 5 % | **5.4** |
| **008 wc85/wo100** | 81 | 9 | **11 %** | **39.2** |
| **002/009 p2 wc37-38/wo149-150** | 75 | 2 | 2–4 % | 6.5 / 12.1 |

At a fixed b0 law, raising wc makes the ring worse; raising wo (or flying the
low-wc converted tune) nearly eliminates it. That is a phase-margin signature
at the loop/observer level. Caveats: 007 is a short log (19 usable windows);
all one day, one craft; b0-mismatch (ADRC-021) still varies underneath as the
gain-scheduling backdrop and is not excluded as a contributor.

**Cross-craft check (jmsweng, `analyze_jmsweng.py`)**: his hover band shows
*no* 24–27 Hz ring — dominant low-frequency content sits at 10–19 Hz with
median tone ≈ 1 deg/s (unremarkable). One suggestive exception: a single
window at t=16 s (converted-stock log), 35 % throttle, **24 Hz, 19 deg/s,
tone fraction 0.77, right after a power loop** — consistent with an
ADRC-024-style event-ignited ring, but a single window is not a
reproduction. His *audible* oscillation is most likely the strong
high-frequency line his `gyroUnfilt` carries in calm windows (log-frame
150–200 Hz, 7–15 deg/s; true frequency unresolvable at the 988 Hz log rate —
aliasing — but it is loud, mechanical/motor-band, and present on both tunes),
not the 24–27 Hz phenomenon.

## ADRC-025: rebound on the new flights (`punches_20260715.py`)

Same event criteria as the b4 analysis. p1 (base tune) pooled across
003/006/010: **18 calm punch→chop events, peak-pitch median 60, max
135 deg/s**; rebound scales with punch height (75–89 % punches → 127–135;
40–55 % punches → 13–94) and the biggest punch rails z3-pitch to the 524k
debug limit. p2 (converted tune, 009): 4 events, 79–102 deg/s at 45–54 %
punches. Not a controlled A/B against the 2026-07-14 b4 flights (different
punch mix), but the phenomenon clearly persists on both tunes.

## jmsweng's power-loop "sticking" (z3 rail episodes)

In his converted-stock log, **2.74 % of samples have z3-pitch at the ±524k
debug rail, 11 episodes** — every one coincides with a flip/loop segment
(|gyro pitch| 750–1010 deg/s) or a zero-throttle drop, including the power
loops at t=13–14 s and t=40–41 s (97–99 % throttle, 4.1–4.6 g). At the rail
the logged value is clipped, and the ESO's own clamp (`pidSumLimit·b0_eff`)
means a railed z3 is contributing up to the *entire* pidSum budget through
the I-equivalent term. This is a correlation, not an established cause of the
"sticks upside-down" feel — but it marks the flip exit as the moment the
controller is fighting its own saturated disturbance estimate, and the
high-collective b0 over-scale (ADRC-021) inflates exactly the `b0·u` term the
ESO mis-attributes during those maneuvers.

## Cascade-ESO experiment (004, p3 — not PR code)

For the record: the p3 flight (opt-in second-stage ESO, `adrc_cascade_alpha
= 60`, author's own experiment on top of the PR head) shows a **sustained
~35 Hz roll oscillation from the moment of takeoff** (20–26 deg/s tone),
aborted after 5.7 s. Quantifies the author's own "didn't work well"; not part
of the PR-branch verdicts above.

## What this means for the open items

- **ADRC-021**: the quadratic exponent is wrong on **both measured crafts**;
  the data prefer ~sqrt growth (best score on both) with total span
  ≈0.6×–1.7× across 10–55 % collective. A conservative fix candidate: sqrt or
  linear `c/h` with a cap well below 3 (data support ≈1.7–2); the below-hover
  clamp at 1 keeps `b0_eff` ~1.6× too high at 10–15 % on the craft measured
  there and is worth revisiting with the law. The "more than one 5″"
  requirement in the protocol is now met (SPEEDYBEE F7 MINI V2 + DAKEFPVF405,
  independently tuned, different hover points 22 %/35 %).
- **ADRC-022 (defaults)**: hover-band b0 measured ≈1800–2300 across both
  crafts — the shipped `b0 = 2000` default and the converter's numbers are
  flight-confirmed at hover. jmsweng independently proposes defaulting to the
  converted-stock numbers or 60/100/2000 rather than the tuning-guide's
  10/50/200 starting point.
- **ADRC-024**: no longer hypothesis-only — the ring responds strongly to
  wc/wo at fixed b0 law (worse with wc↑, nearly gone with wo↑ or wc≈37),
  pointing at loop/observer phase margin as the ignition-carrying mechanism,
  with the b0 over-scale (measured here) as the gain-scheduling backdrop.
  Discriminating margin-only vs margin+b0 requires re-flying the ring band
  after a b0-law fix.
- **ADRC-025**: persists on both tunes (median 60, max 135 deg/s on the new
  base-tune events); every large rebound coincides with a z3 transient toward
  the rail, and the punch regime is exactly where the quadratic law
  over-scales b0 the most — fixing ADRC-021 first and re-measuring is the
  cheapest next discriminator.

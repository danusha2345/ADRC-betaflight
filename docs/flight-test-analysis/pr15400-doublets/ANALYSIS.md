# ADRC-021: b0-vs-collective identification from the 2026-07-15 doublet flights

**Verdict up front**: on this craft the shipped b0 throttle law
(`scale = clamp((collective/hover)^2, 1, 3)`) **over-scales**. The measured
plant-gain growth from hover to 40–60 % collective is **×1.3–1.7**, not the
×2.3–3 the quadratic law applies there; below hover the true gain *falls* to
~×0.6 while the clamp holds the model at ×1. Both estimators (direct
regression and the observer's own z3) agree the ESO over-estimates its
control authority everywhere except right at hover. The hover-band absolute
value (~2100–2300 in the controller-relevant band) independently confirms the
flight-evolved default `b0 = 2000` and the PID-converter's 2252–2328.

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

## What this means for the open items

- **ADRC-021 (this item)**: the quadratic exponent is wrong for this craft;
  the data prefer ~sqrt-to-linear growth with total span ≈0.6×–1.7× across
  10–55 % collective. A conservative fix candidate: linear `c/h` with a cap
  well below 3 (data support ≈1.7–2), or sqrt; and the below-hover clamp at 1
  keeps `b0_eff` ~1.6× too high at 10–15 % — worth revisiting once a law is
  chosen.
- **ADRC-022 (defaults)**: hover b0 ≈ 2000–2300 measured — the shipped 2000
  default and the converter's numbers are flight-confirmed at hover on a
  second craft.
- **ADRC-024/025**: with the shipped law, the controller runs under-gained
  (authority over-estimated) increasingly above ~25 % collective and mildly
  below hover — consistent with (not yet proof of) the rebound's weak-control
  phase and with the ring living where the mismatch is changing fastest.
  Mechanism work stays open.

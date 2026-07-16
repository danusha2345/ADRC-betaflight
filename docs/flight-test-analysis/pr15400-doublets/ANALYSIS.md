# 2026-07-15/16 flight-data analysis: b0 law (ADRC-021), ring sensitivity (ADRC-024), rebound (ADRC-025)

**Verdict up front**:

1. **ADRC-021, now on two crafts**: the shipped b0 throttle law
   (`scale = clamp((collective/hover)^2, 1, 3)`) **over-scales**. Measured
   plant-gain growth from hover to 40–60 % collective is **×1.3–1.7** on the
   PR author's SPEEDYBEE and **×1.4** on jmsweng's DAKEFPV — not the ×2.3–3
   the quadratic applies there; below hover (SPEEDYBEE) the true gain *falls*
   to ~×0.6 while the clamp holds ×1. On this corpus the quadratic law scores
   worse than applying no schedule at all (the code-vs-fixed gap shrinks to
   +0.004 in the worst leave-one-log-out subset — a corpus-level result, not
   a universal fact); sqrt has the best *pooled* score on both crafts, though
   the per-log winners on jmsweng's two logs are fixed and linear — the data
   select against the quadratic, they do not yet select the production
   exponent. The direct regression and the ESO's own model residual (z3, a
   qualitative cross-check on the same data, not an independent estimate)
   agree in sign: the ESO over-estimates its control authority everywhere
   except right at hover.
2. **ADRC-024 gained suggestive discriminators**: at fixed b0 law the wc 85
   flight shows **increased ring incidence and amplitude** (11 % of
   hover-band windows, 5 episodes, up to 39 deg/s vs base 2–9 %/2 episodes
   per log/20–33 deg/s). The short wo 150 flight (19 usable windows) contains
   **no strong ring** — one threshold-level window at 5.4 deg/s — but is too
   short to establish an incidence reduction; the low-wc converted tune shows
   one weak window per log. Consistent with a phase-margin hypothesis
   (and with jmsweng's independent "wc ≈ 40 quiets it"), **not yet a causal
   discriminator** — flights were not randomized or maneuver-controlled.
3. **ADRC-025 persists** (18 pooled calm punch→chop events on the base tune:
   median 60, max 135 deg/s; one of the larger punches — 79 %, 127 deg/s
   rebound — reaches the ±524k debug clipping limit, while neither the
   highest-throttle nor the maximum-rebound event does) — same picture as the
   b4 verification flight.
4. Hover-band absolute b0 supports `b0 = 2000` as a conservative hover
   starting point on **both crafts** (~2100–2300 SPEEDYBEE, ~1800–2100
   DAKEFPV). The converter's 2252–2328 is close on the SPEEDYBEE; on the
   DAKEFPV it sits ~18–22 % above the direct pooled estimate — flight-tested
   and flyable, but not independently confirmed there.

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

- Decode: `blackbox_decode <log>.bbl` (defaults, no `--unit-rotation`;
  betaflight/blackbox-tools commit `f832acf9cd`), fs = 1592 Hz,
  `gyro_scale = 1.0` (deg/s).
- Per 0.4 s window (50 % overlap): gate open (`debug[7] > 0`), no motor
  clipping (48..2047 range, guard 60/1950), band-limited (1.5–25 Hz,
  zero-phase Butterworth both signals) OLS slope of measured `omega_ddot`
  (double gradient of 25 Hz-low-passed gyro) on `u` → `b0_hat`; keep
  R² ≥ 0.5, slope > 0, excitation RMS ≥ 8 pidSum units.
- Collective = mean motor output normalized to 0–100 % (the mixer-collective
  the b0 schedule low-passes), window-mean.
- Law scoring: pooled windows, per-law best-fit `b0_hover` in log space, score
  = RMS of `log2(b0_hat / model)`.

Reproducibility: decode the committed `.bbl` in place (`blackbox_decode
*.bbl && blackbox_decode jmsweng/*.bbl`, blackbox-tools `f832acf9cd`, no
flags), then the primary tabulated metrics regenerate from the committed
scripts — `identify_b0.py` /
`fit_b0_law.py` / `fit_b0_jmsweng.py` (b0 law), `sensitivity.py` (sweeps,
non-overlapping windows, leave-one-log-out, frequency-covariate exponent),
`z3_check.py` (observer cross-check), `ring_sensitivity.py` (ADRC-024
windows/episodes), `punches_20260715.py` (ADRC-025 events),
`analyze_jmsweng.py` (second-craft overview, z3 rail episodes with
flip/zero-throttle classification, wide-band scan), `cascade_scan.py` (p3
experiment). Exceptions are attributed inline (the review's ad-hoc ~0.74
exponent variant is external to these scripts). The intermediate
`.csv`/`.event` decode products are not committed — they are
byte-reproducible from the `.bbl` with the pinned decoder.

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

On this corpus the shipped quadratic law scores **worse than applying no
schedule at all**; sqrt and linear fit best. Robustness (`sensitivity.py`):
with non-overlapping windows (n=82) the ranking holds (sqrt 0.441 / linear
0.453 / fixed 0.540 / code 0.544); in leave-one-log-out runs sqrt stays first
every time, while the code-vs-fixed gap ranges +0.004…+0.052 — so
"worse than no schedule" is a corpus-level result, not a per-log invariant.
A descriptive log-log fit of `b0_hat` on collective with a
dominant-excitation-frequency covariate and per-log fixed effects gives a
collective exponent of **0.88** (the external review's ad-hoc centroid
variant — not generated by these scripts — got ~0.74) — both far from the
2 the shipped law implies below its cap; note this is
closed-loop system identification on selected windows, not an unbiased causal
estimate. Hover-band (18–27 %) absolute medians: roll 2272, pitch 2149 — no
meaningful axis asymmetry, both within ~10 % of the default 2000 and ~5 % of
the converter's 2252–2328.

## Cross-check: the observer's own z3 (qualitative ESO model-residual check)

Not an independent plant-gain estimate — it reuses the same u, gyro and b0
law — but a consistency check on the ESO's own model residual: if
`b0_eff = b0 * scale` were exactly right, z3 would be uncorrelated with u.
Measured (`z3_check.py`: z3 = `debug[2]`·16, roll; same window length,
overlap, gate, no-clip and u-RMS criteria as the direct estimator, but
*without* its R² ≥ 0.5 / positive-slope selection; rail-free windows only):
the z3-on-u slope is **negative in every collective bin of every log
checked** (001/006/010: −0.5 k to −2.0 k), i.e. the ESO consistently
attributes a control-correlated component to disturbance with the sign of
`b0_eff > b0_true`, worst above 30 % collective where the quadratic law
applies ×2.3–3. (Magnitudes are attenuated relative to the direct
estimator's prediction, as expected from the ESO's finite bandwidth; this
check is qualitative.)

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
shipped law** (also with non-overlapping windows: fixed 0.317 vs code 0.387).
Per-log winners differ, though: fixed on `42-100-2000`, linear on the
converted-stock log; sqrt is best only after pooling — the corpus rejects the
quadratic without picking one production exponent. Hover-band absolute
≈ 1800–2100: his `b0 = 2000` is spot-on; the converter's 2252/2328 sits
~18–22 % above the pooled best-fit hover value (~1910) — flight-tested and
flyable here, but its b0 is not independently confirmed on this craft (the
flight also does not isolate b0 from the tune's different wc/wo).

## ADRC-024: ring sensitivity to wc/wo (`ring_sensitivity.py`)

Ring window = gate-open, 10–35 % stick throttle, dominant 18–32 Hz tone,
amp > 5 deg/s, tone fraction > 0.5 (the b4 ADRC-024 signature):

| variant | windows | ring n | ring % | amp max (deg/s) |
|---|---|---|---|---|
| base wc60/wo100 (001/005/006/010) | 324 | 15 | 2–9 % per log | 19.7–32.7 |
| **007 wc60/wo150** | 19 | 1 | 5 % | **5.4** |
| **008 wc85/wo100** | 81 | 9 | **11 %** | **39.2** |
| **002/009 p2 wc37-38/wo149-150** | 75 | 2 | 2–4 % | 6.5 / 12.1 |

Independent-episode counts (ring windows merged within 1.5 s): base logs 2
each, wc 85 → 5, wo 150 → 1, converted logs 1 each.

Reading this honestly: the **wc 85 flight is suggestive of increased ring
incidence and amplitude**. The short wo 150 flight contains no strong ring
(its single window is threshold-level, 5.4 deg/s, and its 5 % incidence sits
inside the base logs' 2–9 % range), but 19 usable windows are too few to
establish an incidence reduction. The pattern is **consistent with a
phase-margin hypothesis, not yet a causal discriminator** — flights were not
randomized or maneuver-controlled, all one day, one craft, and the
b0-mismatch (ADRC-021) still varies underneath as the gain-scheduling
backdrop and is not excluded as a contributor.

**Cross-craft check (jmsweng, `analyze_jmsweng.py`)**: his hover band shows
*no* 24–27 Hz ring — dominant low-frequency content sits at 10–19 Hz with
median tone ≈ 1 deg/s (unremarkable). One suggestive exception: a single
window at t=16 s (converted-stock log), 35 % throttle, **24 Hz, 19 deg/s,
tone fraction 0.77, right after a power loop** — consistent with an
ADRC-024-style event-ignited ring, but a single window is not a
reproduction. Separately, his `gyroUnfilt` carries a strong high-frequency
line in calm windows (log-frame 150–200 Hz, 7–15 deg/s; the true frequency is
unresolvable at the 988 Hz log rate — aliasing — and it is present on both
tunes). That line is a **plausible mechanical/motor-band candidate** for what
he hears; without blackbox-to-audio synchronization its relationship to the
audible oscillation is unproven. What the logs do establish is that his hover
band shows no sustained 24–27 Hz ring.

## ADRC-025: rebound on the new flights (`punches_20260715.py`)

Same event criteria as the b4 analysis. p1 (base tune) pooled across
003/006/010: **18 calm punch→chop events, peak-pitch median 60, max
135 deg/s**; rebound scales with punch height (75–89 % punches → 127–135;
40–55 % punches → 13–94). One of the larger punch events (78.7 % throttle,
127 deg/s rebound) reaches the ±524k blackbox debug clipping limit on
z3-pitch; neither the highest-throttle event (88.8 %, 132 deg/s, z3 238k) nor
the maximum-rebound event (75.0 %, 135 deg/s, z3 260k) clips the debug
channel. p2 (converted tune, 009): 4 events, 79–102 deg/s at 45–54 %
punches (one also reaching the debug clip). Not a controlled A/B against the
2026-07-14 b4 flights (different punch mix), but the phenomenon clearly
persists on both tunes.

## jmsweng's power-loop "sticking" (z3 rail episodes)

In his converted-stock log, **2.74 % of samples have z3-pitch at the ±524k
debug rail, 11 episodes**. Ten of the eleven coincide with an aggressive
flip/loop segment (|gyro pitch| 750–1010 deg/s) or a zero-throttle drop,
including the power loops at t=13–14 s and t=40–41 s (97–99 % throttle,
4.1–4.6 g); one episode (t≈62.3 s, ~56 % throttle, |gyro pitch| ≤ 61 deg/s in
the episode, ≤ 84 deg/s in ±0.5 s context) fits neither pattern and remains
unexplained. Interpretation limit: ±524k is the **int16 telemetry clip**
(`debug = z3/16`), not the ESO's internal clamp (`pidSumLimit·b0_eff`, which
can be several times higher) — the logs only establish |z3| ≥ 524k during
these episodes; the true magnitude lies somewhere between the debug threshold
and the internal authority clamp, so how much of the pidSum budget the
I-equivalent term actually consumed is unknown. The coincidence with flip
exits is a correlation, not an established cause of the "sticks upside-down"
feel; the high-collective b0 over-scale (ADRC-021) inflating the `b0·u` term
the ESO mis-attributes during those maneuvers is the candidate mechanism to
test after a law fix.

## Cascade-ESO experiment (004, p3 — not PR code)

For the record: the p3 flight (opt-in second-stage ESO, `adrc_cascade_alpha
= 60`, author's own experiment on top of the PR head) shows a **sustained
~35 Hz roll oscillation from the moment of takeoff** (20–26 deg/s tone),
aborted after 5.7 s. Quantifies the author's own "didn't work well"; not part
of the PR-branch verdicts above.

## What this means for the open items

- **ADRC-021**: both measured crafts independently show substantially
  shallower authority growth than the shipped quadratic schedule (span
  ≈0.6×–1.7× across 10–55 % collective). **sqrt and linear are the grounded
  candidates for a controlled A/B** — the corpus rejects the quadratic but
  does not yet pick the production exponent (pooled winner sqrt; per-log
  winners vary). Cap around 1.7–2 (not 3) and the below-hover clamp behavior
  (holds ×1 where the measured gain is ~0.6×) need their own test. The "more
  than one 5″" requirement in the protocol is met (SPEEDYBEE F7 MINI V2 +
  DAKEFPVF405, independently tuned, different hover points 22 %/35 %).
- **ADRC-022 (defaults)**: `b0 = 2000` is well supported as a conservative
  hover starting point across both crafts. The converter values are close on
  the SPEEDYBEE and remain a plausible flight-tested starting point on the
  DAKEFPV, but appear ~18–22 % high in that craft's direct estimate. jmsweng
  independently proposes defaulting to the converted-stock numbers or
  60/100/2000 rather than the tuning-guide's 10/50/200 starting point.
- **ADRC-024**: the wc 85 flight is suggestive of increased ring incidence
  and amplitude; the short wo 150 flight shows no strong ring but cannot
  establish an incidence reduction. Phase margin is the **working
  hypothesis, not an established cause**; the b0 over-scale (measured here)
  remains the gain-scheduling backdrop. The informative next test is a
  randomized/controlled wc-wo-law A/B on one unchanged craft, or at minimum
  re-flying the ring band after a b0-law fix.
- **ADRC-025**: persists on both tunes (median 60, max 135 deg/s on the new
  base-tune events); large rebounds coincide with large z3 transients (one
  reaching the debug clip) — a correlation, with the causal link to the b0
  schedule and z3 saturation unproven. The punch regime is exactly where the
  quadratic law over-scales b0 the most, so fixing ADRC-021 first and
  re-measuring is the cheapest next discriminator.

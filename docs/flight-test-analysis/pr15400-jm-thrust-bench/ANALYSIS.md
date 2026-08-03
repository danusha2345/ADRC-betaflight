# @jmsweng's kitchen-scale thrust stand (2026-08-03) — what it measures, and what it can say about `adrc_b0_law`

Source: PR comment 5161126252. An Air65 held upside down over a kitchen scale,
motors driven to fixed throttle values from the Configurator, fresh 1S packs
swapped every few points; ~20 points from 1000 to 2000, plus a desk-fan
inflow probe and three fits (linear / quadratic / sqrt) with 95 % prediction
intervals. Prop/motor: Gemfan 1219s-3 on 0702-27000 kV, whose manufacturer
sheet he also attached.

The experiment is worth continuing. The conclusion drawn from it — "the fits
are equally bad, so the schedule shape is unknowable; probably `LINEAR`" —
does not follow, because of one transform that was skipped.

## 1. A schedule shape follows the *slope* of the thrust curve, not the thrust

The mixer adds a per-axis differential to each motor command:
`cmd_i = collective + k_i · u`, with `k_i` constant in the unsaturated region.
The body torque is `τ = l · Σ s_i T(cmd_i)`, so for a small control excursion
around an operating point the static torque gain is

```
∂τ/∂u ≈ l · (dT/dcmd) · Σ|k_i|
```

The stand measures `T(cmd)`; the schedule needs `dT/dcmd`. Differentiating
inverts the mapping the comment used:

| measured shape of `T(cmd)` | implied `dT/dcmd` | schedule shape it argues for |
|---|---|---|
| linear | constant | FIXED |
| quadratic | linear | LINEAR |
| `cmd^1.5` | `cmd^0.5` | SQRT |
| cubic | quadratic | QUADRATIC |

So "the data look roughly linear" argues for FIXED, not LINEAR.

**Scope of that statement, deliberately narrow.** `dT/dcmd` is a *static
roll/pitch proxy for the scheduling shape*, not an identification of this
implementation's `b0`. Three reasons to keep it labelled that way:

- This ADRC models `ω̈ = z3 + b0·u` (third-order ESO; `adrc.h` gives `b0` in
  deg/s³ per PID output), so `b0` sits one derivative above the static torque
  gain and absorbs the ESC/motor/prop response and loop delays. A static
  bench cannot see any of that.
- Yaw is driven by the propeller *reaction torque*, so its slope is `dQ/dcmd`
  — a quantity a downward-reading scale does not measure at all.
- The proxy only constrains the *shape* under the assumption that the
  actuator dynamics do not themselves vary strongly with throttle. That
  assumption is untested here.

## 2. Running the transform on his own manufacturer sheet

Per-motor, 4.2 V, from the attached Gemfan chart (`thrust_slope.py`). The
craft's hover point is not known for that bench, so the normalisation is swept
rather than assumed:

| normalising hover | slope ratio at 40 % | at 60 % | at 80 % | at 100 % |
|---:|---:|---:|---:|---:|
| 25 % | 1.27 | 1.35 | 1.33 | 0.94 |
| 29 % | 1.11 | 1.18 | 1.16 | 0.82 |
| 31 % | 1.07 | 1.13 | 1.12 | 0.79 |
| 35 % | 1.04 | 1.10 | 1.09 | 0.77 |

Across every plausible hover the slope ratio stays inside 0.77–1.35 with no
systematic rise — above ~30 % the sheet is close to a straight line with a
negative intercept (`T ≈ 0.423·thr − 7.2 g`, every tabulated point within
0.8 g), which is a constant slope by construction. Caveats that belong with
those numbers: it is vendor data at one voltage on a 10-point grid, and the
point-to-point slope itself scatters by 1.44× over 30–100 %, so the
non-monotone details (the dip at 70 %, the 0.8 at 100 %) are grid noise, not
structure.

What the laws would apply over the same span, at hover 29 %: FIXED 1.00, SQRT
1.17–1.86, LINEAR 1.38–3.45, QUADRATIC 1.90–11.89 raw (the firmware clamps to
`adrc_b0_scale_max`, default 3, which binds above ~50 % throttle).

So the sheet, differentiated, lands near FIXED, below SQRT, and far below
QUADRATIC — the same direction the flight data gave independently in ADRC-021
(plant-gain growth hover→40–60 % collective of ×1.3 on two 5″ craft, 559
windows in the b5 A/B). Two very different methods pointing the same way is
worth something; it is not a joint identification, and the two craft classes
are not interchangeable.

## 3. The 97 g vs 138.8 g gap is consistent with pack sag — but is not measured

At 100 % the sheet gives 34.7 g per motor at 4.2 V, i.e. 138.8 g for four,
against the ~97 g measured. The sheet also gives 5.70 A per motor there:
22.8 A out of a 1S whoop pack. At a plausible 30–40 mΩ of pack-plus-wiring
resistance that pack would sit near 3.3–3.5 V under load, and with
`T ∝ ω² ∝ V²` that predicts 86–97 g. The arithmetic lands on the measurement,
but loaded voltage, current and pack resistance were all assumed, not
recorded — so this is a plausibility check that identifies what to log next,
not an attribution.

If it *is* sag, it cuts both ways: part of the "linear" shape would be the
pack rather than the propeller, but it is also the shape the flight controller
experiences, since in flight all four motors draw from the same sagging pack.
Either way, logged pack voltage turns the question from arguable into
measurable.

## 4. Smaller points on the fits

- **Overlapping prediction intervals are not a test of model equivalence.**
  They widen with residual scatter and say nothing about which mean function
  is right; the discriminating evidence is systematic curvature in the
  residuals (or AIC/BIC on the same data).
- **The plotted "sqrt model" is not a sqrt fit.** Fitting a line to squared
  data and inverting produced a curve that falls from 1000 to ~1200 before
  rising — non-monotone, so it cannot be a `√` relation, and it cannot be used
  to reject one. Worth refitting as a free power law `T = a·(cmd − cmd₀)^n`.
- **The fan probe measures inflow sensitivity of `T` at one operating point.**
  Real and worth keeping, but it becomes a statement about scheduling only
  after the same derivative step, and about in-flight `b0` only with a model
  of the inflow a whoop actually sees.

## 5. On "leave FIXED/SQRT as a user selector"

The corpus does not say FIXED is universally unusable — it says one
configuration on one craft was dangerous. In the b5 A/B (2026-07-19), the
FIXED flight on that 5″ at defaults 60/100/2000 was deliberately ditched at
12 s as unflyable: two self-sustained 25.5 Hz episodes, 58–59 dps roll tone,
~10 % of samples at motor saturation at zero stick throttle. That is one
craft, one parameter set, no repeat — enough to say exposing FIXED as a
casual default-adjacent option carries a demonstrated hazard on at least one
airframe, not enough to rule out a selector.

Pooled scoring on that corpus is `sqrt 0.157 < linear 0.173 < fixed 0.186 <
quadratic 0.253`, SQRT winning all 12 leave-one-flight-out refits; LINEAR is
the *leading compromise candidate in the current corpus* because SQRT flares
the ADRC-024 hover ring. The production exponent is not chosen.

## 6. The raw data (2026-08-03, comment 5168882363): the bench does discriminate

`Air65 Throttle vs thrust.csv` (SHA-256
`a970aa4e8cf762b5bc11f56488fac291873441941c538ec91c41f3974c45e9ad`), 25 points,
command 1026–2000, thrust 0–97 g, no voltage column. Fitted properly —
information criterion and residual structure, not band overlap
(`fit_bench.py`):

| model | RSS | resid sd | AICc | runs test |
|---|---:|---:|---:|---|
| affine `T = a·x + b` | 383.1 | 3.91 g | 143.7 | 9 vs 13.0 (z = −1.71) |
| quadratic | 323.2 | 3.60 g | 142.1 | 8 vs 13.3 (z = −2.21) |
| power law `n = 1.04`, dead offset `x₀ = +0.115` | 288.5 | 3.40 g | 139.2 | 12 vs 12.7 (z = −0.29) |

The best model is a power law with exponent 1.04 through a dead command — an
affine curve with an offset, i.e. **a constant slope**, and the only one of the
three whose residual signs show no structure. Its implied slope ratio is
1.02 → 1.06 over 40 → 100 % collective (hover 29 %), which is FIXED.

The data are not sharp enough to stop there. Bootstrapping the most permissive
shape (the quadratic, whose slope is free to grow; 4000 resamples) gives, at
hover 29 %, a slope ratio of **1.15 [0.97, 1.32]** at 60 % collective and
**1.35 [0.94, 1.72]** at 100 %. So this bench:

- is consistent with FIXED (1.00 sits inside both intervals);
- brackets the in-flight doublet estimate (×1.3 at 40–60 % collective) —
  the two methods do not conflict;
- puts SQRT (1.44 at 60 %, 1.86 at 100 %) at or just outside the upper bound;
- **excludes LINEAR (2.07 / 3.45) and QUADRATIC (capped 3.00)** in this
  command range, on this craft, statically.

That is a direct answer to the "the variance is too large to pick a law"
reading: the scatter is large enough that FIXED and SQRT cannot be separated
here, and small enough that the two aggressive laws can be. It is also
consistent with the pilot's own report that fixed and sqrt feel alike on this
whoop — over the collective he actually flies, the two schedules differ by
about 1.0 vs 1.2–1.3 while the measured static slope barely moves.

One gap the data now make visible: the static best fit is flat (≈1.03) while
the in-flight identification measured ×1.3. Whatever separates them —
actuator and prop dynamics, inflow, the fact that this `b0` is defined on
`ω̈` — is exactly the part a scale cannot reach.

## What would make the bench decisive

Raw CSV with `motor command, thrust, pack voltage under load, eRPM (or
current), pack ID, fan setting`. Then: fit a monotone `T(cmd, V)`,
differentiate it, normalise to the measured hover point of that craft, and
compare that curve against the four laws and against the doublet estimate.
Anything beyond scheduling shape — the dynamic `b0` itself, or yaw — needs the
in-flight doublet protocol, not a scale.

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| the static torque gain follows `dT/dcmd`, not `T` | POSITIVE | mixer is additive in command; torque linearised about the operating point | high |
| his linear `T(cmd)` implies LINEAR `b0` scaling | NEGATIVE | it implies FIXED; the transform inverts the mapping | high |
| `dT/dcmd` identifies this implementation's `b0` | NEGATIVE | `b0` is defined on `ω̈` (deg/s³ per PID output) and absorbs actuator dynamics; yaw needs `dQ/dcmd` | high |
| the shipped quadratic came from the same conflation | PLAUSIBLE | `adrc.c` derivation text scales `b0` with thrust rather than its slope; no author statement | low-medium |
| this prop's slope ratio above hover is ≈0.8–1.35 | POSITIVE (vendor data) | `thrust_slope.py`, hover swept 25–35 %; slope itself scatters 1.44× on a 10-point grid | medium |
| bench proxy and flight identification point the same way | POSITIVE (agreement, not joint identification) | slope ratio ~1.1–1.35 (static, whoop) vs plant-gain growth ×1.3 (in flight, two 5″) | medium |
| the 97 g result attributes to pack sag | PLAUSIBLE, UNMEASURED | 22.8 A on 1S predicts 86–97 g at 30–40 mΩ; loaded V/I not recorded | medium |
| the three fits are statistically indistinguishable | PARTLY NEGATIVE | on the raw 25 points, AICc and the runs test prefer a constant slope, and the bootstrap excludes LINEAR/QUADRATIC while leaving FIXED vs SQRT open | medium-high |
| the raw bench data are consistent with FIXED | POSITIVE | best fit `n = 1.04` through a dead offset; slope ratio 1.02–1.06; 1.00 inside the bootstrap interval at 60 % and 100 % | medium |
| the raw bench data contradict the in-flight ×1.3 | NEGATIVE | ×1.3 sits inside the bootstrap interval 1.15 [0.97, 1.32] at 60 % | medium |
| FIXED is universally unsafe to expose | NEGATIVE (overreach) | one craft, one parameter set, one aborted flight — a demonstrated hazard, not a general result | high |

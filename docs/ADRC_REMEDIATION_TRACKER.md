# ADRC review & remediation tracker (PR betaflight#15400)

Public tracker for the review findings against the ADRC branch of
[betaflight/betaflight#15400](https://github.com/betaflight/betaflight/pull/15400).
Maintained by @danusha2345; the full internal runbook (bench logs, local build
matrices, per-craft configs) is kept out of the PR tree — this is the complete
list of findings, their status, and what remains open.

All remediation SHAs in the table below are reachable from the current PR head
on `bvandevliet:adrc-toggle`. The review baseline was the previous, pre-rebase
head `a138a5dd19`; the remediation series landed with the force-push to
`9d04e46d57` and the follow-ups on top.

**Status legend**

- `DONE` — implementation and all applicable acceptance criteria are complete;
  the evidence columns record how the fix was characterized.
- `IMPLEMENTED` — code closed and host-tested; an *external* acceptance
  criterion remains (flight evidence, official CI, or hardware timing).
- `OPEN` — tracked, not started or intentionally deferred.
- `CLOSED` — resolved after this tracker was published; the entry moves to
  *Closed after publication* below and keeps its reasoning for reference.

## Findings

| ID | Finding | Status | Commit(s) | Test evidence | Flight evidence | Remaining |
|---|---|---|---|---|---|---|
| ADRC-001 | Liftoff gate open was not bumpless: first open loop fed the stale grounded-epoch `b0·lastOutput` into the ESO (~1.3 s oscillation, 89 % motor saturation on the pre-fix AIR log) | DONE | `1bdfffcef1`, `799ff89e60` | Regression test reproduces the discontinuity on baseline | Verified 2026-07-11: gate opened on takeoff with no transient (pre-fix log had 1.3 s oscillation at the same point) | — |
| ADRC-002 | Crash detection only ran inside `if (Kd > 0)` — ADRC with `d_roll/d_pitch = 0` silently lost crash detection incl. GPS Rescue | DONE | `1321ef4c1b` | ADRC + `D=0` enters crash recovery; GPS Rescue path covered | n/a (bench-provable) | — |
| ADRC-003 | Crash recovery zeroed `pidData.I`, but ADRC re-derived `I = −z3/b0` later in the same loop, restoring up to full `pidSumLimit` | DONE | `1321ef4c1b` | Full-loop-order test starting from saturated `z3` | n/a | — |
| ADRC-004 | TD used forward Euler — allowed loop-rate/cutoff combos diverge to Inf in ~48 ms; reset zeroed `vRef` | DONE | `62fe21523a` | Sweep over all allowed combos stays finite | n/a | — |
| ADRC-005 | ESO forward Euler unstable at allowed extremes (e.g. 200 Hz loop + `wo=600` → spectral radius > 2) | DONE | `62fe21523a` | Sweep 200 Hz–8 kHz; invariant `wo·dT ≤ 0.5` | n/a | — |
| ADRC-006 | Out-of-PR experimental D-term branch: a new persisted field was inserted mid-`adrcProfile_t` without a PG version bump — old blobs silently reinterpreted with shifted fields | IMPLEMENTED | `555f575a70` (+ D-term branch series) | PG14-blob rejection + PG round-trip tests; 3× reboot `diff all` 187/187 on real EEPROM | n/a | A dedicated ADRC parameter group is the preferred long-term layout; the field/layout finding does not affect PR #15400 |
| ADRC-007 | ESO feedback stored pre-mixer-normalization command — the normalization/attenuation difference accumulated into `z3` as fake disturbance | IMPLEMENTED | `c3311a0ba9`, `2e891d6f18`, `ab98b77127`, `72e47757e8` | Real-`mixTable()` tests: legacy/linear mixers, no-Airmode attenuation, yaw-spin limit | Superseded in part by ADRC-018 (see below) | `MIXER_DYNAMIC` per-motor redistribution intentionally left as lumped disturbance (documented) |
| ADRC-008 | Gate/`b0` scheduling read pre-override throttle — ALT_HOLD/GPS_RESCUE overrides invisible to ADRC | DONE | `c3311a0ba9`, `ab98b77127`, `1b19666f6c` | Real-`mixTable()` ALT_HOLD/GPS_RESCUE tests | n/a | — |
| ADRC-009 | State limits inconsistent with gyro FSR; corrupt `b0ThrottleScaleMax=0` → `0/0` NaN; finite-check optimizable away under `-ffast-math` | DONE | `62fe21523a` | High-FSR, zero/invalid `b0`, corrupt-scale tests; IEEE-754 exponent check | n/a | — |
| ADRC-010 | CLASSIC↔ADRC handover semantics undefined; tests implied an unsupported mid-air bumpless switch | DONE | `fc2b9cca4c` | Disarmed-switch test checks reset state, not a false mid-air promise | n/a | — |
| ADRC-011 | Gate re-arm tests were vacuous (`liftoffIdleHoldMs=0` disabled the very path under test) | DONE | `1bdfffcef1` | Mutation check: reverting cross-clamp/stillness cap breaks the tests | n/a | — |
| ADRC-012 | Coverage: full `pidController` path, mixer E2E, crash/GPS Rescue, loop-rate sweeps; F411 8 kHz cycle budget | IMPLEMENTED | `ab98b77127`, `72e47757e8`, `799ff89e60` | 63 host suites green with `-Werror`; F405/F411 size deltas recorded (+3280 B / +2624 B FLASH) | n/a | F411 8 kHz DWT cycle benchmark on real hardware — **NOT PROVEN, medium risk** |
| ADRC-013 | Integration: rebase onto master, official CI, release, structured re-flight | IMPLEMENTED | rebase series (`range-diff`-verified equivalent) | Local full test-all + clean target builds | Partial (see 017/018/019) | Official CI matrix needs maintainer approve-and-run; structured flight checklist below |
| ADRC-014 | Yaw-spin recovery zeroed visible I but left `z3` alive — exit kicked up to `pidSumLimit` | DONE | `ee9a153767` | Mutation reproduces the kick; regression in normal and `-ffast-math` matrix | n/a | — |
| ADRC-015 | Crash Flip: ESO could learn the turtle command and open the gate; auto-rearm entered flight with stale state | DONE | `7ade8d8089` | Crash-Flip loop reset tests | n/a | — |
| ADRC-016 | With `thrust_linear > 0` the mixer published inverse-compensated throttle — 40 % gate threshold effectively shifted to ~45 %, `b0` schedule underestimated thrust | DONE | `1b19666f6c` | Real mixer test with target-equivalent thrust formula 11/11; mutation breaks 10/11 | n/a | — |
| ADRC-017 | ESO state and liftoff gate survived disarm→arm (with default `pid_at_min_throttle=ON` the only reset branch was dead code); ground-wound `z3` up to the ±524k rail carried into the next arm | DONE | `04813845dc` | `testAdrcArmTransitionStartsFreshEpoch` fails pre-fix | **Verified in flight 2026-07-12** (second arm of the same power cycle starts gate-closed, `z3 ≈ 0`) | — |
| ADRC-018 | Remediation regression: feeding the ESO the authority-*scaled* command (`scale·u`) silently re-defined b0's calibration frame — loop over-gained by `1/scale` at low throttle → sustained 24–26 Hz roll/pitch limit cycle | IMPLEMENTED | `c718282ad6` | Characterization tests (unscaled-feedback expectations) fail pre-fix | **b4 verification flight (2026-07-14, byte-identical tune): the always-on over-gain did not reproduce** — one full 41 s b4 flight is baseline-clean (1.1 deg/s across the hover band ≈ pre-remediation 0.8, through punches and 670 deg/s flips), which no b3 log achieved. A mode-specific (acro vs air) A/B is *not* establishable — airmode state is not recoverable from these logs (switch-based, not in headers/flags). An *episodic* ring at the same 26 Hz remains in disturbance-rich low-collective states — tracked separately as ADRC-024 | ADRC-024 |
| ADRC-019 | b0 throttle schedule read the raw post-mixer collective: (1) mixer constrain tracks the loop's own axis activity → gain modulation at the resonance (`debug[7]` swinging 1.0↔2.8 at steady stick); (2) throttle chop collapsed the scale 3→1 in ~80 ms, faster than the ESO re-adapts → punch-chop rebound | IMPLEMENTED | `79f8b6041d` | Release-gradient and modulation-ripple characterization tests fail pre-fix | **b4 flight, split verdict**: (1) modulation FIXED — steady-window `debug[7]` swing p90 0.27–0.29 vs pre-fix 1.0↔2.8; (2) punch rebound NOT improved — post-chop pitch peaks: b4 per-log medians 45–97 deg/s (pooled 76, max 181) vs b3's 80 (max 95); the LPF alone is demonstrably not sufficient (though these flights can't fully exclude the release rate as a factor — no controlled A/B), and the rebound coincides with the z3 transient (consistent mechanism, causation not yet established) — tracked as ADRC-025 | ADRC-025 |

## Open items

### ADRC-021 — b0 throttle-curve identification (raised by @bvandevliet)

**Design note (2026-07-29) — post-flight hover suggestion, not an in-flight
learner.** `adrc_hover_throttle` is the schedule's anchor and the single most
common config trap so far (three testers in two weeks flew with hover set to
22 %, 50 %, and the default 35 against different actual hovers, silently
pinning or distorting the schedule). The measured hover is already cheap to
extract from any log: median post-mixer collective over calm-hover windows
(airborne, gate open, low setpoint/gyro variance, stable collective) — our
analysis scripts do exactly this. Proposal: surface that number to the pilot
*after* the flight ("measured hover ≈ 43 %, profile says 35 — update and
re-verify b0") via log analysis first, later possibly post-flight stats/OSD.
An **in-flight** hover learner is deliberately rejected for now: a moving
anchor is a moving loop gain — the same transient family as ADRC-025, only
self-induced. (Physics footnote for whenever this is revisited: the hover
*collective* is the constant-RPM point regardless of battery sag, so a
correctly tracked hover anchor would compensate sag for free — a static
percentage doesn't. The principled endgame remains measured b0(throttle)
identification below, which subsumes the hover+law construct entirely.)

**Field data (2026-07-30/31) — this estimator gets nothing from free flight,
and the sweep shows why the doublet protocol is needed.** Pavel_M. flew a
two-craft b0 sweep (3200 / 4800 / 6400 at wc 60, wo 100, two packs each,
13 sessions; data:
[`pr15400-pavel-part2/`](flight-test-analysis/pr15400-pavel-part2/)). Three
results bear on this item — all descriptive (free flights; manoeuvres and pack
state differ between sessions):

1. **Group medians move the same way on both crafts** — 20–80 Hz content falls
   with b0 throughout, and tracking error is clearly worse by 6400 on both
   (the Air65's 3200→4800 step is not worse). Sound follows the HF column and
   feel follows the tracking column, which reproduces the pilot's own reports
   ("6400 cleanest sound-wise, lower b0 flew better") with no contradiction
   between the crafts.
2. **Identical settings behave several-fold differently across crafts**: at
   b0 3200 on fresh packs the Air65 II shows 5.6× the Meteor75's 20–80 Hz
   gyro content while the motor-mean HF differs only ~1.3× — strong craft
   dependence, though one flight per craft with different IMUs cannot
   attribute the ratio between plant gain, mechanics and sensor path.
3. **No numeric b0 came out of these logs.** Regressing gyro_dot on pidSum
   inside the loop returns the controller's own b0 (proportional to the
   setting, coherence 0.9+) — an identity, not a measurement; the
   setpoint-as-instrument route got command-to-u coherence of only 0.29–0.46,
   and the few yaw bins passing 0.6 gave unphysical values (17–37). Doublets
   should supply the missing excitation; whether the estimator then returns a
   credible b0 has to be shown on the first doublet dataset.

Also observed there: the measured hover proxy correlates with pack voltage
across sessions (36–39 % at 3.71–3.90 V vs 45–50 % at 3.47–3.62 V, with the
schedule's applied multiplier moving 1.05 → 1.22 alongside) — consistent with
the physics footnote above, but confounded with b0 across those sessions and
not yet a within-pack measurement. The clean check is a start-of-pack vs
end-of-pack hover on one battery, tune unchanged.

**Field data (2026-08-01, part 3) — the complementary wc sweep; the
wc/wo-ratio folklore did not bind.** The same pilot then held b0
(6400 Air65 / 3200 Meteor) and wo (100) and swept wc 20/40/60 on both crafts
(13 sessions; data:
[`pr15400-pavel-part3/`](flight-test-analysis/pr15400-pavel-part3/)). wc
dominates the rankable measurements (roll/yaw tracking and event counts;
short-window pitch cells are too noisy to rank): at wc 20 flyability
collapses — roll/yaw tracking ≥ 100 % of the command sd in commanded windows
(the extreme 1298 % cell is a departure-dominated small-command-sd artifact,
not a standalone measurement), and 16 merged uncommanded high-rate events in
the clean wc-20 logs (12 Air65 + 4 Meteor, peaks to 735 dps, integrated
body-axis angles to 242° — matching the pilot's "90°+ rotations"; 2 more sit
in a crash record, counted separately) — while at wc 60 both crafts fly at
14–29 % (clean-log roll/yaw) with zero detector events outside the one
excluded crash tail. Three Meteor wc-40 events persist (peaks > 1000 dps);
the two biggest wc-40 departures begin after ≥ 100 ms of continuous
upper-rail saturation — at least one motor at the configured high rail in
every sample — and remain continuously saturated during the detected event,
with |I| railing during rather
than before (causal direction open), and 15 of the 16 clean-log wc-20 events
start unsaturated with the schedule multiplier locally steady (the one
exception chains off the biggest departure's recovery; mechanism open — an
earlier "schedule-transient" framing was withdrawn on re-inspection). The textbook
"wc = 20–30 % of wo" cap did not bind in these data (best-of-set at
wc/wo = 0.6 on both whoops; the Pavo20 flying at ≈ 0.8 with yaw at 1.9 as an
existence point) — which is not a universal refutation and does not
establish wc 80 as safe; the observed practical limits are saturation duty
and gyro-path noise. Same-tune day-to-day spread (Meteor wc 60 / 3200: roll
24–29 % here vs ~10 % in part 2) again says σ-ratio comparisons resolve only
large effects — the doublet protocol remains the instrument for the rest. In
flight-time terms: 8ksal8's in-flight b0_yaw sweep (32k → 24k at wc_yaw 300,
`pr15400-8ksal8-yawb0/` follow-up 2) is the cleanest one-knob field series
in this corpus so far — tracking error and σ-ratio fell together with flat
20–80 Hz content, in the `wc²/b0` direction (descriptive; PIDtoolbox agrees
at the endpoints).

The quadratic `(throttle/hover)²` law is capped at ×3 as a *safety bound*, not
a model. Classic TPA suggests the true plant-gain growth hover→full is more
like ×2–3 than the ×8+ the quadratic extrapolates to. To be settled as a
system-identification task on flight data, not by analogy:

- Candidates: fixed (scale=1), current quadratic+cap, linear+cap, fitted
  power/blended curve.
- Protocol: repeated identical roll/pitch doublets in several usable collective
  bins (approximately 25/35/50/65 %, classified afterward from the actual
  post-mixer collective), unchanged `wc/wo/b0`, and blackbox with
  `debug_mode=ADRC`. Exclude clipped, normalized, recovery, and other
  non-comparable samples from the curve fit; keep repeatable punch→chops as a
  separate transient check rather than identification data. Estimate the
  throttle-dependent effective plant gain from the lag-aligned relationship
  between applied axis excitation and angular acceleration. `z3` contains all
  lumped disturbances, not just b0 error, so use its correlation with the
  applied command as a cross-check rather than a direct b0 measurement. Fit a
  monotone curve across more than one 5″.

Status: **MEASURED (2026-07-16) — fix design pending.** The PR author flew the
doublet protocol on 2026-07-15 (10 flights, SPEEDYBEE F7 MINI V2, build
`35adbf14e6` = PR head + inactive-in-p1/p2 cascade commit); identification in
[`docs/flight-test-analysis/pr15400-doublets/`](flight-test-analysis/pr15400-doublets/)
(data, `identify_b0.py`, `fit_b0_law.py`, `ANALYSIS.md`). Measured, pooled
over 159 windows / 9 logs / both axes:

- **The quadratic law over-scales on this craft**: true plant-gain growth
  hover→40–60 % collective is ×1.3–1.7 (band-stable across analysis
  settings), vs the ×2.3–3 the shipped `clamp((c/hover)², 1, 3)` applies
  there; in law scoring on this corpus the shipped curve fits *worse than no
  schedule at all* (RMS log2 0.541 vs 0.512; the code-vs-fixed gap shrinks
  to +0.004 in the worst leave-one-log-out subset), with sqrt (0.425) and
  linear (0.453) best — the data reject the quadratic, they do not yet pick
  the production exponent.
- **Below hover the true gain falls** (~0.56× at 10–15 %) while the clamp
  holds the model at ×1 — `b0_eff` ≈1.6× too high there.
- **The ESO's own model residual is consistent** (qualitative cross-check on
  the same u/gyro/b0-law data, not an independent plant-gain estimate):
  z3-on-u regression is negative in every bin of every log checked — the
  sign of `b0_eff > b0_true` across the band, worst above 30 % collective.
- **Hover-band absolute b0 ≈ 2100–2300** (roll 2272 / pitch 2149, 1.5–25 Hz
  band) — flight-confirms the default 2000 and the converter's 2252–2328 on a
  second craft (feeds ADRC-022). Caveat: absolute values are band-dependent
  (plant closer to first-order in rate); the *relative* law is band-stable.

Fix candidates the data support: linear `c/h` or sqrt growth with a cap
around 1.7–2 (not 3), plus revisiting the below-hover clamp at 1.

**Second craft confirms (2026-07-16)**: the same estimator on jmsweng's two
b4 logs (DAKEFPVF405, 2300 kV, hover ≈ 31 %, 71 windows,
`fit_b0_jmsweng.py`) measures growth 20→55 % collective of only ×1.4; sqrt
scores best after pooling and *even a fixed b0 beats the shipped quadratic*
there (per-log winners differ: fixed on one log, linear on the other);
hover-band absolute ≈ 1800–2100 (his b0=2000 spot-on; the converter's
2252/2328 ~18–22 % above the direct estimate on this craft). The protocol's
"more than one 5″" requirement is met — sqrt and linear are the grounded
candidates for a controlled A/B; the corpus rejects the quadratic without
yet selecting the production exponent.

**A/B build published (2026-07-18)**: prebuilt release
[`adrc-pr15400-b5`](https://github.com/danusha2345/ADRC-betaflight/releases/tag/adrc-pr15400-b5)
= PR head `eda3bb16eb` + a fork-side per-PID-profile `adrc_b0_law` selector
(`QUADRATIC` default = b4 behavior / `SQRT` / `LINEAR` / `FIXED`), so one
flash A/Bs all candidates by switching profiles in the field; the active law
is recorded in the blackbox header. Kept out of the PR branch by agreement
with the PR author (the 4-bit PG version budget — this bump wraps 15 → 0;
the winning law ships upstream alone). Next: the controlled same-craft A/B
(same day, same packs, same maneuver script, randomized order if possible).

**A/B flown (2026-07-19)**: 12 b5 flights, one craft, all profiles at
defaults 60/100/2000, only the law differing (SQRT ×3 / QUADRATIC ×4 /
LINEAR ×4 / FIXED ×1 — the FIXED flight was **deliberately ditched at
12 s: unflyable** per the pilot, corroborated by telemetry — two
self-sustained 25.5 Hz episodes, tone RMS 58–59 deg/s roll with ~10 % of
samples at motor saturation at zero stick throttle, which answers the
null-control question qualitatively: no b0 schedule at all is unflyable on
this craft, so scheduling *does* help, the question is only its shape). Analysis in
[`docs/flight-test-analysis/pr15400-b5-b0law/`](flight-test-analysis/pr15400-b5-b0law/)
(data, `b5_ab.py`, `ANALYSIS.md`); the active law is verified from
telemetry (debug[7] applied-scale vs law prediction, every log). Pooled law
scoring over 559 windows — candidate-schedule shape vs the pooled
plant-gain estimates (plant is law-independent), not per-arm in-flight
accuracy: **sqrt 0.157 < linear 0.173 < fixed 0.186 < quadratic 0.253**
(RMS log-error); SQRT wins all 12 leave-one-flight-out refits and ~98 % of
flight-level bootstrap resamples; plant gain hover→40–60 % again grows only
×1.3. z3~u is flattest under SQRT, steepest under QUADRATIC. **But the law
choice interacts with ADRC-024**: the 26 Hz hover ring flares under SQRT
(29–41 % of hover-band windows vs 0–2 % QUADRATIC, 2–7 % LINEAR under the
b5 script's stricter gate; 41–58 / 3–12 / 8–15 % under the original
`ring_sensitivity.py` criterion — same ranking) — the accuracy-optimal law
removes the over-scaling that was suppressing the ring. Production read:
LINEAR is the compromise on current loop code; SQRT is right *if* the
margin hypothesis holds (see ADRC-024). Remaining: the decisive margin
experiment (the wc/wo 2×2 on SQRT, see ADRC-024); FIXED must not be re-flown on this craft.

**Bench cross-check (2026-08-03)**: @jmsweng measured static thrust vs
throttle on an Air65 over a kitchen scale (PR comment 5161126252). Analysis in
[`docs/flight-test-analysis/pr15400-jm-thrust-bench/`](flight-test-analysis/pr15400-jm-thrust-bench/).
The reading he drew from it inverts a transform: the mixer is additive in
command, so the static torque per unit control follows `dT/dcmd`, and a
*linear* thrust curve therefore argues for FIXED, not LINEAR. Differentiating
his own manufacturer sheet (Gemfan 1219s-3 / 0702-27000 kV) gives a slope
ratio above hover of ≈0.8–1.35 across every plausible hover normalisation
(25–35 %) — near FIXED, below SQRT, far below the quadratic — which points the
same way as the doublet identification here without being a second
identification of it. Scope limits that must travel with the number:
`dT/dcmd` is a *static roll/pitch proxy for schedule shape*, while this
implementation's `b0` is defined on `ω̈` (deg/s³ per PID output) and absorbs
actuator dynamics; yaw needs the reaction-torque slope `dQ/dcmd`, which a
scale cannot see; and the vendor grid's own slope scatters 1.44× over
30–100 %. The bench does not select a production exponent, and the b5 FIXED
result remains one craft at one parameter set — a demonstrated hazard there,
not a general verdict on exposing a selector.

### ADRC-022 — Conservative typical-5″ defaults (raised by @bvandevliet)

Explicit criterion going forward: defaults (`wc/wo/b0`, gate thresholds,
`adrc_b0_scale_max`) target a conservative point on a typical 5″ freestyle
quad — `pid_type = ADRC` must be a credible, safe drop-in, like classic PID's
stock tune. The current `60/100/2000` package is a *flight-validated starting
point* (two crafts), not a final default.

Status: OPEN — blocked on ADRC-021 and multi-craft evidence (≥3 typical 5″,
same maneuver set; accept: no narrowband limit cycle, low saturation,
acceptable overshoot/settling, no punch/chop rebound; pick from the lower,
calm part of the common stable region).

### ADRC-023 — Decouple P:D (and I:filter) ratio via damping-ratio parameters (raised by @bvandevliet)

Current `wc`/`wo` are Gao's standard bandwidth parameterization: each places a
*repeated* pole (`kp=wc², kd=2·wc` for the control law; `beta1=3wo, beta2=3wo²,
beta3=wo³` for the observer), which pins the ratio between the two virtual-PD
terms and between the observer's "I-like" (`z3`) and "D-filter-like" behavior
to a fixed, non-adjustable shape. Confirmed via the PID↔ADRC equivalence work
([`docs/pid-adrc-converter/pid_to_adrc.py`](pid-adrc-converter/pid_to_adrc.py), cross-checked
against arXiv:2501.11374 and `ActiveDisturbanceRejectionControl.jl`): classic
tunes with `Q = Ki·Kd/Kp²` outside `(0.25, 0.4)` — i.e. most real tunes,
including stock — have **no exact ADRC equivalent at any `(wc, wo, b0)`**,
because that band is exactly what a repeated-pole placement can reach. This
isn't a bug, it's the direct cost of collapsing 3 classic gains into fewer,
less-interacting knobs.

The lock is a parameterization choice, not a limit of ADRC/ESO as a
framework. Standard pole-placement extension: replace the single `wc` with a
natural frequency + damping ratio pair (`kp=ωn², kd=2·ζ·ωn`; `ζ=1` recovers
today's behavior exactly), and similarly for the observer. This would restore
independent P:D (and I:filter) shaping much closer to classic PID's feel,
at the cost of two more CLI fields and the associated tuning-complexity
increase ADRC's single-bandwidth-knob design was meant to avoid.

Proposed framing: an opt-in **"expert mode"** — extra `adrc_*_damping`-style
fields, hidden/defaulted to `1.0` (today's behavior) unless explicitly
touched, so the default 3-knob (`wc`/`wo`/`b0`) tuning experience for typical
pilots is completely unaffected. Not proposed as a change to the current PR
or its defaults.

Status: OPEN — future improvement, explicitly **not high priority**;
raised for later consideration, not blocking b4 or any item above.

### ADRC-024 — Episodic 26 Hz ring in disturbance-rich low-collective states (from the b4 flight)

The b4 verification flight (2026-07-14, byte-identical tune) confirmed the
ADRC-018 always-on over-gain not reproducing (one fully baseline-clean flight
at 1.1 deg/s across the hover band ≈ pre-remediation baseline; a mode-specific
claim is not possible — see the analysis), but a ring at the **same
24–27 Hz** (93–100 % of in-band RMS in a single tone,
present in `gyroUnfilt`) still **ignites on events** — gate open at takeoff
(up to 41 deg/s for ~3 s), propwash re-entry after a hard punch→chop, landing
approach — then self-sustains for seconds at 10–30 % throttle and decays. The
same flight is quiet for tens of seconds at the same stick positions between
ignitions; one of the four logs never rings at all despite punches and
670 deg/s flips. No obvious association with battery voltage or motor-floor
clipping (a window-medians comparison, not a formal correlation test).

Working hypotheses, in order: (1) **b0 under-calibration near/below hover on
this craft** (hover 22 % vs the 35 %-hover craft b0=2000 traces to →
≈2.5× standing authority gap → thin phase margin at 26 Hz that disturbance
kicks can push into a self-sustained cycle) — directly measured by ADRC-021;
(2) an airmode-specific low-collective feedback mismatch the binary
applied-signal doesn't capture — needs a code-path re-read plus replay
simulation against these logs; (3) pure phase-margin shortfall at `wc=60`
given `adrc_gyro_lpf 150` + craft latency — distinguished by the same
ADRC-021 data.

Status: OPEN — root cause unknown; the b0 story above is the *leading
hypothesis*, not an established cause. Data, methods and scripts:
[`docs/flight-test-analysis/pr15400-b4/`](flight-test-analysis/pr15400-b4/)
(the four `.bbl` originals, `ANALYSIS.md` with reproduction criteria, and the
analysis scripts). Primary discriminator: the ADRC-021 doublet flight.

**Suggestive discriminators (2026-07-16, `ring_sensitivity.py` in
[`pr15400-doublets/`](flight-test-analysis/pr15400-doublets/))**: at a fixed
b0 law the **wc 85 flight shows increased ring incidence and amplitude**
(11 % of hover-band windows, 5 episodes, tone to 39 deg/s vs the base
wc 60/wo 100's 2–9 %, 2 episodes per log, 20–33 deg/s). The short wo 150
flight (19 usable windows) contains no strong ring — one threshold-level
window, 5.4 deg/s — but is too short to establish an incidence reduction;
the wc≈37 converted tune shows one weak window per log. Consistent with a
loop/observer phase-margin hypothesis (and with jmsweng's independent
"wc ≈ 40 quiets it"), **not yet a causal discriminator** — flights were not
randomized or maneuver-controlled. The b0 over-scale measured in ADRC-021
remains the gain-scheduling backdrop; separating margin-only from margin+b0
needs a controlled A/B (or at minimum a re-fly of the ring band after a
b0-law fix). Cross-craft: jmsweng's hover band shows no sustained 24–27 Hz
ring (one suggestive post-power-loop window at 24 Hz); his gyroUnfilt
carries a strong high-frequency line that is a plausible mechanical/
motor-band candidate for what he hears, though its link to the audible
oscillation is unproven (no audio sync; aliasing at his 988 Hz log rate).

**Law-controlled measurement (2026-07-19,
[`pr15400-b5-b0law/`](flight-test-analysis/pr15400-b5-b0law/))**: with
wc/wo/b0 fixed at defaults and only `adrc_b0_law` varying, ring incidence in
hover-band windows is **29–41 % under SQRT (all three flights, 25–26 Hz),
2–7 % under LINEAR, 0–2 % under QUADRATIC** (b5 script's
stricter window gate; 41–58 / 8–15 / 3–12 % under the committed
`ring_sensitivity.py` criterion — same ranking; method delta documented in
the b5 ANALYSIS.md); ring windows sit at 24–26 % collective, just above
hover, where quadratic applies ×1.2–1.4 b0 — a ~17–29 % direct-path gain
cut vs scale 1 (~12–25 % vs sqrt's ≈×1.05; b0 also enters the ESO
feedback, so the full-loop figure is approximate). That modest gain
difference flips the mode. **Measured**: the b0 law controls the ring
incidence on this craft, and the quadratic's over-scaling (the ADRC-021
defect) was suppressing it. **Leading hypothesis** (consistent with the
wc-85-worsens observation above, not yet established): a marginally-damped
~26 Hz mode short on loop margin; the decisive discriminator is the
**wc/wo 2×2 on SQRT** agreed with the PR author (2026-07-19): p1 = 60/100
baseline, p2 = 45/100, p3 = 60/150, p4 = 45/150, one b5 flash, same
maneuver script per profile. It separates the two margin levers the
existing evidence conflates (the quiet converted tune is low-wc *and*
high-wo at once; the lone wo-150 flight was too short): wc-gain story →
p2/p4 quiet; observer-lag story (mode 26 Hz ≈ 163 rad/s sits *above* the
wo = 100 observer poles, so the ESO contributes phase lag there) → p3/p4
quiet; additive → only p4; all-ring → mechanism isn't (just) margin. Fix space if it holds: loop/observer margin at
~26 Hz (wc shaping; the fork's `adrc-dterm-lpf` z2-LPF is a separate
untested candidate) rather than retaining the inaccurate law as an
implicit gain cut. **The FIXED arm completes the dose-response**: the
pilot ditched it at 12 s as unflyable — telemetry shows the same mode at
25.5 Hz, tone RMS 58–59 deg/s with ~10 % motor saturation at zero stick
throttle. Ring *incidence* is monotone in scheduling strength
(SQRT > LINEAR > QUADRATIC under both window criteria; FIXED consistent);
episode *amplitudes* overlap between arms once motor-floor windows are
counted (`flight_screen.py` in the b5 dir: sustained calm-stick tones
reach 70 deg/s under SQRT at ~28 % stick, 25–40 under LINEAR/QUADRATIC;
b5_ab.py's gated "worst tone" column understates amplitude because the
all-motors-above-floor gate drops the deepest ring windows — incidence
comparisons are unaffected). FIXED is unique not by amplitude but by
**uncommanded thrust**: zero-stick mean-motor p90 = 993 vs ≤ 469 in every
other flight — strong same-craft support for the gain-sensitivity of the
mode, still short of proving the margin mechanism.

**Second craft (2026-07-20, jmsweng DAKEFPV,
[`pr15400-jm-b0sweep/`](flight-test-analysis/pr15400-jm-b0sweep/))**: a
second-craft ADRC-024-like **22 Hz** instability observed at
wc = 40 / wo = 100 / b0 = 1000 (band RMS ~40 deg/s in the 0.46 s of gate-open
takeoff transient before a disarm); similarity of mechanism and established
airborne-hover reproduction remain unconfirmed. At b0 ≥ 2000 the same craft's
calm-stick 18–32 Hz tone sits at 1–5 deg/s and falls to a flat ~1 deg/s floor
by b0 ≈ 3000–4000 with no high-b0 rebound in calm windows (1–3 windows per
arm — point estimates). His four-law hover A/B from the same day is
**effectively degenerate** (`adrc_hover_throttle = 35` vs actual ~28 % hover
→ the never-below-1× clamp held three arms at exactly ×1.00 and LINEAR at
≤×1.03 for 0.27 s), so it neither confirms nor refutes the law/ring
inversion cross-craft.

**Law A/B redo (2026-07-21, same dir, `btfl_lawab2.bbl` + `jm_lawab2.py`)**:
re-flown with `adrc_hover_throttle = 28` and deliberate above-hover
excursions — the arms genuinely separated this time (`debug[7]` max ×2.4–3.0
QUAD / ×1.3–1.6 SQRT / ×1.9–3.0 LINEAR / ×1.00 FIXED). Calm-stick ring
episodes (overlapping 1 s windows, strict setpoint gate, 18–32 Hz band RMS
> 10 dps): **FIXED 6 episodes across both its logs (worst 25.6 dps
@ 23 Hz), QUADRATIC 1 takeoff episode, SQRT and LINEAR none**. Repeated
ring occurred only under FIXED — an **association, not proof the schedule
is the mechanism**: one FIXED episode sits entirely below the 28 % hover
reference where every law applies ×1.00, and the QUADRATIC episode is also
below hover. The SPEEDYBEE's SQRT ≫ LINEAR > QUADRATIC inversion does
**not** reproduce on the DAKEFPV; cross-craft agreement is at the extreme
only (the unscheduled arm is worst on both — consistent with the
gain-sensitivity dose-response); the fine ordering among scheduled laws is
craft-dependent. Caveats: not randomized, 2–3 short hovers per arm. The
wc/wo 2×2 above remains the decisive experiment.

**wc/wo 2×2 flown (2026-07-22,
[`pr15400-b5-wcwo2x2/`](flight-test-analysis/pr15400-b5-wcwo2x2/)) — the
experiment half-failed, informatively.** Both wo = 150 arms never reached
the air: a ~28.3–28.8 Hz idle oscillation on the ground false-triggered the
gyro-only liftoff detector within 0.1–0.4 s of arming (gate open at **0 %
stick throttle**), the ESO wound up against ground contact and the motors
ran to saturation — the pilot's "almost instant fly-aways" (see ADRC-026;
**do not re-fly wo = 150** on this craft without a mitigation). So the
observer-lag lever is untested in the air. The wc lever *was* tested:
45/100 vs 60/100 leaves ring incidence, episode count, 27 Hz tone and peak
amplitude essentially unchanged (10/39 windows worst 33.9 dps at wc 60 vs
14/81 / 13/64 worst 27.8/30.8 dps across two wc 45 flights). Under the
pre-registered predictions this lands in the **"neither lever" branch**
(with the wo half untestable): plain wc reduction is de-prioritized as the
ADRC-024 fix, and the structural observer-path candidates (the fork's
`adrc-dterm-lpf` z2-LPF branch; observer redesign) move to the front.
Cross-craft note: jmsweng's ICM42688 crafts hover all laws where this
BMI270/MPU6000-target craft rings — an IMU/craft-difference hypothesis is
on the table (his planned same-frame BMI270 A/B addresses it), unproven
from logs.

**Independent same-frame IMU swap (2026-07-29, pilot report only)**:
a new tester (Pavel_M., experienced across 3.5″–13″ on
multiple ADRC implementations) reports swapping two BetaFPV whoop AIO
boards — one ICM426xx ("ICM42622P" per his message), one BMI270 — on the
same craft, and that the gyro difference "seems to impact the ADRC wo
ceiling". This preliminary swap is directly relevant to the discriminating
experiment planned above, but the report does not establish same-frame
tune/filter parity, direction, `wo` numbers or paired logs. Mechanistic
prior: at high wo the observer can track the gyro's noise floor and latency,
so the IMU and its internal filtering may set the wall.
Same tester independently converged on SQRT ("cleanest logs") after
trying all four laws on b5, on a correctly set hover (35 vs actual
35–40 %) — and still reports throttle-transition excursions
(pitch nose-dips, ~45° yaw), consistent with ADRC-025 rather than the
hover config trap; the requested logs were pending.

**Follow-up (2026-07-30, data:
[`pr15400-pavel-whoops-20260730/`](flight-test-analysis/pr15400-pavel-whoops-20260730/))**:
the uploaded Air65/Meteor75 logs do **not** contain the reported same-frame
IMU swap. They identify different targets (`BETAFPVG473` and
`BETAFPVG473_V2`), but each target supports multiple IMU drivers and the
Blackbox header does not record the detected chip. Pavel later identified
the Meteor board as ICM42622P; this remains pilot-reported metadata, and no
paired BMI270 log is present. Thus the ICM42622P↔BMI270 direction and `wo`
ceiling remain unmeasured. The logs also show no ADRC-024-like calm narrow
line: zero strict calm-window 10–100 Hz tones above 5 dps/tone fraction 0.5.
Their dominant unwanted motion is instead a much slower 0.5–1.3 Hz
pitch/yaw family; see ADRC-025 below.

**2026-07-28 (8ksal8 hand tune,
[`pr15400-8ksal8-hoteltune/`](flight-test-analysis/pr15400-8ksal8-hoteltune/))**:
with SQRT + matched hover (29) and wo 138–165, calm-stick ring is nearly
absent across four windy flights — 3 genuine narrow-line windows total
(11–13 dps @ 20–25 Hz; a fourth flagged window was a wind skirt, peak/floor
7.6×) out of 571 calm windows, flights 2–4 fully clean including full-
throttle. Same frequency family as the 24–27 Hz mode; consistent with the
tune-dependence picture, adds no mechanism discrimination. The follow-up
retune (wc 125 / wo 160 / b0 4000/3000/7000,
[`pr15400-8ksal8-wc125/`](flight-test-analysis/pr15400-8ksal8-wc125/)) in
much heavier wind (gusts to 23 mph) shows 4 narrow lines / 264 windows at
18–23 Hz, ~11 dps — slightly higher incidence, lower frequency, still
nothing self-sustained; raising wc to 125 did not open a margin problem
on this craft.

### ADRC-026 — Ground-constrained excitation can false-open the liftoff gate and drive zero-throttle z3 windup/runaway (from the 2×2 flights)

At wo = 150 (SQRT, b0 = 2000, wc 45 or 60) the craft oscillates at
~28.5 Hz on the ground at idle throttle, exceeding
`adrc_liftoff_gyro_dps = 20` for the 25 ms hold within 0.1–0.4 s of arming.
The gate then opens **with the craft on the ground at 0 % stick throttle**,
the ESO integrates ground-contact dynamics it cannot model, z3 winds up and
the motors run up to saturation (6–24 % of samples at 2047) — an
uncommanded thrust runaway on the ground. Three of five wo = 150 arms show
exactly this signature; the other two were disarmed before the detector
fired. Data: [`pr15400-b5-wcwo2x2/`](flight-test-analysis/pr15400-b5-wcwo2x2/).

Status: OPEN. The defect is the liftoff detector's gyro-only path treating
a self-induced idle oscillation as liftoff — any sufficiently-unstable tune
can arm-and-runaway without the pilot ever raising throttle. Candidate
mitigations (deliberately not implemented while the code is frozen for
A/B continuity): require a minimum throttle floor alongside the gyro
condition; band-reject 15–40 Hz content in the liftoff gyro test; or gate
z3 accumulation until throttle exceeds idle. Safety guidance meanwhile:
treat "motors audibly oscillating at idle after arming" as an immediate
disarm, and do not fly high-wo profiles.

**Trigger set is broader than self-oscillation (2026-07-28 pilot report,
unlogged)**: 8ksal8, armed on a table in 15–23 mph gusts (wc 125 / wo 160 /
SQRT tune), reports "the quad jumped off the table when trying to
stabilize itself in some turbulent wind" — wind rocking is an external
gyro source that satisfies the same gyro-only liftoff test (> 20 dps for
25 ms is indistinguishable from a toss launch by design), so the gate can
open on the bench with a perfectly stable tune. The airmode activation
latch does not prevent it: with `pid_at_min_throttle = ON` (default) the
mixer applies corrections at idle regardless. No blackbox exists (flash
full), so this stays a pilot report — but it matches the mechanism
exactly and strengthens the case for the minimum-throttle-floor
mitigation over the band-reject one (wind is not band-limited).

**First logged in-event captures (2026-07-29, indoor, no wind — data:
[`pr15400-8ksal8-armbounce/`](flight-test-analysis/pr15400-8ksal8-armbounce/))**:
arming with the ANGLE box + airmode produces a repeated ground bounce
("like a basketball") — gate open, 0 % stick throttle, collective slamming
to ~48 %, motor-saturation bursts to 2047, gyro to 1945 dps, and crucially
a **non-zero setpoint (up to 446 dps) from the ANGLE leveling loop**: tilt
→ leveling demands rate → idle-throttle motor response → jump → new tilt,
with the grounded ESO amplifying (z3 ±300k). Stock BF has a milder known
angle+airmode arm-jump; the ADRC-specific share needs a same-craft classic
A/B. The airmode-only arm from the same session is the first **logged slow
windup that self-limits**: gate open on a quiet craft (setpoint 0, gyro
5–13 dps), z3-yaw ramps to +437k and motors creep to 42 % of range at zero
throttle, then the `adrc_sigma_decay` leak (0.3/s) bleeds it back over
~8 s and the eventual takeoff is clean. Both halves of the mechanism story
are now on tape: an open gate does wind against ground contact, and the
runaway occurs only when the fight outpaces the leak (joint loop gain —
this craft's b0 4000/3500/10000 stays under; the 2×2's b0 2000 did not).
Interim guidance strengthened: **arm in acro (ANGLE box off) on ADRC
profiles** — the leveling loop is a standing ground-excitation source.

**Single-arm CLASSIC comparison flown (2026-07-30, same dir) — supports an
ADRC-specific path, but does not yet quantify its share.** Same craft and
bottom-battery tilt; the first 0.25 s starts with essentially identical
ANGLE demand (123/124/123 dps). CLASSIC + permanent feature-airmode has no
motor at the 2047 rail and settles 0.46 s after the first saved frame;
ADRC + permanent feature-airmode bounces, with a motor at 2047 in 60.9 %
of the first 0.25 s and z3 reaching the debug clip. At zero throttle before
Airmode throttle-activation, CLASSIC runs `pidResetIterm()` every loop,
whereas `adrcZeroThrottleItermReset()` (pid.c:1123) clears only published
`pidData.I` and leaves the ESO/z3 state alive. In the ADRC recording the
gate is already open and roll z3 is already clipped from the first saved
frame, so the trigger and build-up are not captured. Once open, the gate
selects the 0.3/s airborne z3 decay rather than the 20/s gated decay while
`-beta3 * errorEso` continues integrating: a concrete code path consistent
with the bounce, not single-run causal proof.

The control run is itself discordant: CLASSIC with box-airmode (pilot
reports it active at arm) also bounces at 928 dps although feature and box
Airmode collapse to the same runtime boolean. There is one arm per
condition, BOXAIRMODE state is not logged, and raw headers include minor
per-log differences beyond the persistent `FEATURE_AIRMODE` bit. **Candidate
mitigation:** while `zeroThrottleItermReset` is active, retain ground-rate
z3 decay or inhibit its growth even if the gate opens. This is analogous
in intent to CLASSIC protection, not equivalent to an every-loop reset,
and needs repeated-arm plus patched/unpatched ADRC A/B validation.

**Fourth logged capture (2026-08-01, 8ksal8's ground b0_yaw sweep — data:
[`pr15400-8ksal8-yawb0/`](flight-test-analysis/pr15400-8ksal8-yawb0/),
follow-up section): the trigger crossed by *lowering b0*, at wo 160.** During
a deliberate armed-on-the-ground yaw-b0 sweep (ANGLE on, 0 % stick throttle,
`wc 125/130/300`, `wo 160/160/160`), the b0_yaw = 20000 arm false-opened the
gate 0.775 s in and kept it open for 69.2 % of the record: |gyro| to 128 dps,
a motor driven to 1122 of the 198–2047 range (≈ 50 % of span), yaw z3 at the
debug clip 26.2 % of the post-open record, disarm 1.74 s after the open. Not a
full rail runaway, but a clean false-liftoff + ground windup capture — at the
lowest wo recorded for this failure (160, vs 150 in the 2×2 and 160 with wind
in the bench report). The same sweep brackets the trigger: 24k and 32k arms
briefly touch 21 dps without satisfying the 25 ms hold, and all nine
ascending-b0 arms (36k → 65535) stay ≤ 17 dps with the gate closed — i.e. the
output's 1/b0 scaling means *lowering* b0 raises the grounded loop gain until
idle excitation crosses the gyro test. This is the most direct evidence yet
for the joint-loop-gain threshold reading above (wo, wc, b0 jointly — there is
no safe "wo below X" line), and it strengthens the minimum-throttle-floor
mitigation over the band-reject one for the same reason as the wind report.

*Pilot confirmation and outcome (2026-08-02, PR comment 5157640545):* the
pilot reports the 20k arm "just popped to a hover about an inch or two …
off the ground and stayed there till disarm" — i.e. the capture reached
**uncommanded flight**, not just windup: motors transiently at 820–1122 with
motor-mean collective p90 15 % / max 24 %, enough for a guarded whoop in
strong ground effect, and the outcome was self-limited (a low hover, not an
escalation to the rail). A plausible mechanism for the self-limiting — z3
winds while the grounded plant does not respond, lift-off restores a
responding plant and the windup stops — remains a hypothesis: the log has no
altitude channel and the z3 inflection is not resolvable from the clipped
trace. The self-limited outcome in ANGLE does not blunt the hazard (entry
into uncommanded flight at 0 % throttle); the high-wo captures show
oscillatory, non-parking versions of the same entry.

**Fifth logged gyro-path open at 0 % throttle, plus small grounded margin at
the flying tune (2026-08-02, same source, `Getting_close.zip` follow-up-2
section):** in `btfl_052` the *arm transient itself* (a 26.4 ms **roll** run
to 56 dps, exceeding the 25 ms hold, at b0_yaw 32k) opened the gate at 0 %
stick throttle 0.12 s into the log. It did not develop into a recorded
ground incident before the commanded lift-off ~1.5 s later; the
zero-throttle false-open itself was still unsafe. Notable because it was
roll-driven: the exposure is not purely a b0_yaw property. In the armed grounded segments of the other three
sessions the peak grounded yaw |gyro| was 35 / 38 / 43 dps at b0_yaw
28k / 26k / 24k (one arm per setting — a small and, in these arms, shrinking
amplitude margin, not an established monotone law), with 29–83 separate
>20 dps crossings per arm, each under 7.6 ms. At the pilot's current flying
tune the 20 dps amplitude threshold is crossed routinely and **only the
25 ms hold keeps the gate closed** — the margin is hold-limited, not
amplitude-limited, and lower b0 raises the grounded loop gain (1/b0), i.e.
the false-open risk. Any mitigation that touches `adrc_liftoff_hold_ms`
must treat it as the active guard in this regime, not a formality.

**An open latch alone does not produce the runaway (2026-07-29, logged)**:
8ksal8's Wind flight (`pr15400-8ksal8-hoteltune/`, flight 3) begins with a
"Logging resume" event (blackbox on a switch, `logIteration = 48640`) and
the gate **already open at 0 % stick throttle on the ground**, z3 already
non-zero (yaw +141k, roll −85k in debug units) — yet through ~7 recorded
seconds of quiet ground idle (worst-axis 15–40 Hz RMS 0.53 dps) the motors
held near idle with only small differential corrections. The runaway
requires *ongoing* excitation against the ground constraint (wind rocking,
self-oscillation) while the gate is open, not merely an open latch. The
moment and cause of the gate opening fall in the unrecorded interval.

**Threshold is a joint loop-gain property, cross-craft support**: every
ADRC output term scales as 1/b0 in the b5 code, so at fixed wc/wo,
b0 = 2000 carries twice the command gain of b0 = 4000. 8ksal8's five
ground segments at wo 160–165 / b0 3500–4000 are quiet (worst-axis
15–40 Hz RMS 0.5–1.6 dps across full pre-liftoff intervals) where the 2×2
craft at wo 150 / b0 2000 self-oscillated at 28.5 Hz into saturation —
consistent with the ADRC-026 threshold being set by (wo, wc, b0) jointly
plus craft/ground-contact mechanics. Cross-craft with several variables
changed at once: support, not proof; no same-craft b0-only A/B exists.
Tuning-workflow corollary (the thread's "find the wo wall at high b0,
lower b0 last" procedure): lowering b0 at the end raises loop gain and
invalidates the wo margin measured earlier — re-check margin after the
final b0, and don't hunt the absolute wo wall at all until this defect
has a mitigation.

### ADRC-025 — Punch→chop rebound persists after the release-LPF fix (from the b4 flight)

Calm-stick post-chop pitch peaks (deg/s; table produced by
[`analyze_b4_punches.py`](flight-test-analysis/pr15400-b4/analyze_b4_punches.py)):
pre-remediation median 152 (2 events, max 171) → b3 "ACRO2" median 80
(5 events, max 95) → b4 per-log medians 97/80.5/45 (9 events pooled: median
76, max 181 on an 87 % punch) — the ADRC-019 release LPF smoothed the
`debug[7]` trajectory but produced **no measurable rebound improvement**.
That shows the LPF alone is not sufficient; it does not fully exclude the
release rate as a contributing factor (no controlled same-maneuver A/B).
During every punch the b0 scale still traverses its full 3.00→1.00 range;
z3P hits the ±524k debug rail in two of three flight logs (0.20 % and 1.50 %
of whole-log samples; the third peaks at ~478k without railing). The rebound
**coincides with** the z3 transient — the thrust-collapse pitch moment plus
the observer re-learning after adapting under a ×3-inflated gain frame — a
consistent mechanism, but correlation, not established causation.
Candidates: the b0 law itself (ADRC-021), and/or an explicit
throttle-transition feed-forward (the "anti-gravity analog" the PR author
asked about), and/or **carrying z3 across schedule-multiplier changes**
(design note 2026-07-29): z3's meaning in the output is `z3 / (b0·scale)`,
so when the multiplier moves, the stored disturbance estimate is applied
in a gain frame it wasn't learned in — the re-learning transient *is* the
rebound. Rescaling z3 by `scale_new / scale_old` at each multiplier update
would carry the estimate across the frame change instead of forcing a
re-learn. Cheap to implement and testable offline by replaying logged
punch→chop episodes; interacts with the z3 anti-windup bound (already
`pidSumLimit · b0_eff`, so the bound moves with the scale consistently).
Untested — a candidate, not a fix.

Status: OPEN — blocked on ADRC-021 (the b0 law determines how much of the
transient is model error vs physics). 2026-07-15 flights re-confirm
(`punches_20260715.py`): 18 pooled base-tune events, calm-stick peak-pitch
median 60 / max 135 deg/s, scaling with punch height; one of the larger
punches (79 %, 127 deg/s rebound) reaches the ±524k *debug telemetry clip*
on z3-pitch — neither the highest-throttle nor the max-rebound event does,
and the clip is not the ESO's internal clamp, so the true z3 magnitude there
is unknown. Converted tune shows the same (79–102 deg/s at 45–54 % punches).
ADRC-021 is now measured — a law fix plus re-measure is the cheapest next
discriminator; the z3-saturation link remains correlation, not established
cause. **2026-07-19 b5 A/B adds the law dimension**: calm punch→chop
rebounds — SQRT median 51 / max 114 (n=10), LINEAR 58 / 111 (n=17),
QUADRATIC 71 / 145 (n=11) deg/s — direction consistent with less
high-collective over-scaling leaving a smaller stored observer error at the
chop, not yet conclusive at these n.

**2026-07-25 FIXED/LINEAR pair (data:
[`pr15400-jm-fixedlinear/`](flight-test-analysis/pr15400-jm-fixedlinear/))**:
identical tune (40/100/2000, hover 28 — matching the craft, so this is the
first dataset with a schedule confirmed live: LINEAR's multiplier ran med
1.71, hit the ×3.0 cap), only the law differing. FIXED rings at 24 Hz
(41.4 dps, one episode at ~61 % collective, where LINEAR would command
scale ≈ 2.2 vs FIXED's 1.00 — a ~2× over-gain, same frequency family as
ADRC-024); LINEAR is clean (0/19 ring windows) despite higher median
collective. Supports upward-scheduling *direction*; still bracket-level
(one unbalanced pair, wind, damaged props), does not identify the law shape.

**2026-07-28 first live SQRT data (data:
[`pr15400-8ksal8-hoteltune/`](flight-test-analysis/pr15400-8ksal8-hoteltune/))**:
four flights on the second craft with `adrc_hover_throttle = 29` finally
matching the craft (previous 8ksal8 logs had hover 50 → multiplier pinned
×1.00). The SQRT multiplier tracked the theoretical bound
√(collective/hover) to <2 % in every flight (max ×1.83 at full throttle),
with no ring at high collective (full-throttle flight 0/58 windows) and no
stalls. The schedule mechanism is now field-confirmed under both SQRT and
LINEAR; the law-shape question (ADRC-021 doublets) remains open.

**2026-07-29 (pilot report, Discord)**: a third independent
tester (Air65 II whoop, hover correctly set at 35 vs actual 35–40 %,
settled on SQRT after trying all four laws — "cleanest logs") still
reports throttle-transition excursions (nose-dips, ~45° yaw swings).
With the hover trap excluded, this is a clean ADRC-025 candidate case;
see also the z3 carry-across-schedule design note under ADRC-025's
candidates.

**Logs received 2026-07-30 (data:
[`pr15400-pavel-whoops-20260730/`](flight-test-analysis/pr15400-pavel-whoops-20260730/))**:
the transition component is real. Air65 `.02` repeatedly reaches
62–96 dps pitch with pitch setpoint ≈0 around 16–28-point throttle moves;
one event integrates to ≈21° in the 15 Hz low-pass trace. Meteor `.02`
shows pitch/yaw errors to 100/154 dps while scale traverses ×1.00→×1.32.
Measured hover is close to the configured anchor (Air65 36–39 vs 35,
Meteor 38–44 vs 40), so this is not the known hover-setting trap.

But multiplier transitions are **not a complete explanation**. Meteor
also carries long 0.5–1.3 Hz uncommanded pitch/yaw series at nearly constant
throttle and scale (e.g. `.01` t=47.4–52.4 s, scale ×1.00–1.06; `.02`
t=112–117.5 s, ×1.24–1.28), with large lagging I/z3 movement. Wind/external
torque is not separable from a self-excited observer response in these
uncontrolled flights, so this proves only that the z3 carry-across candidate
cannot explain every excursion. Also, the Meteor attachment is mislabeled:
despite `tune_60_100_4000` in its filename and post, raw headers contain
wc 30 / wo 120, b0 **6400 then 4800**; no b0=4000 session is present.
Pavel later confirmed that the intended dump was uploaded but the older
30/120-120-100 profile had been selected accidentally.

### ADRC-027 — Inverted "sticking" in flips: rate collapse after entry overshoot (two crafts)

A recurring pilot report ("the quad sticks upside-down mid-flip") now has a
measured signature on two different crafts:

- **Air65 II, 2026-07-25** (video-synced by the pilot; data:
  [`pr15400-jm-air65/`](flight-test-analysis/pr15400-jm-air65/)): full-
  collective flip entry **overshoots 2.5×** (gyro −1428 dps vs −582
  commanded), z3-pitch dives to the −524k debug rail braking it, then the
  rotation **collapses to −99 dps median against −433 commanded for
  356 ms** — the visible inverted hang — while z3-pitch swings rail-to-rail
  (≥1 M range in 0.2 s), motor 1 rides 2047 for 78 % of the stall and the
  LINEAR b0 multiplier holds ×2.35.
- **5″ law session, 2026-07-23**: same signature at t≈34.9 s of the linear
  log — z3-pitch pinned at the debug rail ~96 ms during a reported sticking
  episode.

Not gravity: gravity acts through the CG and produces no torque about it, so
a rate loop (and z3) cannot see it directly — which also explains the "never
on yaw" observation, since yaw is simply not commanded in these events.

Status: OPEN. Three co-occurring candidate mechanisms — z3 observer
transient (ADRC-025 family), differential-authority saturation at full
collective, and the b0 schedule's ×2.3+ output cut — none separable from
these flights. Discriminating test: the same flip at ~60 % throttle
(scale ≈ 1.7, no saturation), and FIXED vs LINEAR at matched throttle.

**A concrete, testable mechanism proposal (2026-07-30, @jmsweng)**: setting
`adrc_hover_throttle` **above** the craft's real hover collective reproduces
the sticking, and clearing it removes it. He replicated the effect on his
rebuilt Air65 by raising the anchor a few points above the measured hover,
and his earlier sticking logs had the anchor left at the default 35. The
mechanism is available in code: the anchor is the b0 schedule's reference,
so an anchor above the true hover keeps the multiplier clamped at ×1.00
through most of the usable throttle band, i.e. the loop runs at un-scaled
gain exactly where the schedule was meant to raise it. It also predicts the
side effect he reports — take-off much faster than PID and a hover that is
hard to hold.

@8ksal8's 2026-07-31 control run (`adrc_hover_throttle = 35`, no sticking) is
a **weak control, not a refutation**. The measured hover collective in that
flight reads 34.6 % — but from only 24 heavily-overlapping calm windows in an
aggressive flight (p10–p90 spread 28.1–40.0 %), on a sagging pack (10.56 V in
the calm windows versus 11.78 V in his `btfl_041`). Taken at face value the
anchor was matched to within +0.4 points rather than sitting above the hover,
i.e. the run most likely never created the offset the hypothesis needs — but
that offset estimate is too noisy to assert. Data and per-log offsets:
[`pr15400-8ksal8-yawb0/`](flight-test-analysis/pr15400-8ksal8-yawb0/). The
discriminating run on that craft: two equally-charged **fresh** packs
(measured hover 28–30 %), anchor 29 versus 34–35, everything else unchanged —
the same few-points offset the original report described.

Related, from [`pr15400-pavel-part2/`](flight-test-analysis/pr15400-pavel-part2/):
across that sweep's sessions the measured hover proxy correlates with pack
voltage (36–39 % fresh vs 45–50 % sagged; confounded with b0 and not yet a
within-pack measurement). If a start-vs-end-of-pack check confirms it, the
offset this finding turns on is not a constant over a pack.

Not universal: the 2026-07-28 8ksal8 flights (SQRT, hover matched,
including intentional inverted holds — data:
[`pr15400-8ksal8-hoteltune/`](flight-test-analysis/pr15400-8ksal8-hoteltune/))
show no stall window even under a loose scan (≥150 ms, |setpoint| > 100,
gyro < 40 % of it) across four flights; a hang read off that pilot's video
at ~1:46 was an intentional inverted stop per the pilot, and the logs
agree.

## Closed after publication

Items that were open when this tracker was first published and have since been
resolved. Kept here (rather than deleted) because the reasoning is referenced
from the PR thread and the wiki guide.

### ADRC-020 — Ground/air re-arm semantics (raised by @bvandevliet)

The opt-in mid-air gate re-arm (`adrc_liftoff_idle_hold_ms`, default 0) still
cannot strictly distinguish a landing from a calm mid-air float using
throttle+gyro alone. Accelerometer magnitude is the natural discriminator
(measured: 0.99 g on ground vs 0.1–0.5 g in the float windows that
false-triggered the old always-on re-arm), but it is not strict either
(steady aerodynamic descent approaches 1 g) and adds `USE_ACC`/vibration/craft
dependence.

Options on the table:

- **(a) Remove the opt-in re-arm from the initial PR entirely.** After
  ADRC-017 every arm starts a fresh epoch, so ground re-tries are simply
  disarm→arm; the in-flight heuristic carries risk with no validated use case.
  Fewer params, less surface for upstream review. *(Preferred.)*
- **(b) Keep it off-by-default and add a sustained `|acc| ≈ 1 g` condition**,
  gated on independent flight evidence across the existing logs first.

Status: **CLOSED — implemented upstream by the PR author** right after the b4
verification flight: `eda3bb16eb` "fix(adrc): remove unreliable mid-air
liftoff-gate re-arm (ADRC-020)" (2026-07-14, −279 lines incl. the
`adrc_liftoff_idle_*` params and their tests). The b4 flight logs predate this
commit (built from `08ad602ce`), which is immaterial — the re-arm was
off-by-default there.

Removing the `adrc_liftoff_idle_*` fields shifts the `adrcProfile_t` layout,
so the same commit bumps `PG_PID_PROFILE` 14 → 15: flashing any build from
`eda3bb16eb` onward over a b2–b4 install **resets PID profiles to defaults** —
`diff all` first. Build lineage for bisection reference: b1 = PG 12,
b2–b4 = PG 14, PR head `eda3bb16eb` = PG 15, and the fork-side **b5 = PG 0**
(verified against `src/main/flight/pid.c` at each release tag). The b5 wrap
back to 0 is deliberate, not a typo: the PG version is a 4-bit field, so 15 was
already the maximum and b5's own `adrc_b0_law` layout change had nowhere to
count up to — wrapping to 0 still differs from the stored 15 and therefore
still forces the profile reset. Every b5 flash over b2–b4 or over the PR head
resets PID profiles too.

## How to help test

Flight-test reports from experienced pilots are welcome, especially on typical
5″ freestyle builds. Use
[`adrc-pr15400-b5`](https://github.com/danusha2345/ADRC-betaflight/releases/tag/adrc-pr15400-b5)
(PR head `eda3bb16eb` plus the fork-side `adrc_b0_law` A/B selector) for
anything touching the b0 throttle law, or
[`adrc-pr15400-b4`](https://github.com/danusha2345/ADRC-betaflight/releases/tag/adrc-pr15400-b4)
(PR head `79f8b6041d`) when continuing an earlier comparison series — and keep
the tune unchanged within any one comparison run. Note both flashes reset the
PID profiles (see the PG lineage under ADRC-020 above): `diff all` first.

> **Ground-safety warning before you raise `adrc_wo` (ADRC-026).** The liftoff
> gate's gyro-only path (`adrc_liftoff_gyro_dps = 20` sustained for
> `adrc_liftoff_hold_ms = 25`) cannot tell a self-induced idle oscillation from
> a real takeoff. At `wo = 150` the craft oscillated at ~28.5 Hz on the ground
> at idle and opened the gate **on the ground at 0 % stick throttle** within
> 0.1–0.4 s of arming, after which z3 wound up and the motors ran to saturation
> — an uncommanded thrust runaway with the pilot's throttle still down. Treat
> "motors audibly oscillating at idle right after arming" as an immediate
> disarm, arm props-off first when trying a higher `wo`, and do not fly
> high-`wo` profiles until ADRC-026 is fixed.

> **Reading your own logs — mode flags are mislabeled by the current
> Blackbox Explorer release.** Firmware 2026.6.0 added the AUTOPILOT box,
> shifting every later box bit by one; the viewer's table was fixed in
> betaflight/blackbox-log-viewer#904 (2026-04-08) but the latest release
> (2025.12.1) predates it. Until a new viewer release: the flag shown as
> "AIRMODE" is really your BLACKBOX switch, and "3D" is really AIRMODE.
> Details in `pr15400-8ksal8-hoteltune/ANALYSIS.md`.

The b4 regression re-flight happened on 2026-07-14 (verdicts recorded in
ADRC-018/019/024/025 above). The immediate priority is now the **ADRC-021
system-identification protocol**: repeated identical roll/pitch doublets in
collective bins around 25/35/50/65 %, unchanged tune, `debug_mode = ADRC` —
plus, as separate checks, controlled punch→chops and hover passes at
10–30 % throttle. Please attach or link
the Blackbox log in [PR #15400](https://github.com/betaflight/betaflight/pull/15400)
with the craft/target, exact firmware tag, `diff all`, flight mode, prop and
battery setup, and timestamps for the relevant manoeuvres. ADRC remains
experimental and opt-in; use conservative conditions and leave safety margin.

## External acceptance criteria still pending

- Official upstream CI matrix on the current head (needs maintainer
  approve-and-run for collaborator pushes).
- ~~b4 re-fly (same tune)~~ — **happened 2026-07-14**; split outcome recorded
  in ADRC-018/019 (always-on over-gain and d7 modulation gone; episodic ring
  → ADRC-024, punch rebound → ADRC-025; the zero-throttle drop report is
  consistent with the logs — flight mode itself is not log-verifiable).
- ADRC-021 doublet flight (now the primary pending flight evidence).
- F411 8 kHz DWT cycle benchmark on real hardware (ADRC-012).

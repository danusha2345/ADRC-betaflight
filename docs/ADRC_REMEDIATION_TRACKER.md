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
| ADRC-018 | Remediation regression: feeding the ESO the authority-*scaled* command (`scale·u`) silently re-defined b0's calibration frame — loop over-gained by `1/scale` at low throttle → sustained 24–26 Hz roll/pitch limit cycle | IMPLEMENTED | `c718282ad6` | Characterization tests (unscaled-feedback expectations) fail pre-fix | Root-caused from a byte-identical-tune flight A/B (header diff = `vbatref` only) + closed-loop sim reproducing direction and ~25 Hz; **fix awaits the b4 re-fly** | b4 flight confirmation |
| ADRC-019 | b0 throttle schedule read the raw post-mixer collective: (1) mixer constrain tracks the loop's own axis activity → gain modulation at the resonance (`debug[7]` swinging 1.0↔2.8 at steady stick); (2) throttle chop collapsed the scale 3→1 in ~80 ms, faster than the ESO re-adapts → punch-chop rebound | IMPLEMENTED | `79f8b6041d` | Release-gradient and modulation-ripple characterization tests fail pre-fix | Same A/B evidence; rebound already halved by the earlier ×3 cap (132–180 → 80–95 deg/s) | b4 flight confirmation |

## Open items

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

Status: OPEN — decision pending with the PR author.

### ADRC-021 — b0 throttle-curve identification (raised by @bvandevliet)

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

Status: OPEN — blocked on the b4 re-fly (regression must be confirmed gone
first so the data is clean).

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
([`tools/adrc/pid_to_adrc.py`](../tools/adrc/pid_to_adrc.py), cross-checked
against arXiv:2501.11374 and `ActiveDisturbanceRejectionControl.jl`): classic
tunes with `Q = Ki·Kd/Kp²` outside `(0.25, 0.4]` — i.e. most real tunes,
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

## How to help test

Flight-test reports from experienced pilots are welcome, especially on typical
5″ freestyle builds. Please use the
[`adrc-pr15400-b4`](https://github.com/danusha2345/ADRC-betaflight/releases/tag/adrc-pr15400-b4)
pre-release (based on PR head `79f8b6041d`) and keep the tune unchanged for
comparison runs.

The immediate priority is the b4 regression re-flight: check the 10–30 %
throttle acro band for the former 24–26 Hz oscillation, repeat controlled
punch→chops, and include an AIR-mode zero-throttle drop. Please attach or link
the Blackbox log in [PR #15400](https://github.com/betaflight/betaflight/pull/15400)
with the craft/target, exact firmware tag, `diff all`, flight mode, prop and
battery setup, and timestamps for the relevant manoeuvres. ADRC remains
experimental and opt-in; use conservative conditions and leave safety margin.

## External acceptance criteria still pending

- Official upstream CI matrix on the current head (needs maintainer
  approve-and-run for collaborator pushes).
- b4 re-fly (same tune): 10–30 % throttle acro band calm again, punch→chops
  without rebound, AIR-mode zero-throttle drop.
- F411 8 kHz DWT cycle benchmark on real hardware (ADRC-012).

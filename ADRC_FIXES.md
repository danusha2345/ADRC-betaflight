# ADRC robustness fixes — call for flight testers

**English** | [Русский](ADRC_FIXES.ru.md)

This fork adds a series of **small, independent** robustness fixes on top of
[`Boyyt357/ADRC-betaflight`](https://github.com/Boyyt357/ADRC-betaflight). They came out of a
line-by-line review of the ADRC implementation in `src/main/flight/pid.c` against ADRC/LADRC
theory. The math core (LESO + virtual PD + disturbance compensation, Gao 2003 bandwidth
parameterization) is faithful; these fixes target the **robustness seam** where ADRC meets the
legacy Betaflight plumbing.

> ⚠️ **All of these are UNTESTED on real hardware.** I do not have a craft to fly them on.
> Each fix is a **separate commit**, so you can build with or without any of them
> (`git revert <sha>` to drop one). **Please flight-test and report in the issues.**

## What to report
- Craft (size, weight, motors/props, FC target), and your ADRC P/I/D (wc/wo/b0) values.
- Which commits you built with (or "all").
- Behavior: arm/spool-up, hover, hard maneuvers, prop wash, wind, recovery after throttle
  chops / desync, any oscillation or motor heating.
- Blackbox log if possible.

## The commits

| Fix | Commit subject | What it changes | Risk |
| :-- | :-- | :-- | :-- |
| #3 defaults | `re-derive default P/I/D as ADRC bandwidths` | Default P/I/D were unconverted stock PID ints (wo/wc≈1.78); now wc=10, wo=110, b0=100 (yaw wo=80) per the proven 5" tune, with an explicit yaw b0. | Low (defaults only) |
| #1 anti-windup | `add anti-windup clamp on the ESO disturbance estimate z3` | Bounds z3 so the disturbance term `z3/b0` stays within the per-axis pidsum limit; prevents lag in recovery after motor saturation. | Medium |
| #2 observer feedback | `feed the ESO the saturation-limited command` | The ESO `b0*u` term now uses the pidsum clamped to the per-axis limit (what the plant can actually apply) instead of the raw pre-saturation pidsum. | Medium |
| #4 zero-throttle | `keep the ESO running at zero throttle` | At zero throttle (no airmode) the observer was reset every loop; now it keeps integrating and only the legacy I accumulator is cleared, so the disturbance estimate survives spool-up. Genuine disarm/overflow still fully resets. | Medium |
| #5 core-only feedback | `EXPERIMENTAL — feed ESO only the ADRC core (exclude F/S)` | Feeds the observer only P+I+D, excluding feedforward F and S-term (which aren't /b0). **Reverted on master 2026-07-02** after the hardware A/B below showed #2 flies the same or slightly better — the default build is now the #2 behavior. To try #5 anyway: `git cherry-pick 0d43645`. | High / uncertain |
| #6 gain ceiling | `raise the PID gain ceiling to the uint8_t max (255)` | The System-Gain (D → b0) input was capped at 250 by the legacy `PID_GAIN_MAX`; on fast motors the tune can need more. Raised to 255 (the hard uint8_t ceiling). Only widens the allowed range — no behavior change at existing values. Going above 255 would need a wider field (breaks MSP/blackbox). | Low (range only) |
| #7a anti-gravity | `EXPERIMENTAL — disable anti-gravity P-boost under ADRC` | Anti-gravity (on by default) multiplies the roll/pitch P-term during throttle transients — a legacy PID heuristic. ADRC already rejects throttle-sag torque via the observer (z3), so the boost just adds a transient overshoot at spool-up/takeoff (a likely extra cause of the takeoff bounce). Boost still logged for study; revert to A/B. | High / uncertain |
| #7b observer log | `add DEBUG_ADRC blackbox logging of the ESO states` | New `debug_mode = ADRC`: logs the observer states so testers can actually see them — roll z1/z2/z3 (debug 0–2), pitch z1/z2/z3 (3–5), yaw z3 (6), pitch b0 (7, sign-tagged by the fix #8 liftoff latch: positive = airborne, negative = gated). Diagnostic only, no flight-behavior change. | None (logging) |
| #9 b0 multiplier | `add adrc_b0_scale — per-craft System-Gain multiplier` | New CLI setting: `set adrc_b0_scale = N` (1–100, default 10) makes **b0 = D × N**. Set once per craft; day-to-day tuning stays in the ordinary D cell of the Configurator. Solves the whoop case where D maxes out at 250 (with the default ×10 the ceiling is b0 = 2550; a whoop can set scale 20–40 and keep D mid-range). ⚠️ When reporting tunes, state the scale too — the same D means different b0 on different crafts. | Low (default unchanged) |
| #8 liftoff gate | `EXPERIMENTAL — gate the ESO b0·u feed until liftoff` | Blackbox analysis of real takeoffs (see below) showed the residual bounce = z3 winding toward −b0·u while the craft is still ground-constrained (on the ground the plant does not respond to the command, i.e. effective b0 ≈ 0). Until liftoff is detected — throttle ≥ 40%, or any-axis rotation > 20 deg/s sustained 25 ms (a toss launch opens it almost instantly) — the observer's b0·u term is zeroed, so z3 stays ≈ 0 on the ground *by construction*. Latched until disarm, so in-flight throttle chops keep the full observer. Known limitation: a re-takeoff without disarming is not re-gated (same as pre-#8 behavior). | High / uncertain |

## How to build with/without a fix
```
git log --oneline          # find the commit SHAs
git revert <sha>           # drop one fix (creates a revert commit)
# then build as usual: make <TARGET>   (see README "Compiling ADRC-Betaflight")
```

## Known real-world feedback (as of July 2026)

Real-flight evidence for the ADRC-Betaflight fork is currently very thin (the fork is only days old). Collected here so the picture stays honest:

**Flights of this fork**
- **Author demo** — Boyyt357, YouTube *Engineering Robotic*, [BLTQN-Gw7LE](https://www.youtube.com/watch?v=BLTQN-Gw7LE): a 10" quad flown with uncalibrated params (P10/I50/D20) and a water-bottle payload swinging off one arm. Proof-of-concept; per comments the clip reportedly ends in a crash.
- **One independent pilot — jmsweng** ([PR #1](https://github.com/Boyyt357/ADRC-betaflight/pull/1)): flew a 5" quad carrying an unstable load (~40% of AUW), toss-launched with PID off at min throttle, params 10/110/100. The only third-party flight found.
- **Negative hands-on report** — YouTube commenter @captain-ulitka: on a normal build the controller "barely resists external influences" and oscillates when the gains are raised. Worth watching for during testing.
- **Update (2026-06-30, [issue #1](https://github.com/danusha2345/ADRC-betaflight/issues/1)) — jmsweng** ran more flights on a 5" (640 g, DAKEFPVF405, 4S, 2300 kV) and reported a **strong positive disturbance-rejection result**: a leaf-blower and a stick strike mid-air did not meaningfully destabilize it, and it flew with 20–40% of AUW offset on one motor arm. He also derived the step-by-step **tuning procedure** now in the README (ending at 40/160/200). Open question he surfaced: the rate **ESO doesn't model gravity**, so throttle-up shows a brief sub-second bounce/oscillation before it settles — a likely cause of the "unpredictable on arm" reports, and a candidate that fixes **#4 (keep ESO at zero throttle)** and **#1 (anti-windup)** may affect. (Caveat: his tests were on the original code with a damaged motor; re-test pending.)
- **✅ Hardware validation (2026-07-01, [issue #1](https://github.com/danusha2345/ADRC-betaflight/issues/1)) — jmsweng** A/B-tested this fork against the original firmware on his 5" (640 g, DAKEFPVF405, 4S, now 1750 kV, params 40/160/250) with **blackbox logs**:
  - **The takeoff bounce is fixed.** The original firmware still bounces/shakes at takeoff even after a motor swap; builds with **fix #2 or fix #5 take off cleanly**. Blackbox confirms fewer start-up oscillations with either fix, and **fix #2 damps out faster** → fix #2 is the recommended baseline; fix #5 (EXPERIMENTAL) flew nearly identically and *maybe* slightly worse under a hanging load, so it stays optional.
  - **Disturbance rejection confirmed hands-on:** he could set the quad down and balance it on a single motor and it stayed stable (⚠️ he cut himself doing this — do not attempt near a spinning 5").
  - **Chattering at the gain ceiling:** at D=250 (b0=2500) he still heard occasional chatter, and lowering the gain made it worse. He hit the old 250 cap wanting ~263 for the faster motors. Fix **#6** raises the ceiling to 255; beyond that the real lever is re-tuning observer bandwidth (I/wo) / gyro filtering for the new motor vibration, not more gain.
  - Zero-throttle "sticks at the last attitude it touched down at" — expected side effect of keeping the ESO alive (fix #4); jmsweng considers it a harmless ADRC quirk.
- **✈️ Airfield tests (2026-07-01, [issue #1](https://github.com/danusha2345/ADRC-betaflight/issues/1)) — jmsweng**, now on the full fix stack including **#7a** (anti-gravity off), re-tuned to **30/100/200** on the 1750 kV setup. Verdict: *"In its current state, this method seems to be superior to PID control."*
  - **Wind rejection felt in flight:** the quad noticeably did not drift when the wind picked up (consistent with the earlier leaf-blower test).
  - **~20% AUW hung off motor 4:** flyable but "handles like crap"; blackbox shows motor 4 pinned at max output for a large share of the flight — a **thrust-ceiling limit, not a control limit**.
  - **Prop-damage tolerance:** a crash severely bent two props → flew back normally, only the noise gave it away. He then **cut one blade off** prop 2 (plus two bent blades on prop 3) and it *still* flew acceptably, until vibration loosened the arm screws and ejected the arm.
  - Residual takeoff oscillations are still visible in blackbox even with #7a, but no longer visible/audible in person. He keeps #7a: anti-gravity duplicates what the observer already does.
  - He also proposed picking tunes **quantitatively** from the variance of the takeoff/hover blackbox traces — plots of the same maneuver under different tunes separate clearly.
- **🔬 Maintainer blackbox analysis (2026-07-02)** of the logs above (charts in [`docs/flight-test-analysis/`](docs/flight-test-analysis/)):
  - **The takeoff bounce tracks z3 windup on the ground.** In the four-tune takeoff A/B, tunes where pitch z3 (the I-term) wound up to ~+65…+90 during spool-up bounced (pitch tracking-error RMS 13–19 deg/s in the first airborne second); tunes where z3 stayed ≈0 took off clean (RMS 3–5 deg/s). Single-run data, but it localizes the mechanism: while the craft is ground-constrained the ESO mis-attributes thrust to a phantom disturbance, which then has to unwind at liftoff. → strongest candidate for the next fix: ground-transient handling of z3 (gate or slew-limit it until liftoff is detected).
  - **Load flight:** motor 4 at ≥99% output ~12% of the flight — confirms the power-limit reading.
  - **Prop-damage flight:** unfiltered-gyro vibration PSD ~20× the intact-prop flight across the band, whole-flight tracking-error RMS ~3.7× higher — and still controllable. A strong disturbance-rejection data point.

**No wider traction yet:** no Reddit / RCGroups / IntoFPV / blog threads on this fork, and the official Betaflight project has zero ADRC mentions (issues/PRs/discussions).

**Broader ADRC on multirotors (not this fork, research)** — genuine real flights that favor ADRC for disturbance rejection, but always with *tuned* ADRC on research rigs:
- Lv et al., *Sensors* 2024 — LADRC quad autonomously landing on a moving USV; landing accuracy ~0.057 m vs ~0.11 m for PID. [PMC10935343](https://pmc.ncbi.nlm.nih.gov/articles/PMC10935343/)
- Michalski et al., ICUAS 2023 — ADRC vs PID position control on a Crazyflie 2.1 (OptiTrack mocap), real indoor flights. [IEEE 10156505](https://ieeexplore.ieee.org/document/10156505/)

**Reality check on "no tuning":** ADRC for quads has many parameters, and a whole research subfield exists just to auto-tune them (GA/PSO/Kriging); PID still covers ~90–97% of UAV applications. ADRC is a capable disturbance-rejection approach, but "PID killer / no tuning" is marketing, not an established field result. This is exactly why these fixes ship **with a call for testers** rather than as proven defaults.

## Background
The full theory-vs-implementation review (what matches canonical LADRC, what is a deliberate
simplification, what deviates, and the robustness concerns these commits address) lives outside
the firmware tree in the maintainer's notes; the short version of each concern is in the commit
messages. Questions and results → **open an issue**.

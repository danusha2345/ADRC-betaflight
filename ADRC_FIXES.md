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
| #5 core-only feedback | `EXPERIMENTAL — feed ESO only the ADRC core (exclude F/S)` | Feeds the observer only P+I+D, excluding feedforward F and S-term (which aren't /b0). **Debatable** — F/S are applied to the plant too. Revert this single commit to restore #2 behavior; fly both back-to-back. | High / uncertain |

## How to build with/without a fix
```
git log --oneline          # find the commit SHAs
git revert <sha>           # drop one fix (creates a revert commit)
# then build as usual: make <TARGET>   (see README "Compiling ADRC-Betaflight")
```

## Known real-world feedback (as of June 2026)

Real-flight evidence for the ADRC-Betaflight fork is currently very thin (the fork is only days old). Collected here so the picture stays honest:

**Flights of this fork**
- **Author demo** — Boyyt357, YouTube *Engineering Robotic*, [BLTQN-Gw7LE](https://www.youtube.com/watch?v=BLTQN-Gw7LE): a 10" quad flown with uncalibrated params (P10/I50/D20) and a water-bottle payload swinging off one arm. Proof-of-concept; per comments the clip reportedly ends in a crash.
- **One independent pilot — jmsweng** ([PR #1](https://github.com/Boyyt357/ADRC-betaflight/pull/1)): flew a 5" quad carrying an unstable load (~40% of AUW), toss-launched with PID off at min throttle, params 10/110/100. The only third-party flight found.
- **Negative hands-on report** — YouTube commenter @captain-ulitka: on a normal build the controller "barely resists external influences" and oscillates when the gains are raised. Worth watching for during testing.

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

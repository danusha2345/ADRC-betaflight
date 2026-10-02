# ADRC — experimental tester firmware based on betaflight/betaflight#15400

⚠️ **Experimental. Bench-test before flying. Use at your own risk.**

## mp2 — mp1 plus Betaflight's chirp, and corrected τ guidance

Identical flight code to mp1. Two changes:

- **Chirp is back.** It is a build option (`USE_CHIRP`) that the Betaflight cloud builder adds and mp1 did not;
  mp2 builds every target with it, except where it does not fit — **STM32F722 boards** (ITCM RAM is full) are
  built without it and listed in the release's build summary.
- **τ guidance corrected.** mp1's notes suggested 8–12 ms on whoops. That was wrong for at least one: a chirp on
  a Pavo20 Pro II measured τ ≈ 33 ms on roll and 27 ms on pitch, and 12 ms on it cut the modelled phase margin
  from ~45° to ~21°. **Measure τ with a chirp** (the plant-fit tool, or ask in #15400), and if you must guess,
  guess high: a τ above the real one only gives part of the benefit, a τ below it costs margin.

The line underneath (PR line adrc-toggle 1eabcb3877 + master afe6a86dc5, plus ADRC-036):

- **`adrc_motor_tau_ms`** (0–100, default **0 = exactly the current law**, bit-identical). Set it to your craft's
  motor time constant in ms and the observer carries the motor pole itself instead of learning it as a
  disturbance; the D gain becomes `2·wc − 1/τ` (floored at `0.5·wc`). Roll and pitch only; yaw keeps the plain law.
  Why: docs/ADRC_MATH_REVIEW.md — the plain law overshoots rate steps by ~10 % at the flown wo·τ ≈ 1–2, the
  model says the pole removes that at the cost of 8–15° of phase margin. **This is what the build is for: A/B
  the same craft with `adrc_motor_tau_ms = 0` and with your τ, same tune otherwise, log both with
  `debug_mode = ADRC`.** The header line `adrc_motor_tau_ms` tells which one a log was flown with.
- Where τ comes from: a chirp fit — 21 ms on 8ksal8's 2.5" (US25), 27–33 ms on a Pavo20 Pro II. Too large a τ
  is the safe side (part of the benefit, no harm in the model); too small cuts the D gain more than the plant needs.
- **`adrc_td_hz` is gone** (a PT1 on the setpoint, never validated); `adrc_motor_tau_ms` takes its profile slot,
  so **profiles load unchanged, the PG version stays 15** and a b11/PR-line `diff all` pastes back as is.

Debug mode: `debug_mode = ADRC` is **111** on this line (upstream's indices preserved), not 102 — set it again
after flashing from b11.

Not built: **NEXUSXR** (STM32F722) — its ITCM RAM overflows on the upstream base itself.

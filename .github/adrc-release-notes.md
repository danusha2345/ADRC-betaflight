# ADRC — experimental tester firmware based on betaflight/betaflight#15400

⚠️ **Experimental. Bench-test before flying. Use at your own risk.**

## mp1 — the PR line (adrc-toggle head 1eabcb3877 + master afe6a86dc5) plus the motor pole in the observer

Same code as #15400 after bvandevliet/betaflight#4, with one addition (ADRC-036) and one removal:

- **`adrc_motor_tau_ms`** (0–100, default **0 = exactly the current law**, bit-identical). Set it to your craft's
  motor time constant in ms and the observer carries the motor pole itself instead of learning it as a
  disturbance; the D gain becomes `2·wc − 1/τ` (floored at `0.5·wc`). Roll and pitch only; yaw keeps the plain law.
  Why: docs/ADRC_MATH_REVIEW.md — the plain law overshoots rate steps by ~10 % at the flown wo·τ ≈ 1–2, the
  model says the pole removes that at the cost of 8–15° of phase margin. **This is what the build is for: A/B
  the same craft with `adrc_motor_tau_ms = 0` and with your τ, same tune otherwise, log both with
  `debug_mode = ADRC`.** The header line `adrc_motor_tau_ms` tells which one a log was flown with.
- Where τ comes from: a chirp fit (21 ms on 8ksal8's 2.5"; the plant-fit tool will report it), or start from
  15–20 ms on 2.5"–5" and 8–12 ms on whoops and compare. Too large a τ is the safe side (half the benefit, no
  harm in the model); too small cuts the D gain more than the plant needs.
- **`adrc_td_hz` is gone** (a PT1 on the setpoint, never validated); `adrc_motor_tau_ms` takes its profile slot,
  so **profiles load unchanged, the PG version stays 15** and a b11/PR-line `diff all` pastes back as is.

Debug mode: `debug_mode = ADRC` is **111** on this line (upstream's indices preserved), not 102 — set it again
after flashing from b11.

Not built: **NEXUSXR** (STM32F722) — its ITCM RAM overflows on the upstream base itself.

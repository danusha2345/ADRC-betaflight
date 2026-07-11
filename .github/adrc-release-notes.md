# ADRC — prebuilt hex of upstream PR betaflight/betaflight#15400

⚠️ **Experimental. Bench-test before flying. Use at your own risk.**

## What's new in b3

- **Rebased onto current Betaflight master** (`6ecfb45f93`).
- **Full remediation round** (17 tracked findings, each with characterization
  tests): bumpless liftoff-gate open (fixes the takeoff oscillation bout seen
  in the first airmode log), crash recovery decoupled from classic D, stable
  TD/ESO discretization at every supported loop rate, finite-value defenses
  that survive `-ffast-math`, the observer now fed the actually-applied mixer
  output (normalization, saturation, ALT_HOLD/GPS_RESCUE overrides,
  thrust-linearization domain), clean yaw-spin/Crash Flip state handling.
- **Fresh ADRC epoch on every arm** (ADRC-017): the liftoff gate and
  disturbance estimate no longer survive disarm into the next arm cycle
  (flight-reproduced on b2-era code: a post-landing z3 windup entered the
  next arm with the gate already open).
- **Settings survive from b2**: the profile layout and PG version are
  unchanged, so upgrading b2 → b3 keeps your tune (still: `diff all` backup
  first). Upgrading from b1 resets profiles — see below.
- **STM32F446 builds don't include ADRC**: that MCU's 512k flash is full with
  the default feature set. F446-based boards get a working classic-PID build;
  `set pid_type = ADRC` won't exist there. All other targets are unaffected.

## Upgrading from b1

The first freestyle blackbox on this branch exposed two tuning-default problems, both
fixed here (see the PR discussion for the full log analysis):

- **Mid-air gate re-arm is now off by default** (`adrc_liftoff_idle_hold_ms = 0`): the
  old landing heuristic false-triggered on smooth zero-throttle floats, dumping the
  disturbance estimate mid-air — the reason airmode felt broken on b1. Airmode is fine
  again on this build.
- **`adrc_b0_scale_max` default 9 → 3**: the throttle-scaled b0 over-weakened the
  controller on throttle punches (huge uncommanded pitch excursions with motors
  nowhere near saturation).

Because keeping the old stored values would silently re-create both problems, the
profile version was bumped: **your PID profiles reset to defaults on first boot of
this build** — `diff all` before flashing and re-apply your tune after.

These are ready-to-flash builds of the **upstream ADRC pull request**
[betaflight/betaflight#15400](https://github.com/betaflight/betaflight/pull/15400)
(opt-in `pid_type = ADRC` per PID profile, classic PID untouched by default), so you
don't have to wait on the Configurator cloud build — or fight it when it queues or
errors out. The exact source commit is in the release tag description; the same code
can also be cloud-built by entering `#15400` in the Configurator's *Select commit*
field (visible only when the `2026.6.0-alpha` version is selected in the dropdown).

## Which file do I flash?

Same convention as official Betaflight releases:

- **Your board has its own hex** (`betaflight_2026.6.0-alpha_<BOARDNAME>.hex`) — use it.
- **Board not listed?** Use the **generic hex for your MCU** (`STM32F7X2` for any F722,
  `STM32F405`, `STM32H743`, `AT32F435M/G`, …) and accept *Apply custom defaults* on
  first connect.

Flash via Configurator → Firmware Flasher → **Load Firmware [Local]**.

## Enabling ADRC

ADRC is **off by default** — the firmware flies classic PID until you opt in:

```
set pid_type = ADRC
save
```

Starting tunables (flight-validated on two 5" and a 65 mm whoop; see the
[tuning guide](https://github.com/danusha2345/ADRC-betaflight#tuning)):
`adrc_wc_* = 60`, `adrc_wo_* = 100` (yaw 80), `adrc_b0_* = 2000` (5") — whoops need
roughly `33/65/3200`. Set `debug_mode = ADRC` and enable blackbox if you can — logs
are the most valuable thing you can send.

## Where to report

Flight reports, logs and issues: [danusha2345/ADRC-betaflight#2](https://github.com/danusha2345/ADRC-betaflight/issues/2)
(or directly on the PR). Both good and bad results help.

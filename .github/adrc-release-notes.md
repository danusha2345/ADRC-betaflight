# ADRC — prebuilt hex of upstream PR betaflight/betaflight#15400

⚠️ **Experimental. Bench-test before flying. Use at your own risk.**

## What's new in b6

- **The liftoff gate now reads the *commanded* collective, not the applied one**
  (ADRC-026). This is the whole reason b6 exists. The gate's throttle test used to
  read the collective *after* the mixer added airmode headroom — so a craft that
  starts oscillating while armed raises its own applied collective, that raised
  value crosses `adrc_liftoff_throttle`, and the gate opens with the throttle stick
  still down. `mixer.c` now publishes the collective twice: the applied value as
  before (the b0 schedule keeps using it — "how much thrust is there") and a new
  commanded value sampled between the automatic-mode overrides and
  `applyMixerAdjustment()`, which the gate uses instead ("was thrust commanded").
  Because the sample sits after the ALT_HOLD/GPS_RESCUE overrides, an autonomous
  climb still opens the gate with the stick at zero.
- **z3 can no longer grow while the gate is closed and the craft is idle** —
  scoped to *ungated AND idle* specifically so the airborne zero-throttle float
  case (ADRC-020) cannot come back.
- **Measured evidence this addresses.** Re-decoding the `wo = 150` ground arms
  showed every gate opening explained by the throttle test reading airmode-raised
  collective at a zero stick, not by the gyro branch. The clearest single recording
  is @8ksal8's `LOG008` on b5: at the transition the throttle stick is at **8.2 %**
  (and never exceeds 23.3 % anywhere in that log) against
  `adrc_liftoff_throttle = 40`, while the applied-collective proxy climbs to 42.9 %
  in the 4.7 ms before the gate opens. In that same log the gyro branch is ruled
  out numerically: the longest run above `adrc_liftoff_gyro_dps` is ~4.1 ms of
  firmware time against the 25 ms `adrc_liftoff_hold_ms` requires.
- **Your PID profiles survive the upgrade from b5.** The stored profile layout is
  byte-identical to b5, including `adrc_b0_law`, so b5 tunes carry over unchanged.
  (Coming from b1–b4, the b5 reset still applies — see below.)
- **Known trade-off:** a toss launch thrown at literally zero throttle no longer
  opens the gate on rotation alone; it opens as soon as throttle comes up, through
  either branch.

### What b6 does *not* fix

This build is **host-tested only** — 63/63 unit suites pass, including three ADRC
suites, but nothing here has been flown. The bench repro → limited props-on arm →
patched/unpatched A/B chain is still open, and the arming-into-oscillation guidance
stands: if the motors run away as you arm, disarm immediately.

It also does not touch loop timing. One tester's log showed the PID loop running at
about half its configured rate (748 µs against a 375 µs target) with an external
serial logger enabled; since `pidRuntime.dT` is a constant, the observer's effective
bandwidth halves while the controller gains do not. The scheduler and gyro sources
are identical between b5 and b6 — that question is open and separate.

## What's new in b5

- **`adrc_b0_law` — A/B selector for the throttle→b0 schedule** (ADRC-021,
  fork-side only, will not go upstream): flight logs from two crafts measured
  the shipped quadratic `(throttle/hover)²` law applying ×2.3–3 where the
  plant gain only grows ×1.3–1.7; the data reject the quadratic but cannot
  separate the sqrt vs linear candidates — that needs a controlled same-craft
  A/B. New per-PID-profile CLI setting:

  ```
  set adrc_b0_law = QUADRATIC   # (throttle/hover)^2 — b4 behavior, default
  set adrc_b0_law = SQRT        # sqrt(throttle/hover)
  set adrc_b0_law = LINEAR      # throttle/hover
  set adrc_b0_law = FIXED       # no throttle scheduling
  ```

  Suggested protocol: profile 1 = QUADRATIC, profile 2 = SQRT, profile 3 =
  LINEAR — same craft, same day, same pack rotation, same maneuver script
  (doublets, hover ring check, punch→chop), law switched by PID profile
  between flights, randomized order if you can. The active law is recorded in
  the blackbox header (`adrc_b0_law`); `set debug_mode = ADRC` as always.
  Default QUADRATIC flies exactly like b4.
- **Mid-air liftoff-gate re-arm removed entirely** (ADRC-020): b4 shipped it
  off-by-default, b5 deletes it — throttle+gyro alone cannot distinguish a
  landing from a calm mid-air float, and the fresh-epoch-on-arm behavior
  already covers the ground-rep use case it existed for.
- **PID profiles reset on first boot** when upgrading from **any** earlier
  build (b1–b4): the profile layout changed twice since b4 (ADRC-020 field
  removal, the new selector). `diff all` before flashing, re-apply and verify
  after. (Technical footnote: the config version field is 4 bits, so this
  bump wraps 15 → 0 — the version check is an equality check and no build in
  this lineage ever shipped 0, so the wrap still forces the reset everywhere.)

## What's new in b4

The first flight logs on b3 (thanks @bvandevliet) caught **a regression of the
b3 remediation round** — both defects root-caused from the logs and fixed:

- **The "twitchy" feel is gone**: b3's authority-scaled observer feedback
  silently over-gained the loop by up to ~1.9× at 10–30% throttle without
  airmode, producing a sustained 24–26 Hz roll/pitch limit cycle. The observer
  feedback semantics are reverted to the frame every flight-validated b0 was
  calibrated in.
- **Throttle-punch "nose dip rebound" reduced**: the b0 throttle schedule now
  reads an ~80 ms low-passed collective, so a throttle chop no longer yanks
  the effective gain back up 3× faster than the disturbance estimate can
  re-adapt (also removes a gain modulation at the loop resonance that the
  post-mixer collective was feeding in under airmode).
- **Settings survive from b2/b3** (same PG layout) — `diff all` backup first,
  as always.

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

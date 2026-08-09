# ADRC — prebuilt hex of upstream PR betaflight/betaflight#15400

⚠️ **Experimental. Bench-test before flying. Use at your own risk.**

## b8 — b7 is withdrawn, use this instead

**If you downloaded b7, replace it.** b7 carried a defect in the very gate path it was
built to fix: the hold timer drained at the same rate it filled, which turned "250 ms
continuously above the threshold" into "above it more than half the time". Any duty cycle
over 50 % latched eventually — 1.8 s at 55 %, 0.9 s at 60 % — and ground oscillation is
exactly that kind of signal, so the ground false-open could come back. Raising
`adrc_liftoff_hold_ms` did not help either (22.5 s at 55 % duty for a 1000 ms setting).

b8 resets the timer outright below the threshold, so the hold means what it says. Nothing
else changed; everything described under b7 below still applies. Three tests were added
that the b7 suite let through: ten seconds of bursts, twenty seconds at 60 % duty, and one
that checks `adrc_liftoff_hold_ms` is honoured by this path.

## What's new in b7 (carried into b8)

**This build exists because of one defect: the liftoff gate opened on the ground, by
itself, on every single arm.** Across ten logs from @8ksal8 on 2026-08-06 the gate opened
with the throttle stick at exactly 0.0 %, between 25 and 710 ms after arming and 0.97-2.66 s
*before* the pilot first touched the throttle. The mechanism is the mixer, not the pilot:
when the controller asks for more authority than the mixer has, the mixer normalises the
axis mix and pins the collective at a value that crosses `adrc_liftoff_throttle` on its own.
Once open, the gate admits `b0*u` and lifts the z3 inhibit, and the observer winds up
against a plant that cannot respond.

The gate now reads two different things for two different questions:

- **"Was thrust commanded?"** - the collective as commanded, sampled before the mixer adds
  airmode headroom (this landed in b6). Automatic modes are included: ALT_HOLD and
  GPS_RESCUE override the throttle upstream of that sample.
- **"Is thrust actually being applied, and for long enough to mean flight?"** - the applied
  collective, held above the threshold continuously. Duration is what separates the two
  cases: across those ten logs the longest unbroken run above the threshold before takeoff
  was **43.5 ms** (68.2 ms at a 25 % threshold), while a flying craft holds it for
  **0.37-16.3 s**. The hold is 250 ms, or `adrc_liftoff_hold_ms` if you set it higher.

The applied path also requires that *something* asked for thrust - the same idle interlock
the toss-launch path uses. Without it a held stick, a craft resting wedged or tilted, and
launch control (which forces the commanded collective to zero while forcing airmode on)
would each hold the applied collective up indefinitely on the ground and open the gate
anyway. With it, the timer stays at exactly zero through every pre-takeoff phase in all ten
logs.

**Your PID profiles survive the upgrade from b5** - the stored layout is byte-identical,
including `adrc_b0_law`, so b5 tunes carry over unchanged. (From b1-b4 the b5 reset still
applies, see below.)

### Set `adrc_liftoff_throttle` below your hover, not above it

Worth checking before you fly this build. In those same logs the craft hovered at
**26.8-37.0 %** collective while `adrc_liftoff_throttle` was 40 - so in two of the flights
the threshold was never crossed at all, and only the ground defect above opened the gate.
A threshold above your real hover means the gate can stay shut for a whole flight, which is
the opposite failure: the observer then flies without its actuator feedback. Measure your
hover from a log and set the threshold under it.

### What is still open

Host-tested only - 63/63 unit suites including three ADRC suites, and the new behaviour is
pinned from both sides by tests that fail on b5 and on b6 respectively. **Nothing here has
been flown.** Bench first, props off, and if the motors run away as you arm, disarm
immediately. This build also does not touch loop timing: one tester measured the PID loop
running at half its configured rate with an external serial logger enabled, and since
`dT` is a compile-time constant the observer's effective bandwidth halves with it. That is
a separate open question.

## What's new in b6

Superseded by b7 and never released as a build. b6 made the gate read only the *commanded*
collective, which closed the ground false-open but created the opposite failure: thrust the
mixer applied without the pilot commanding it can still lift the craft, and then nothing
opened the gate at all. b7 keeps the commanded path and adds the applied one behind the
duration test.

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

> **Safety, read before your first ADRC arm.** ADRC-028 has been observed once: a
> single unrestrained props-on ground arm on a 5" craft using the shipped ADRC
> defaults reached the yaw command limit in 87.017 ms and an upper motor rail in
> 127.025 ms, with the collective dragged from 7.7 % to 49.6 % at zero throttle
> stick. That is one craft and one arm — not a demonstration that it happens
> everywhere — but 87 and 127 ms leave no credible margin for a manual cutoff.
> **Do not make your first ADRC arm with props on and the craft unrestrained.**
> Use props off, or a restraint/test stand with an automatic cutoff. Analysis:
> [pr15400-dedlike-mamba](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-dedlike-mamba).

Starting tunables (see the
[tuning guide](https://github.com/danusha2345/ADRC-betaflight#tuning)):
`adrc_wc_* = 60`, `adrc_wo_* = 100` (yaw 80), `adrc_b0_* = 2000` (5") — whoops need
roughly `33/65/3200`. These are the shipped defaults and a starting point only;
they are **not** validated as safe across airframes, and the arm-time behaviour
above was seen on exactly this tune. Set `debug_mode = ADRC` and enable blackbox
if you can — logs are the most valuable thing you can send.

## Where to report

Flight reports, logs and issues: [danusha2345/ADRC-betaflight#2](https://github.com/danusha2345/ADRC-betaflight/issues/2)
(or directly on the PR). Both good and bad results help.

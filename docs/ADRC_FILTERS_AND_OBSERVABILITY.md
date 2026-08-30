# ADRC filters and Blackbox observability

Evidence and source scope: PR #15400 through head `6317fe2a`, fork tester builds
`adrc-pr15400-b9` (`919116fed`) and `adrc-pr15400-b10.1` (`923932bdee`), the
published Air65/Petrel filter and yaw sweeps, and the short Air65 check through
2026-08-30. ADRC is experimental and remains behind a hard tester gate. This
document describes the current signal path and logging contract; it does not
select a universal tune or prescribe a flight programme.

## Which filters act on ADRC

The current ADRC measurement path is:

```text
gyro sensor
  -> Betaflight gyro chain (`gyro.gyroADCf`)
  -> ADRC-dedicated PT2 (`adrc_gyro_lpf_hz`)
  -> ESO (`z1`, `z2`, `z3`)
  -> ADRC P/I/D-equivalent output
```

RPM filtering, dynamic notch filtering and the configured gyro LPFs act before
`gyro.gyroADCf`, so any enabled stage there adds attenuation and delay to the
ADRC loop. ADRC then applies its own PT2 to the same signal. That extra delay
spends phase margin; it does not by itself prove that a particular observed
30–80 Hz line is an observer mode.

The classic D-term filters do not filter ADRC's D-equivalent output. Classic D
is calculated and filtered earlier, then ADRC overwrites the published P/I/D
terms. `yaw_lowpass_hz` likewise belongs to the classic yaw path and does not
shape the final ADRC output. Changing either setting can still coincide with
other configuration changes, so a multi-setting flight is not evidence that
the no-op field caused the result.

The Air65 filter pair shows a strong same-craft association between the main
gyro chain and the weak ~50 Hz yaw descriptor. The later 28-flight Air65/Petrel
`wo` corpus shows that the descriptor also changes with observer settings, with
a stronger Petrel result and a weak/window-sensitive Air65 result. Motor-phase
regression found no detectable lock to orders 1–6. These results justify the
signal-path and delay warning above, but not a universal minimal-filter recipe,
a universal `wc/wo` rule, or attribution of the line to one loop element.

Current decisions from the PR discussion:

- document the verified path and margin cost now;
- do not publish RPM-only/minimal filtering as general guidance until it is
  replicated on another craft;
- keep a separate ADRC gyro tap at design/discussion stage; do not switch the
  controller before simultaneous current/candidate-tap logging exists;
- keep voltage compensation reduced to the early-pack/late-pack fitter
  discriminator. The 2026-08-28 fail-closed split of the included chirp log
  produced no axis with two acceptable segment fits, so the present corpus
  still justifies no firmware feature.

## 2026-08-30 Air65 short check: ADRC PT2 disabled

@8ksal8 posted one indoor-hover log with throttle pumps in
[PR #15400 comment 5466417130](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5466417130).
The attached archive `adrc_gyro_lpf_hz_0_BF_filters_on_btfl_001.zip` has
SHA-256 `3244ee15b63a6148355f95113c085d81f61a8d83e99ae087d14868a9f81047a0`;
its single BBL has SHA-256
`9a7ffcd0a1b0680974ede5794c42f1eecd540612cbb24856a7a2078642e0d249`.

The BBL header, rather than the accompanying statement that this craft was
still on b9, identifies exact b10.1 revision `923932bde`, target
`BETAFPVG473_V2`, and craft name `AIR65 R`. The logged ADRC tune is
`wc=110/110/47`, `wo=150/150/150`, `b0=8964/5378/3586`, SQRT law, and hover
anchor 29%. The dedicated ADRC stage is disabled with
`adrc_gyro_lpf_hz=0`, while the upstream Betaflight gyro chain remains active:
gyro LPF2 at 375 Hz, the 400/300 Hz static notch, three dynamic notches over
110--500 Hz, and one RPM-filter harmonic with a 185 Hz minimum. The classic
D-term filters are disabled.

Pinned `blackbox_decode` commit `f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`
decodes the 91.485 s log with zero failed frames, eight unreadable loop
iterations, and a clean-end event. The pilot described the result as looking
clean. This is a useful existence check that one Air65 can complete a short
hover/throttle-pump session with the ADRC PT2 bypassed while the Betaflight
gyro chain remains enabled. It is not a matched filter A/B, an aggressive
flight, or cross-craft evidence, and therefore does not establish
`adrc_gyro_lpf_hz=0` as a default or a universal filter recipe.

The same comment mentions difficulty configuring serial ports on a different
b10.1 craft, but gives no target, CLI dump, or failure mode. Keep that as a
separate unresolved usability report; this BBL cannot explain it.

## ADRC-029 `z3` scale

Legacy logs store `debug[2]`, `debug[5]` and `debug[6]` as `z3 / 16`. Ordinary
high-`wo` flight can rail that signed-int16 telemetry field even when the
controller itself is not saturated.

ADRC-029 derives the smallest per-profile integer divisor whose int16 endpoint
covers the controller's own worst-case anti-windup bound
`pidSumLimit * b0 * b0ThrottleScaleMax`, including the float32 rounding forms
used by the runtime clamp. The log header writes that divisor as
`adrc_z3_log_scale`. Readers must use the header value when present and fall
back to 16 for b9-and-earlier logs.

This changes instrumentation only. It does not widen the estimator's internal
bound, alter the control output, or make a railed legacy sample recoverable.

## Exact ADRC observability fields

Fork branch
[`adrc-pr-head-observability`](https://github.com/danusha2345/ADRC-betaflight/tree/aa93b5e6807fca4b6a6825c968a2a47db0c82287)
at `aa93b5e680` is based directly on live PR head `6317fe2a`. When all three
conditions hold — `pid_type=ADRC`, `debug_mode=ADRC`, and the Blackbox debug
field-set is enabled — it adds these main-frame fields:

| field | encoding | meaning |
|---|---|---|
| `adrcPidSum[0..2]` | signed, divide by `adrc_pid_sum_scale=10` | `pidData[axis].Sum` sampled directly after the controller, not reconstructed from separately rounded P/I/D/F fields |
| `adrcCommandedCollective` | unsigned, divide by `adrc_collective_scale=1000` | finite/clamped commanded collective consumed by the gate on this PID iteration |
| `adrcAppliedCollective` | unsigned, divide by `adrc_collective_scale=1000` | finite/clamped applied collective consumed by the b0 schedule on this PID iteration |
| `adrcState` | bit mask | bit 0 `liftoff`; bit 1 commanded collective below the gyro-path floor; bits 2/3/4 actual z3 update suppressed on roll/pitch/yaw; bits 5–6 gate cause: 0 none/reset, 1 commanded collective, 2 sustained gyro |
| `adrcGateResetCount` | unsigned counter | increments on every `adrcResetGate()` call; a delta exposes resets that occur between saved frames |

`mixTable()` publishes the next iteration's collective before Blackbox samples
the frame. Logging the mixer getters directly would therefore shift those
values by one PID iteration. ADRC caches the two finite/clamped values at the
point where `adrcUpdatePerLoopState()` consumes them, and Blackbox logs those
caches instead.

`adrcPidSum` removes the ambiguity caused by adding separately rounded terms.
It is still fixed-point telemetry at 0.1 PID-output resolution, and normal
Blackbox decimation still means unsaved PID iterations are not observed. The
existing DISARM event remains the source for the disarm reason; this patch does
not add a cutoff or a new protection path.

`adrcGateResetCount` is a call counter, not a count of physical takeoffs or
landings. Controller-disabled paths may call the reset repeatedly. Its purpose
is to prove that a reset occurred between saved frames, not to classify why it
occurred without the surrounding state/mode evidence.

## Evidence boundaries

- A good flight with legacy `z3` rails proves censored telemetry, not internal
  estimator saturation or instability.
- `adrcState` reports saved-frame state and the latched gate cause. A transition
  in an unsaved iteration is bracketed by adjacent frames unless a counter
  preserves it.
- Commanded collective is not raw stick: it includes upstream automatic
  contributions and autonomous-mode throttle, but excludes mixer-added
  headroom.
- Applied collective is the physical-domain base collective used by the ADRC
  schedule, not the motor mean and not per-motor authority.
- The protection/governor work discussed separately is deferred. None of the
  fields above changes controller behaviour or claims that ADRC-028 is fixed.

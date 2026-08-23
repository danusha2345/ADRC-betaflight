# Restrained MAMBA `wo` sweep with a bounded ARM guard

Date: 2026-08-23. This is a same-craft, restrained props-on ground-arm campaign
on `DIAT MAMBAF722_I2C`. Props/restraint are operator-reported physical setup;
they are not fields in Blackbox. The purpose was to test whether the b9
zero-command arm-time growth reported on another craft changes when only ADRC
`wo` changes, without allowing the mixer to reach an upper motor rail.

## Provenance and fixed configuration

- b9 base: `919116fed7057b7597825c283a2c8a00008ee338`;
- test firmware identities: `b9t750p30` and `b9t1000p30`;
- test-only guard: disarm before the next motor update when any unconstrained
  `abs(pidData.Sum)>=300`, plus a 750 ms or 1000 ms ARM deadline; exact source
  and artifact hashes are in [BOUNDED_GUARD.md](BOUNDED_GUARD.md);
- ADRC: `wc=60/60/60`, `b0=2000/2000/2000`, `adrc_b0_law=SQRT`;
- `adrc_hover_throttle=22`, liftoff threshold `30% / 20 dps`;
- Blackbox `P interval=2`, `debug_mode=ADRC`;
- `dshot_bidir=OFF`, `motor_pwm_protocol=DSHOT600`;
- only `wo` changed between cells, on all three axes.

All 17 decoded arms have zero R/P/Y setpoint in every saved data frame, a
negative/closed `debug[7]` gate marker throughout, and valid firmware/board/tune
headers. No saved frame reaches an upper motor rail.

Blackbox starts data frames after writing its headers. Across the ten
deadline-like `wo=100/125` arms, the median difference between the 750 ms
firmware deadline and the decoded data window is 157496 us. Durations below are
therefore saved-data-window durations, not claimed ARM-to-event times.

## Results

| `wo` | arms | termination | max logged yaw `P+I+D+F` | max motor | upper rail frames |
|---:|---:|---|---|---:|---:|
| 100 | 6 | 6 deadline-like | 3, 14, 11, 21, 27, 20 | 173–262 | 0 |
| 125 | 4 | 4 deadline-like | 222, 219, 214, 217 | 1015–1174 | 0 |
| 137 | 3 | 1 deadline-like, 1 cutoff-like, 1 early/ambiguous | 182, 296, 297 | 1035–1445 | 0 |
| 150 | 4 | **4 cutoff-like** | 300, 290, 300, 296 | 1367–1383 | 0 |

At `wo=150`, the saved windows end 20.966–95.839 ms after their first data
frame, well before the 750 ms deadline. Two logs contain the exact 300
threshold. The other two end at logged maxima 290/296; the guard evaluates
every PID frame while `P interval=2` saves every second one, so a threshold
crossing in an unsaved frame is expected. The endpoint is yaw-D dominated:
`|D|=246–255` versus `|P|=44–49`, with I=F=0 and zero yaw setpoint.

## Supported conclusions

1. On this second Mamba craft, `wo` was the only changed configuration value
   and there is a strong same-craft dose-response association with zero-command
   arm-time yaw-controller growth.
2. `wo=100` produced six quiet bounded arms; `wo=125` produced a large but
   sub-threshold yaw command; `wo=137` was borderline; `wo=150` produced four
   of four early cutoff-like endings.
3. The growth occurs with the gate marker closed, so the b9 gate/z3 mitigation
   does not prevent this separate P/D-driven onset.
4. This campaign does not require bidirectional DShot.
5. The result adds cross-craft evidence in support of keeping ADRC behind a hard
   tester gate rather than selecting a softer universal default.

## Limits

- The guard intentionally prevents an upper motor rail. This campaign measures
  controller growth, not a physical flyaway.
- Hardware, filter chain and timing differ from ADRC-028 and the Bob b9 event.
  This is not proof of an identical mechanism.
- Cell order, pack state and temperature were not randomized. The strong `wo`
  association is not a pure causal estimate.
- One craft and short, censored repeats cannot define a universal safe `wo` or
  a universal 125–137 threshold.
- These logs do not separate the initial gyro excitation into mechanical,
  closed-loop, or interacting causes.

## Reproduction

Build `blackbox_decode` from commit
`f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`; the binary used here had SHA-256
`6b35322c22d5d9e3d23dd171a9ac0424e2fb38f9b8a2232425155d47cd17d23e`.

```bash
DEC=/absolute/path/to/blackbox_decode
for f in *.bbl; do
    "$DEC" --debug --unit-frame-time us --save-headers "$f"
done
python3 bounded_campaign_summary.py
```

The checker fails closed on firmware identity, target, `wc/wo/b0/law`, P
interval, `dshot_bidir`, zero setpoint, closed gate marker, upper-rail absence,
and the expected termination classification.

Raw SHA-256:

- `wo100-baseline-arm01.bbl`: `325484ae016a0c9eca5dde66edaa3172e4e8aaed937736a2268cb7ed945dc02b`
- `wo125-arm01.bbl`: `7e545097c623c7f796bdf2b1e1c84761599ec9d73b72edc2fe0693d6e43ecddb`
- `wo137-1000ms-arm01.bbl`: `54f0dabd3b69c96ea00c8aa6de7d259d4e0ce0086b2e9511ffa4c63da875b28f`
- `wo150-arm01.bbl`: `feb82490559d47e8c3c570c3dbff817d11a386da5d14a970dec2631abf4ffa71`

## Recommended next changes and tests

1. **P0: hard gate and documentation now.** Do not choose replacement ADRC
   defaults from this threshold. Document the actual gyro/filter path and the
   absence of a cross-airframe safe starting tune.
2. **P1: instrumentation before another mechanism claim.** Log exact
   `pidData.Sum[3]`, commanded/applied collective, gate-opening branch, and a
   cutoff/disarm event with the triggering axis/value. That removes the current
   P-interval and reconstructed-sum ambiguity.
3. **P2: treat an ADRC pre-liftoff neutral-stick guard as a candidate, not this
   test patch as a fix.** A production design needs debounce and explicit
   handling for CrashFlip, Launch Control and autonomous throttle, plus negative
   replay over the published corpus, host tests, HIL and restrained hardware
   A/B before merge.
4. **P3: option C is unblocked for design discussion, not implementation.** Log
   both the current filtered gyro and a candidate post-RPM/pre-notch tap in the
   same run first; compare phase/noise offline before routing ADRC to it.
5. **If physical testing resumes:** use a randomized, pack/temperature-controlled
   matrix with CLASSIC negative controls, yaw-only `wo` changes, at least five
   repeats per cell, and the same automatic cutoff. Do not repeat unguarded
   `wo=150` ground arms.

# Air65 (b10.1): dead throttle on a ~500 Hz RC link, and the ground oscillation with airmode

**Data**: 28 BBLs posted by @8ksal8 in PR #15400 between 2026-08-30 and 2026-09-03
(comments 5466417130, 5501121597, 5518861949, 5527547423). Every header identifies fork
build `adrc-pr15400-b10.1` (`923932bde`, BETAFPVG473_V2, 312 us loop, 1/4 logging), craft
`AIR65 R`, ADRC `b0=8964/5378/3586`, hover 29%. Tunes: 30 Aug `wc=110/110/47 wo=150
liftoff 40%` (ANGLE); 1 Sep `wc=103/103/57 wo=140 liftoff 31%` (acro); 3 Sep `wc=wo`
103/140 on all axes, every gyro filter stage off. Archive SHA-256 and the decode commands
are in the tables below. Decoder: pinned `blackbox_decode` `f832acf9cd` (default units;
a second pass with `--unit-flags raw` for the numeric mode mask, bit 0 ARM, bit 1 ANGLE,
bit 24 BOXAIRMODE). Scripts here: `air65_timeline.py` (windowed timeline with the b10
gate/collective fields), `metrics.py` (per-log overview), `rx_sim.py` (replay of
upstream's `shouldUpdateSmoothing()` on RX_TIMING intervals). The three RX_TIMING logs are
included gzipped (`rx_timing_logs/`, SHA256SUMS); the flight logs are the PR attachments.

| archive | sha256 | logs |
|---|---|---|
| airmode_on_off_btfl_005.zip (30 Aug) | 70d48327b3dc3645b63b6b1f7bd2f3313086607b3a122347e4e670fc29c83d97 | 002, 003, 004, 005 |
| Airmode_on_colective_up_on_take_off_btfl_008.zip (1 Sep) | e65d705be11bdde0c1a0b274a146a6505d021bd8f010fbe517e8d8cddaec149e | 007, 008, 009 |
| Air65_Arm_No_Props_.zip (3 Sep, RX_TIMING) | acb11653a8782730aceb76e684ebdbc555bbc624099027c40d11b3182656376e | 004, 005, 006 |
| Air65_No_filters_btfl_003.zip (3 Sep) | b82798c2f2aec51afdee42a2a162d357a02e4cc036a32434b2961406166e3abf | 003 |
| pid_at_min_throttle.OFF_Airmode_on.zip (3 Sep) | 99d0059c16943f33ab1d11f31ed4fb46f8d5969d280bc9dfe635cb04a78a10d6 | 001–008 |
| pid_at_min_throttle.OFF_Airmode_off.zip (3 Sep) | ccb6cb04ad4859ba5ced20615bc7de683c46510bd5528bacad1660284f2bf115 | 001–009 |

Caveat that cost a day: in b10 the `rollPID/pitchPID/yawPID` header lines no longer carry
the ADRC tune (PID profiles were split, PG 13); read `adrcWC/adrcWO/adrcB0`.

## 1. Dead throttle: `rcCommand[THROTTLE] = 0` on a link the FC sees at ~500 Hz

Five arms out of 24 (30 Aug 003/004; 3 Sep OFF_off 004/005, OFF_on 001) have
`rcCommand[3] = 0` for the whole log (a healthy log reads 1000 at stick minimum), mixer
throttle 0, roll/pitch `rcCommand` 0, yaw `rcCommand` alive, RSSI/LQ normal, failsafe IDLE,
ARM set. Their headers read `rc_smoothing_rx_smoothed` 490–503 and
`rc_smoothing_active_cutoffs_ff_sp_thr = 0,0`; the 19 healthy arms read 252–256 and
93–95. The header separates the two groups without exception.

Code path (`src/main/fc/rc.c`, identical in b9 `919116fed`, b10.1, `betaflight/master`
`e8580ad977` and release `2026.6.1`; introduced by upstream #15291 `4a213bf18b`):

- `processRcSmoothingFilter()` applies the PT3 setpoint/throttle filters unconditionally
  whenever `rc_smoothing = 1` (the default);
- the filters' gain is only ever written by `rcSmoothingSetFilterCutoffs()`, which runs when
  `shouldUpdateSmoothing()` returns true — three *consecutive* frames whose rate is within
  ±20% of the running estimate `smoothedRxRateHz`; an outlier resets the valid count, and
  three same-sign outliers snap the estimate to the current rate;
- `rcSmoothingData` is `FAST_DATA_ZERO_INIT` and `initRcProcessing()` sets only the cutoff
  *settings*, so until that first update the PT3 gain is 0 and `pt3FilterApply()` returns
  its zero state: `rcCommand[THROTTLE] = 0`, `setpointRate[RPY] = 0`;
- arming and `calculateThrottleStatus()` read raw `rcData`, so the craft arms normally.

The RX_TIMING arms show why the update never comes. All three (`rx_timing_logs/`) carry a
strict frame pattern of two ~2 ms gaps then one ~4 ms gap (`S S L S S L …`; 1732/2482/3893
frames, 66.6% short, 3 irregular runs in total). `rx_sim.py` replays the upstream logic on
the recorded sequences: from a 100, 250 or 500 Hz starting estimate it produces **0 cutoff
updates on 004 and 005, and 2 on 006, both at the irregular runs**. A synthetic `2,2,2,4`
pattern updates immediately; `2,2,4` never does. So on this link the filters are
initialised only by a chance run of three equal gaps that also matches the estimate the FC
latched at link-up; whether that has happened before the pilot arms is a race. The tester
reported the link set to 500 Hz on 2026-08-21; the OTA cause of the `2,2,4` pattern is not
visible from the FC side and is not claimed here.

Workarounds that cannot enter this state: a packet rate with evenly spaced frames (the
tester's 250 Hz logs), or `rc_smoothing = OFF` (early return before the filters). Manual
`rc_smoothing_*_cutoff` values do not help — the gain write is still behind the same gate.

## 2. Ground oscillation with airmode: the gate holds, the P/D path plus mixer headroom lifts

**`pid_at_min_throttle = ON` (1 Sep 007/008/009, acro).** From arm until the stick moved
(0.28–0.85 s) all three arms oscillate at 23–28 Hz on roll/pitch (FFT of the arm segment:
46–93% of the energy in 20–30 Hz; gyro RMS up to 49 °/s, peaks 118–168 °/s). Commanded
collective ≤ 6.6%, applied collective 53–59%, mean motor 47–52% against a 29% hover. The
gate is closed, the z3 growth inhibit is on for all axes and z3 = 0 throughout — the
ADRC-026 fix behaves as designed; what oscillates is the P/D path, and the mixer's airmode
headroom (added from the moment of arming whenever the AIRMODE feature or box is on —
`mixer.c:707`, `rc_modes.c:203`, unchanged from upstream) turns the axis demand into
collective. The gate opened 40–100 ms after the stick moved (gyro path) and the RMS fell to
6–18 °/s within 0.1–0.4 s. `airmode_activate_throttle` only latches `throttleRaised`, which
enables I-term/PID stabilisation (`core.c:851–870`); it does not gate the mixer headroom.

**`pid_at_min_throttle = OFF` (3 Sep, 17 arms).** The arm phase is quiet (motors flat at
6.3% idle, controller off, `adrcState = 2`). The controller turns on when the *raw* stick
leaves idle (`throttleActive`, from `rcData`), and the same oscillation starts at once; it
lasts until the liftoff gate opens 0.27–1.13 s later (gyro or commanded path), with applied
collective 26–70% and mean motor 26–67% in that window. `OFF` therefore moves the ground
oscillation from arm time to throttle-up time; the gate opening ends it in every arm.

**Dead throttle + airmode + `OFF` (`OFF_on/001`)**: motors flat for 3.5 s, then the raw
stick enables the controller while the smoothed throttle is still 0: 27.5 Hz, applied 40%,
mean motor 37%, gate closed, z3 = 0, no throttle authority — the tester's second-arm
flyaway. The 30 Aug `003` (prop rubbing, ANGLE, `ON`) is the same combination: 27.5–28 Hz,
motors to 98%, applied 45–49% at 1% commanded, a 2099 °/s event at 1.75 s.

**Controls.** The same craft on 30 Aug (ANGLE, liftoff 40%, `ON`) did not oscillate during
the arm phase in 002/005; 005 did in the 0.7 s between stick and gate. Mode, `wo`, liftoff
threshold and the day changed together; nothing here attributes the difference. The
mechanism of the 23–28 Hz loop with the gate closed is not identified.

## 3. Flights

| set | logs | err median R/P/Y (°/s) | p90 | motor-rail frames | notes |
|---|---|---|---|---|---|
| 30 Aug 002/005 (ANGLE) | 2 | 2–3 | 8–14 | 0.9–2.3% | |
| 1 Sep 007/008/009 (acro) | 3 | 4–7 | 14–23 | 2.3–7.8% | |
| 3 Sep no-filters 003 | 1 | 11/12/14 | 29/37/41 | 3.1% | yaw-error line 76–77.5 Hz in 65/66 windows; not a motor order (fundamental 400–500 Hz from eRPM) |
| 3 Sep OFF sets | 13 | 10–20 | 29–57 | 2.1–5.0% | no z3 telemetry clipping |

Unexplained and left as such: in 30 Aug `004` all four motors step up uniformly by ~5.5% at
2.1 s (eRPM 5.6k → 8.6k) with no logged command change (dyn idle is above its minimum,
MOTOR_STOP off).

## What this does and does not support

- The dead-throttle arms are an upstream RC-smoothing initialisation race, present in the
  2026.6.x release line; ADRC is not involved. Filed upstream with the RX_TIMING logs.
- Under ADRC at these gains, airmode headroom on the ground lifts the craft while the loop
  oscillates with the gate closed; z3 is not the driver. Airmode on a switch after takeoff
  avoids the arm/throttle-up window. No firmware or default change is proposed from these
  arms alone.

## Addendum 2026-09-04: @jmsweng's single-axis arm flyaway (PR comment 5532698449)

Archive `BTFL_BLACKBOX_LOG_20260903_172741_BETAFPVG473_V2.zip`, SHA-256
`89ee5244dbe0fffa7f9d3db3f29e7edd3e6be77f695e09a20833da0f5e676bff`; the BBL is included
gzipped in `jmsweng_flyaway_20260903/` (SHA256SUMS). Header: b10.1 `923932bde`,
BETAFPVG473_V2 (tester: stock Air65 II Freestyle, BMI270), `pid_at_min_throttle = ON`,
AIRMODE feature on, link 250 Hz with smoothing cutoffs 93/93 (healthy). ADRC per axis:
roll `wc/wo = 40/70`, **pitch `103/140`** (8ksal8's values, applied to one axis as an
experiment), yaw `40/70`; `b0 = 3700/2500/2430` (tester: 75 % of his chirp-fit values),
`adrc_b0_law = 2` (LINEAR), hover 27 %, liftoff 40 %, ADRC gyro LPF 150 Hz plus the stock
gyro chain (LPF1 250 dyn, LPF2 500, 3 dynamic notches, 3 RPM harmonics), D-term LPF 75.

The arm lasts 1.91 s with the stick at 1000 and commanded collective 0 % throughout;
`adrcState` is 30 (gate closed, idle, z3 inhibit on all axes) in every frame and z3 = 0.

| t | roll gyro peak | pitch gyro peak | applied collective | mean motor | frames with a motor at 100 % |
|---|---:|---:|---:|---:|---|
| 0.3–0.9 s | 31 → 124 °/s, 15.1 Hz (94 % of roll energy in 10–25 Hz) | 6 → 22 °/s | 7 → 18 % | 7 → 18 % | none |
| 1.0 s | 270 | 283 | 44 % | 44 % | from here: 75.5 % of frames |
| 1.1–1.9 s | 237 → 15 | 293 → 219, 19.3 Hz (99 % in 10–25 Hz) | 43–50 % | 43–50 % | |

The roll axis (40/70) starts a ~15 Hz wobble first and grows for 0.6 s while pitch stays
below 22 °/s; the airmode headroom follows the roll demand (applied 7 → 18 % at 0 %
commanded). At 1.0 s the pitch loop (103/140) breaks into a 19.3 Hz oscillation with its
sum clipped at `pidsum_limit` (logged |sum| up to 2043 against the 500 limit), the mixer
fills the axis demand with collective, mean motor reaches 44–50 % against a 27 % hover,
and the craft lifts with no throttle command; roll decays while pitch persists until
disarm. With the stick at idle none of the three gate paths can open (commanded ≥ 40 %;
gyro/applied paths locked by the idle interlock at < 20 % commanded), so nothing in the
controller ends the event.

What this adds: a healthy link, `ON`, the full stock filter chain plus the ADRC LPF, and a
second tester's craft reproduce the arm-time lift with the gate closed and z3 = 0; the
oscillation frequencies (15 / 19 Hz) are lower than 8ksal8's 23–28 Hz on the unfiltered
chain. The tester's reading — too high `wo` picking up sensor noise — is not what the log
shows on the mechanism side (coherent 15–40 Hz loop energy, not broadband), and the corpus
does not isolate `wo`: 8ksal8's 30 Aug arms at `110/150` were quiet during the arm phase
with a different filter chain, mode and liftoff threshold. Every arm-time event so far is
at `wo ≥ 140`; no counterexample exists at 40–70. Suggested controls: the same one-axis
change on roll instead of pitch, and pitch at `103/140` with the ADRC LPF at 0.

## Addendum 2026-09-04 (2): @jmsweng's four single-axis arms; @8ksal8's `40/70` vs `92/120`

**jmsweng** — archive `BTFL_BLACKBOX_LOG_20260904_073102_BETAFPVG473_V2.zip`, SHA-256
`1ba731446bb93d87a568aaa288b221651e9435f7dccc6b43e567bc378953ce90`, one BBL with four logs
(gzipped in `jmsweng_axis_arms_20260904/`). Same craft/build/filters as the 2026-09-03
addendum, `pid_at_min_throttle = ON`, AIRMODE feature on, LINEAR, `b0 = 3700/2500/2430`.
Per-log tune (header `adrcWC/adrcWO`): log 1 roll `103/140`; logs 2–3 yaw `103/140`; log 4
roll+yaw `103/140`; every other axis `40/70`.

| log | hot axis | span | gyro peaks R/P/Y (°/s) | dominant Hz R/P/Y | applied max | mean motor > hover from | frames with a motor at 100 % |
|---|---|---:|---|---|---:|---:|---:|
| 1 | roll | 0.97 s | 357/244/27 | 19.3/14.2/– | 53 % | 0.17 s | 65 % |
| 2 | yaw | 0.89 s | 2550/1032/381 | 15.4/14.3/40.7 | 70 % | 0.08 s | 28 % |
| 3 | yaw | 0.92 s | 182/184/149 | 15.1/14.0/41.0 | 64 % | 0.10 s | 35 % |
| 4 | roll+yaw | 0.80 s | 236/392/144 | 19.5/13.4/40.2 | 65 % | 0.09 s | 81 % |

All four: stick 1000 and commanded collective 0 % throughout, `adrcState` = 30 (gate closed,
idle, z3 inhibit) in every frame, z3 = 0. The hot axis sets its own frequency (roll
`103/140` → 19 Hz, yaw `103/140` → 41 Hz; pitch → 19 Hz on 09-03), but the `40/70` axes
oscillate at 14–15 Hz in every arm — in the yaw-only arms roll/pitch reach 180–2550 °/s
against 150–380 on yaw. Lift is faster than the 09-03 pitch case (≤ 0.2 s vs 1.0 s).

**8ksal8** — `jmsweng_tune_btfl_001.zip` (`2edebd11…0cd1`) and `40_70_btfl_001.zip`
(`7d1764b4…397a`) contain the same BBL (SHA-256 `0223e35e…961d`); `92_120_btfl_014.zip`
(`d0a8a09a…07b5`). Both flights gzipped in `8ksal8_tune_compare_20260904/`. b10.1,
`pid_at_min_throttle = OFF`, airmode by switch, ADRC LPF 0, gyro LPF1 200 + 3 dynamic
notches + 1 RPM harmonic, link 250 Hz / cutoffs 62.

| | `40/70`, b0 3700/2500/2430 | `92/120`, b0 8964/5378/3586 |
|---|---|---|
| span, vbat | 165 s, 2.46–4.30 V (5.7 % of samples < 3.0 V, last 5 s median 2.76 V) | 148 s, 2.84–4.37 V |
| tracking-error median / p90 R/P/Y | 8/5/7, 34/22/29 °/s | 6/3/3, 17/10/10 °/s |
| overshoot proxy A (share of |setpoint| > 150 samples with gyro > 120 % of setpoint, same sign) | 20/14/13 % | 4/2/0 % |
| overshoot proxy B (per step > 200 °/s: peak gyro / peak setpoint; share > 1.2; n) | 1.14/1.08/1.06; 20/8/8 %; n = 10/12/12 | 1.14/1.06/1.08; 0/0/0 %; n = 4/11/1 |
| per-motor RMS 50–75 Hz / 15–25 Hz | 0.25 % / 0.7–1.0 % (15–25 Hz line in all 2-s windows) | 3.9 % (51–61 Hz line in 50 of 72 windows; weak in the yaw mix) / 0.6–0.8 % |
| error band 30–80 Hz RMS R/P/Y | 1.50/1.16/1.40 | 1.39/1.31/3.46 (yaw line 61 Hz) |
| motor-rail frames | 0.6 % | 1.6 % |

`40/70` tracks looser with more overshoot (roll most by both proxies; yaw is not the worst
axis here and the `92/120` flight has one large yaw step); `92/120` tracks tightly and
carries a ~58 Hz line on all four motors. The line sits where the earlier sweeps put the
`wo`-tracking peak (`wo` 80 → 47–53 Hz, 120 → 58–61 Hz, 140 → 77 Hz on the unfiltered
flight) — observation, not mechanism. The `40/70` log ends on a sagging pack.

## Addendum 2026-09-05: @8ksal8's `wc/wo` sweep and ESC PWM sweep (PR comment 5545438021)

Archives `wc_wo_sweep.zip` (SHA-256 `bc64d222b9473c843c4c063817fcb5f3d7ec9c53de1032560b20b46e00f1e0dd`) and
`ESC_PWM_sweep.zip` (`8c523c89302948be211ce2ac2cad42d5314a56c22bf117b4884d350345715b8a`); the eight BBLs
are gzipped in `8ksal8_sweeps_20260904/`. All b10.1 on the Air65 R, `b0 = 8964/5378/3586`, SQRT,
ADRC LPF 0, gyro LPF1 200 + 3 dynamic notches + 1 RPM harmonic, bidirectional DShot, airmode by
switch, link 250 Hz / cutoffs 62. `pid_at_min_throttle` differs across logs (OFF in 70/80, 88/100,
97/110; ON in 79/90, 106/120 and the three PWM logs) — irrelevant in flight, a confound in the set.
The ESC PWM frequency is not in the Blackbox header; those three logs are labelled by file name only.

Metrics: whole flight after the gate opened; motor line = strongest 40–80 Hz peak of one motor,
RMS averaged over four motors; overshoot = share of |setpoint| > 150 samples with gyro > 120 % of
setpoint (same sign); yaw-error line = 40–80 Hz peak prominence over the 10–150 Hz median.

| wc/wo | pamt | span | vbat med/min | err median R/P/Y | p90 | overshoot R/P/Y | motor line | line RMS/motor | yaw-err line f / prom | rail frames |
|---|---|---:|---|---|---|---|---:|---:|---|---:|
| 70/80 | OFF | 56 s | 3.89/3.32 | 10/5/5 | 40/22/32 | 67/22/17 % | 46.1 Hz | 0.37 % | 48.2 Hz / 11 | 0.8 % |
| 79/90 | ON | 50 s | 3.65/3.15 | 9/5/5 | 40/24/35 | 41/35/6 % | 41.9 Hz | 0.49 % | 51.5 Hz / 9 | 2.0 % |
| 88/100 | OFF | 57 s | 3.49/3.05 | 7/4/4 | 23/17/16 | 17/7/5 % | 54.0 Hz | 1.05 % | 54.2 Hz / 30 | 2.1 % |
| 97/110 | OFF | 65 s | 3.89/3.32 | 8/5/5 | 29/18/18 | 9/7/17 % | 58.3 Hz | 1.95 % | 58.3 Hz / 134 | 2.0 % |
| 106/120 | ON | 64 s | 3.54/3.08 | 6/4/6 | 25/16/34 | 12/7/13 % | 60.6 Hz | **16.2 %** | 60.6 Hz / 26128 | 3.1 % |
| 88/100, ESC 24 kHz | ON | 72 s | 3.58/3.08 | 9/5/5 | 36/19/30 | 20/12/19 % | 52.9 Hz | 0.74 % | 57.7 Hz / 13 | 1.2 % |
| 88/100, ESC 48 kHz | ON | 71 s | 3.81/3.54 | 11/6/6 | 34/21/25 | 19/13/15 % | 58.2 Hz | 0.90 % | 59.8 Hz / 32 | 0.0 % |
| 88/100, ESC 96 kHz | ON | 91 s | 3.91/3.67 | 10/5/5 | 31/16/27 | 13/13/15 % | 62.5 Hz | 0.74 % | 62.5 Hz / 20 | 0.0 % |

Overshoot falls with `wc`; the motor line grows slowly to 97/110 and by ×8 at 106/120, where the
60.6 Hz line is present in every 2-s window (5-s windows 3–28 % relative RMS, gyro peaks 640–715 °/s
at 38–48 s). Its frequency follows `wo` (≈ 0.5–0.55 × `wo`: 46/42/54/58/61 Hz for 80/90/100/110/120),
consistent with the August sweeps and the 77 Hz at `wo` 140. ESC PWM 24/48/96 kHz at 88/100 does
not change the line amplitude beyond flight-to-flight scatter (0.74–0.90 % vs 1.05 % in the sweep's
own 88/100 flight); the 53 → 62 Hz peak drift across the three is unexplained (one flight per
setting). Packs 3.05–3.67 V minimum throughout.

## Addendum 2026-09-05b: @8ksal8's `adrc_sigma_decay 0` + `adrc_b0_scale_max` 4 vs 5 pair (PR comment 5552521564)

Archive `sigma_decay_0_b0_scale_4_5_btfl_002.zip` (SHA-256
`3d94459c0266aec34ae929748f2a438260c332f46c70f9f2ed73fd3efeba0a15`); the two BBLs are gzipped in
`8ksal8_sigma_b0scale_20260905/`. Both b10.1 (`923932bde`) on the Air65 R at 99/110, `b0 = 8964/5378/3586`,
SQRT law, hover 29, ADRC LPF 0, same gyro chain as the sweep, `pid_at_min_throttle` OFF. Header diff to
the sweep's 97/110 flight: `adrc_sigma_decay` 3 → 0, `adrc_b0_scale_max` 3 → 4/5, `wc` 97 → 99 (and the
`simplified_dterm_filter` UI flag, inert under ADRC). Same metric definitions as addendum 2026-09-05;
"calm" = |setpoint| < 30 °/s, "active" = |setpoint| > 150 °/s.

| | scale_max 4 (001) | scale_max 5 (002) | sweep 97/110 (ref) |
|---|---:|---:|---:|
| span after gate | 200 s | 178 s | 63 s |
| active-stick share R/P/Y | 2.6/4.7/4.1 % | 3.8/3.5/5.6 % | 5.6/7.5/4.4 % |
| vbat median / min | 3.62 / 2.96 V | 3.51 / 2.49 V | 3.88 / 3.32 V |
| frames < 3.0 V | 0.06 % | 1.2 % | 0 |
| current median / p95 | 3.4 / 7.6 A | 3.3 / 7.4 A | 4.2 / 10.1 A |
| err median R/P/Y (whole) | 4/2/3 | 4/3/3 | 8/5/5 |
| err median, calm | 4/2/3 | 3/2/2 | 8/4/4 |
| err median, active | 19/14/4 | 19/17/4 | 21/12/23 |
| overshoot R/P/Y | 4/3/2 % | 8/5/0 % | 9/7/17 % |
| motor line / RMS per motor | 60.0 Hz / 1.07 % | 60.5 Hz / 0.94 % | 58.5 Hz / 2.19 % |
| 5-s window line RMS min/med/max | 0.4/0.8/2.4 % | 0.3/0.6/4.0 % | 1.0/1.4/5.4 % |
| rail frames | 1.4 % | 2.2 % | 2.1 % |
| b0 throttle scale median / max | 1.14 / 1.75 | 1.14 / 1.75 | 1.14 / 1.76 |
| max \|z3\| R/P/Y (×10³) | 1121/1038/1066 | 2841/1440/1379 | 2375/1429/672 |
| z3 pitch trim, 30-s medians (×10³) | −253…−200 | −291…−216 | −310…−189 |

Findings:

- **`adrc_b0_scale_max` 4 vs 5 did not act.** In b10.1 `adrc.c` the SQRT law is
  `scale = clamp(sqrt(throttle_lpf / hover), 1, scale_max)`; with hover 29 % the unclamped value is
  1.86 at 100 % throttle, and the logs (debug[7]) show 1.72–1.75 at full stick. Any cap ≥ 2 is the same
  setting on this craft; 3, 4 and 5 are identical in flight. The z3 anti-windup bound is
  `pidsum_limit · b0 · live scale` (≥ 5.1 M on roll here), untouched by the cap and not reached (max 2.8 M).
  The only header field that moved with the cap is `adrc_z3_log_scale` (548 vs 684).
- **The "hotter pack" on scale_max 5 is the pack.** Flight 002 started lower (3.27 V min in the first
  20 s vs 3.49 V), sagged to 2.49 V at ~7 A, and spent 1.2 % of frames under 3.0 V against 0.06 %; the
  median current is the same. The higher rail share and the single 5-s window at 4.0 % line RMS in that
  flight coincide with the sag.
- **`adrc_sigma_decay` 0 vs 3 is not resolvable in flight.** Steady-state error left by a leak of 0.3/s
  against a constant disturbance is `decay · z3 / wo³`; at `wo` 110 and the pitch trim z3 ≈ 250 k
  that is ≈ 0.06 °/s. The better tracking in the pair (calm median 4/2/3 vs 8/4/4) goes with the
  gentler flying (active share roughly halved) and cannot be attributed to the setting. z3 stays well
  inside its bound and the pitch trim is unchanged, so nothing argues against 0 either.
- 99/110 with this filter chain holds the motor line at 0.94–1.07 % (60 Hz ≈ 0.55 × `wo` again), against
  2.19 % in the sweep's own 97/110 flight and 0.71–1.05 % across the four 88/100 flights — inside the
  flight-to-flight scatter, well below the 106/120 knee.

## Addendum 2026-09-06: @8ksal8's b0-law pair, law sweeps with throttle pumps, PID baseline (PR comments 5553626089, 5553723483)

Archives `b0_F_L_btfl_002.zip` (SHA-256 `f3a859a72172b2d39ef45db6ec035cac296a8ce665a6994940a03497de4f0de2`),
`b0_law_sweeps_w_throttle_pumps.zip` (`2908b2587a04c6e53486019b142e54541ef3bad34f4d2848752def666c49d330`) and the
settings dump `Air65_BF_settings_.zip` (`2bcb33068b18a422773f860c9033fd3d4322ec87080dbe2a65a7030d217c8f48`);
the eight BBLs are gzipped in `8ksal8_b0laws_20260905/`. ADRC logs: b10.1, Air65 R, 99/110, `b0 = 8964/5378/3586`,
hover 29, `sigma_decay` 0, `scale_max` 4, ADRC LPF 0; `pid_at_min_throttle` ON in LINEAR/QUADRATIC, OFF in
FIXED/SQRT. `CLASSIC_btfl_001` is a classic-PID flight (38/54/26, debug 19) on the same craft.

Pump = throttle rising ≥ 15 % within 0.3 s from below 30 %; chop = the reverse; peak |setpoint − gyro| in the
0.8 s after each; scale = debug[7] at the pump; z3 swing = largest peak-to-peak of any axis's z3 in that window.
Motor line as in the earlier addenda, windowed 2 s, split by the window's median throttle.

| log | law | span | pumps | peak err R/P pump | chop | scale at pump | z3 swing | line RMS thr<35 % / >45 % | vbat min |
|---|---|---:|---:|---|---|---:|---:|---|---:|
| CLASSIC_001 | PID | 87 s | 15 | 18 / 21 | 17 / 20 | — | — | 0.3 % / — | — |
| FIXED_003 | FIXED | 57 s | 17 | 34 / 29 | 33 / 27 | 1.00 | 390 k | 6.0 % / 2.8 % | 3.07 V |
| FIXED2_002 | FIXED | 48 s | 15 | 32 / 33 | 30 / 30 | 1.00 | — | 4.5 % / 2.8 % | 3.04 V |
| SQRT_001 | SQRT | 48 s | 16 | 42 / 46 | 40 / 42 | 1.56 | 580 k | 1.7 % / — | 3.40 V |
| LINEAR_002 | LINEAR | 42 s | 12 | 93 / 96 | 88 / 94 | 2.58 | 1 100 k | 3.1 % / — | 3.24 V |
| QUADRATIC_001 | QUAD | 46 s | 18 | 122 / 160 | 122 / 156 | 4.00 (cap, 7.2 % of frames) | 2 290 k | 0.9 % / — | 3.31 V |
| b0_FIXED_001 | FIXED | 199 s | 20 | 38 / 28 | 29 / 26 | 1.00 | 530 k | 1.3 % / 1.0 % | 2.80 V |
| b0_LINEAR_002 | LINEAR | 178 s | 17 | 49 / 45 | 51 / 42 | 1.62 | 770 k | 0.8 % / 0.2 % | 2.94 V |

Findings:

- **Pump error is monotone in the scale the law reaches at the top of the pump.** Each step up in scale is a
  step down in controller gain (`kp/b0`, `kd/b0`); the observer sees the gap as a disturbance, z3 swings to fill
  it and swings back on the chop. FIXED never leaves 1.00 and is flattest; QUADRATIC at hover 29 hits the cap.
- **Below hover the four laws are the same code path** (scale clamped to ≥ 1), so the "strange 0–20 %" feel is
  the return from the pump, not the low range itself. Raising `adrc_hover_throttle` moves every non-FIXED law
  toward FIXED.
- **PID baseline** does the same pumps at 18–21 °/s against 30–38 for ADRC FIXED.
- Motor line 59–60 Hz (0.55 × `wo`) in every ADRC log; 1.7–6 % in the short pump flights, 0.7–1.7 % in the long
  ones, no ordering by law that survives the pump content. PID 0.3 %.

## Addendum 2026-09-06b: @8ksal8's FIXED-law `wc/wo` sweep at hover 5 (PR comment 5559979730)

Archive `FIXED_hover_throttle_5_.zip` (SHA-256 `3732cd75099306af30aa8e624e81dd2e3dbafc0d5e9c82ce5b17078cb54c788d`);
six BBLs gzipped in `8ksal8_fixed_hover5_20260906/`. b10.1, Air65 R, FIXED, `adrc_hover_throttle` 5, `sigma_decay` 0,
`b0 = 8964/5378/3586`, `pid_at_min_throttle` ON, filter chain as before.

**`adrc_hover_throttle` is inert under FIXED.** In b10.1 `adrc.c` the only consumer of `hoverThrottlePercent` is the
b0 throttle schedule (`adrcUpdatePerLoopState()`, line 676); FIXED returns `rawScale = 1` regardless, and debug[7]
reads 1.00 on every frame of all six logs, as in the hover-29 FIXED flights. The tester's perceived hover effect on
FIXED therefore has no firmware cause. Same metrics as the earlier addenda.

| wc/wo | span | err median R/P/Y | p90 | overshoot R/P/Y | motor line | line RMS/motor | 5-s windows min/med/max | rail | vbat min |
|---|---:|---|---|---|---:|---:|---|---:|---:|
| 90/100 | 63 s | 5/3/3 | 20/11/9 | 9/7/0 % | 55.5 Hz | 0.73 % | 0.5/0.8/0.9 % | 2.7 % | 3.21 V |
| 92/102 | 64 s | 5/3/3 | 19/13/8 | 6/7/0 % | 55.5 Hz | 0.85 % | 0.6/0.9/1.0 % | 3.0 % | 3.14 V |
| 94/104 | 66 s | 6/3/3 | 22/14/11 | 3/8/0 % | 55.5 Hz | 1.21 % | 0.9/1.3/1.7 % | 3.1 % | 3.06 V |
| 95/106 | 65 s | 5/3/3 | 18/12/9 | 5/4/0 % | 58.0 Hz | 1.32 % | 0.5/1.2/1.9 % | 2.9 % | 3.32 V |
| 97/108 | 61 s | 4/3/3 | 16/11/9 | 4/4/0 % | 58.5 Hz | 2.95 % | 2.1/3.0/3.7 % | 3.7 % | 3.15 V |
| 99/110 | 62 s | 5/3/4 | 19/13/16 | 5/7/2 % | 59.0 Hz | **8.66 %** | 3.3/6.7/19.1 % | 3.1 % | 3.10 V |

Tracking is flat across the sweep; the motor line rises 0.7 → 1.3 % to 95/106, 3 % at 97/108, 8.7 % at 99/110. On
FIXED the knee sits ≈ 10 `wo` below the SQRT sweep's (2 % at 97/110, ×8 at 106/120): SQRT lowered the loop gain by up
to 1.75× above hover, FIXED does not. Line frequency 0.54–0.55 × `wo`.

## Addendum 2026-09-07: first ground-wc (ADRC-030) tests — jmsweng tap tests on the Air65, 8ksal8 TH3+ 2.5" arms and packs (PR comments 5562538603, 5563565563)

Archives: `b11 tests.zip` (`8cc1d2869967b2c596b17ad5f54a9f123b30c5f6a0bda712bd1420e06cace4be`, exp2 `33004f5c`,
`adrc_wc_ramp_ms` 100 set by hand), `US_81_90_2s_3s_b9_btfl_001.zip` (`ef7a7aa0fbe9786f1d8dd9bc3d57a336add31cf7dc0e8a45d3288112b798c4d3`),
`US_81_90_4s_b9_btfl_001.zip` (`94f6a16d8b1cf1c60f99f264af063993bcc796c9dfa4082d30bf21c8cf75bc5b`),
`b11_exp3_Air_Angle_Arm_btfl_001.zip` (`d2ad5cb0c0688de6225d3466716a74965f760f958a23bc855b41278cd649f34e`, exp3 `83a12fc3`).
Ten BBLs gzipped in `b11_tests_20260907/`. Scripts: `ground.py` (per-arm ground segments, bursts with |gyro| > 30 °/s
while the gate is closed), `burst.py` (per-second envelope, motor max, applied/commanded collective, spectrum).

### jmsweng, Air65, tap tests (props on, airmode on, stick at idle)

| log | wc/wo | b0 | ground wc | bursts | peak | motors | settles | gate |
|---|---|---|---:|---|---:|---|---|---|
| 103/140 single axis (pitch) | 40,103,40 / 70,140,70 | 3700/2500/2430 | 40 | 3rd tap at 3.4 s → continuous | 520–1365 °/s every second for 14 s | 2047 every second, mean 550–650 | never (disarmed) | closed throughout; applied collective 600–730 vs commanded 0 |
| same | same | same | 5 | 3 taps | 394–566 °/s | peak 901, no rail | ≈ 1 s each | closed |
| 99/110 all axes | 99/110 | 8964/5378/3586 | 40 | 3 taps | 582–682 °/s | 2047 during bursts | 0.26–0.44 s | closed until the flight at 9.4 s |
| 99/110 all axes | 99/110 | same | 5 | 3 taps | 473–951 °/s | no rail | 0.3–0.6 s | closed |

The 103/140 run at ground wc 40 is a 4 Hz rock (harmonics 8/14/16 Hz), not the 15–19 Hz ring of the 3 Sep arms:
the airmode headroom re-kicks a grounded craft rail-to-idle and the gyro path cannot open the gate with the stick at
idle (ADRC-026), so it rocks instead of lifting and walked off the couch. What separates it from the 99/110 run at
the same ground wc is the ground loop gain, `wc²/b0` (P) and `2·wc·wo/b0` (D): with `b0` 2500 and `wo` 140 against
5378 and 110 the P gain is 2.15× and the D gain 2.74× higher. A bare-`wc` default therefore cannot be right for every
`b0`; the acceptance test is the tap (three taps: each burst dead within ≈ 1 s, no motor at 2047).

### 8ksal8, TH3+ Freestyle 2.5", F722, FIXED, 81/90, hover 5, sigma 0, per-pack b0

exp3 arms: airmode arm 3.1 s on the ground and angle + airmode arm 3.8 s, no gyro activity above 30 °/s, motors
≈ 360 mean / 720 peak, gate opened on the throttle. Flights (same metrics as before):

| log | span | err median R/P/Y | p90 | overshoot | motor line | line RMS/motor | rail | vbat min |
|---|---:|---|---|---|---:|---:|---:|---:|
| exp3 airmode arm (3S, 6560/3936/2624) | 46 s | 3/2/2 | 9/7/7 | 7/9/0 % | 63.0 Hz | 0.65 % | 0 | 10.26 V |
| exp3 angle + airmode arm (3S) | 188 s | 2/2/2 | 8/6/6 | 5/11/0 % | 63.3 Hz | 0.61 % | 0.2 % | 9.05 V |
| b9 2S (4912/2947/1965) | 290 s | 3/2/2 | 11/7/8 | 10/10/0 % | 61.0 Hz | 0.31 % | 1.0 % | 6.57 V |
| b9 3S (6560/3936/2624) | 282 s | 3/2/2 | 9/6/7 | 6/7/0 % | 63.5 Hz | 0.47 % | 0 | 9.27 V |
| b9 4S (7832/4699/3133) | 284 s | 3/3/2 | 11/8/8 | 7/10/1 % | 61.5 Hz | 0.40 % | 0 | 12.03 V |

Line at 0.68–0.71 × `wo` on this frame. 4S has the most overshoot; `b0` steps 1.34× / 1.19× against pack-voltage
steps 1.48× / 1.34×, so 4S roll `b0` ≈ 8.8 k would follow the voltage.

### Addendum 2026-09-07b: ground wc 20 on the same axis, and the closed-gate D-gain ordering (PR comment 5570613494)

`wc_g = 20.zip` (SHA-256 `983c3b62bff00b0748f7ed273a26e5cf6d24b647dbbe7a0a67d6487e8ffe4ef3`, exp2 `33004f5c`), two BBLs
gzipped in `b11_tests_20260907/g20/`. 103/140 pitch, `b0` 2500, ground wc 20: three taps 472–632 °/s, each burst
0.41–0.59 s, a motor at 2047 in every burst (applied collective to 546, commanded 0), gate closed. The second log is
40/70 all axes with `b0 = 8964/5378/3586` (8ksal8's values under jmsweng's wc/wo): 8.7 s hover, error medians
23/27/7 °/s, p90 58/87/30, 2 Hz wallow, no rail, motor line 0.2 % — under-controlled (loop gain halved by the
doubled `b0`), not unstable.

Ground tests ordered by the closed-gate loop gains, P = `wc_g²/b0`, D = `2·wc_g·wo/b0` (PID output per °/s):

| craft / axis | wc_g | wo | b0 | P | D | outcome |
|---|---:|---:|---:|---:|---:|---|
| jmsweng 103/140 pitch | 40 | 140 | 2500 | 0.64 | 4.48 | 14 s rock, rails |
| jmsweng 103/140 pitch | 20 | 140 | 2500 | 0.16 | 2.24 | settles 0.4–0.6 s, rails |
| jmsweng 103/140 pitch | 5 | 140 | 2500 | 0.01 | 0.56 | settles ≈ 1 s, no rail |
| jmsweng 99/110 all | 40 | 110 | 5378 | 0.30 | 1.64 | settles 0.3–0.4 s, rails |
| jmsweng 99/110 all | 5 | 110 | 5378 | 0.005 | 0.20 | settles 0.3–0.6 s, no rail |
| 8ksal8 TH3+ pitch | 40 | 90 | 3936 | 0.41 | 1.83 | clean arms (no taps) |
| flyaway arms, flight wc | 103 | 140 | 2500 | 4.2 | 11.5 | lifts |
| flyaway arms, flight wc | 99 | 110 | 5378 | 1.8 | 4.0 | lifts |

The D column orders every outcome (≥ 4 self-sustaining, 1.6–2.2 settles but rails, ≤ 0.6 clean); P is small
wherever it settles. Implemented as ADRC-030b (`adrc_ground_dgain`, exp4 `0aac46b8`): the ground wc is additionally
capped at `dgain · b0 / (2·wo)` per axis, default 1.0.

## Addendum 2026-09-09: @8ksal8's AOS 3.5 V5 — thrust_linear sweep under ADRC (PR comment 5591248669)

Archives `Thrust Linear_sweep_.zip` (`13f584aa51e26d9294e7ffdc63a2855e210ab234054b61243c66ff98f8408af2`),
`Thrust_linear_sweep_dyn_idle_random_.zip` (`3fc9e009720030c4e2afc27c579d36d4abf1c268a3c4526bd859bc5d16986e2b`),
`AOS35_v5_btfl_001.zip` (`0697810f73b9e69feb171573c6ba8eb4fe983b1956bfe4e89510f4fb4963d3eb`); eleven BBLs gzipped in
`8ksal8_aos35_20260908/` (the 125/43 log is 1 s and skipped). AOS 3.5 V5, F405, 1504/3100KV, 4S, exp3 `83a12fc3`,
90/100, `b0 = 7010/4206/2804`, FIXED, hover 5, ground wc 40 / ramp 100, `pid_at_min_throttle` ON. Script `tl.py`
(2-s windows split by median throttle).

`thrust_linear` applies `c(x) = x·(1 + e·(1−x)·(1 + e·(1−2x)))` to the final motor output (`pid.c`
`pidApplyThrustLinearization`). Hover sits at motor ≈ 0.34 after the curve in every log, so the pre-curve operating
point and the slope there (the multiplier every controller output receives) depend on `e`:

| TL | x before curve | gain × at hover | × at 20 % motor | line f | line RMS/motor | overshoot R/P | err p90 R/P | vbat min |
|---:|---:|---:|---:|---:|---:|---|---|---:|
| 10 | 0.318 | 1.03 | 1.06 | 48.3 Hz | 0.84 % | 22/14 % | 11/9 | 14.77 V |
| 25 | 0.284 | 1.09 | 1.18 | 57.5 Hz | 0.76 % | 19/10 % | 12/9 | 14.47 V |
| 60 | 0.207 | 1.36 | 1.61 | 65.5 Hz | 1.53 % | 12/9 % | 9/7 | 13.89 V |
| 75 (dyn idle 111, 292 s) | 0.178 | 1.55 | 1.88 | 64.5 Hz | 3.63 % | 5/7 % | 7/6 | 12.46 V |
| 80 | 0.168 | 1.63 | 1.98 | 65.5 Hz | 5.72 % | 5/8 % | 9/7 | 13.39 V |
| 90 | 0.152 | 1.81 | 2.20 | 65.5 Hz | 7.97 % | 7/9 % | 9/8 | 13.30 V |
| 90 (dyn idle 60, 285 s) | 0.152 | 1.81 | 2.20 | 64.5 Hz | 7.11 % | 6/7 % | 7/5 | 12.15 V |
| 95 | 0.144 | 1.91 | 2.32 | 65.0 Hz | 9.63 % | 6/5 % | 9/7 | 13.20 V |
| 95 (AOS35_v5, 282 s) | 0.144 | 1.91 | 2.32 | 64.5 Hz | 8.46 % | 3/4 % | 6/5 | 13.06 V |
| 100 (dyn idle 43, 125 s) | 0.136 | 2.02 | 2.44 | 64.5 Hz | 11.5 % | 6/9 % | 7/7 | 13.03 V |

Error medians are 2/2 °/s in every log. The line grows ×10 across the sweep with the hover gain multiplier (90/100
at TL 95 ≈ 125/140 without TL, the Air65's over-the-knee region) while overshoot falls 22 → 5 %. The low-throttle
instability the tester reported without TL is the under-gain below hover: the b0 schedule only scales up (FIXED not
at all) while the plant gain at 20 % motor is ≈ half of hover's; TL supplies ×1.6–2.3 there. Dynamic idle 43/60/111
is not separable at equal TL. Candidate ADRC-031: allow the b0 schedule below 1 under hover. Tuning rule: TL is a
gain — fit `b0` with the intended TL, or leave TL off.

## Addendum 2026-09-09b: AOS 3.5 — taking the TL gain back out, and the roll/pitch b0 split (PR comment 5605089162)

Archives `wc_wo_b0_compare.zip` (`b0be5992f02416cdffaf99c080accae455cc7be417e03d317aee370c8f7885da`) and `b0_allocation.zip`
(`9121100a8b85a2d0555789ce52a70e1a7e71ac355279d1beeec9a55abf2dcb74`); five BBLs gzipped in `8ksal8_aos35_20260909/`.
Same craft/build as addendum 7. Script `ov.py`: per-axis peak gyro / peak setpoint on moves above 200 °/s and the
error-to-setpoint ratio on samples above 150 °/s (the flights are gentle — |setpoint| p90 30–65 °/s, two large moves
per log — so the overshoot share alone rests on few samples).

| flight | wc/wo | b0 R/P/Y | TL | line | line RMS/motor | overshoot R/P | roll peak ratio / err ratio | pitch peak ratio / err ratio | vbat med/min |
|---|---|---|---:|---:|---:|---|---|---|---:|
| sweep ref. (add. 7) | 90/100 | 7010/4206/2804 | 95 | 65 Hz | 9.63 % | 6/5 % | 1.14 / 0.04 | 1.08 / 0.04 | 14.88/13.20 |
| Higher_b0 | 90/100 | 13319/7991/5328 | 95 | 52.5 Hz | 0.70 % | 19/5 % | 1.35 / 0.14 | 1.18 / 0.08 | 16.46/15.03 |
| Lower_wc_wo | 64/72 | 7010/4206/2804 | 95 | 49.3 Hz | 0.75 % | 17/11 % | 1.29 / 0.11 | 1.15 / 0.06 | 15.94/14.35 |
| TL_60 | 90/100 | 7010/4206/2804 | 60 | 65 Hz | 1.04 % | 9/8 % | 1.20 / 0.05 | 1.14 / 0.06 | 15.44/14.43 |
| allocation 55/25/20 | 90/100 | 7711/3505/2804 | 60 | 65 Hz | 2.02 % | 9/9 % | 1.20 / 0.08 | 1.10 / 0.05 | 15.11/13.80 |
| allocation 60/20/20 | 90/100 | 8412/2804/2804 | 60 | 66.5 Hz | 0.98 % | 16/7 % | 1.28 / 0.11 | 1.08 / 0.04 | 16.42/14.97 |

Removing the ×1.9 either way (b0 ×1.9, or 64/72) drops the line 9.6 → 0.7 % at unchanged tracking; higher b0 keeps
the observer at 100 and costs roll overshoot, lower wc/wo slows the observer (line 49 Hz) and costs both axes; TL 60
with the fitted b0 is the balance (1.0 %, 9/8). Roll exceeds pitch on both ratios in every flight; both ratios rise
when the loop gain drops and fall when it rises (under-gain = bounce-back). +20 % roll b0 moves roll 1.20 → 1.28 /
0.05 → 0.11 while pitch (less b0) improves 1.14 → 1.08 — consistent with roll wanting a lower b0 than the 50 % split
(squished X: arm ∝ d, roll inertia ∝ d²), low N. The 2 % line of the 55/25/20 flight coincides with the lowest pack
of the set (15.1 V median vs 16.4 V).

## Addendum 2026-09-10: Air65 at 144/160 SQRT — `adrc_hover_throttle` sweep 5…27 (PR comment 5620793842)

Archive `Hover_throttle_sweep.zip` (`6062a27a38595a4bed484ed9c6aecff05ff21b6854637d4714e7d3254d1c9fee`); twelve hover-only
BBLs gzipped in `8ksal8_air65_hover_20260910/`. Air65, exp5 `6143baff`, 144/160, SQRT, `b0 = 8964/5378/3586`,
`adrc_b0_scale_min` 100 (ADRC-031 not engaged), TL 5, ground wc 40 / dgain 10; headers otherwise identical. Scripts
`hov.py` (2-s windows: line vs scale/throttle/pack) and `hov2.py` (1-s windows, burst windows > 5 %, throttle and
scale in burst vs calm windows, 76 Hz gyro amplitude).

True hover is 34–38 % throttle in every log, so the SQRT scale at hover is √(36/hover): 2.69 at hover 5 (debug[7]
agrees), 1.15 at 27. Both P (`wc²/b0`) and D (`2·wc·wo/b0`) scale with 1/b0, so the effective wc/wo is
144/160 ÷ √scale.

| hover | scale at hover | effective wc/wo | line, window median | window p90 | burst windows (>5 %) | throttle in bursts / calm | gyro 76 Hz in bursts |
|---:|---:|---|---:|---:|---:|---|---:|
| 5 | 2.69 | ≈ 88/98 | 0.40 % | 2.1 % | 2/24 | 22 / 36 % | 1.0 °/s |
| 7 | 2.29 | ≈ 95/106 | 0.52 % | 8.1 % | 2/16 | 32 / 38 % | 1.4 |
| 9 | 2.04 | ≈ 101/112 | 0.73 % | 18.5 % | 3/23 | 38 / 37 % | 1.5 |
| 11 | 1.81 | ≈ 107/119 | 0.89 % | 13.2 % | 3/20 | 29 / 37 % | 2.2 |
| 13 | 1.67 | ≈ 111/124 | 1.17 % | 18.5 % | 5/21 | 0 / 37 % | 2.6 |
| 15 | 1.57 | ≈ 115/128 | 1.52 % | 21.9 % | 4/22 | 0 / 38 % | 3.1 |
| 17 | 1.46 | ≈ 119/132 | 3.02 % | 58.8 % | 8/22 | 8 / 37 % | 3.3 |
| 19 | 1.38 | ≈ 123/136 | 1.85 % | 34.1 % | 4/26 | 1 / 36 % | 1.9 |
| 21 | 1.32 | ≈ 125/139 | 2.49 % | 22.7 % | 6/28 | 0 / 37 % | 2.0 |
| 23 | 1.26 | ≈ 128/143 | 2.93 % | 19.6 % | 6/29 | 11 / 37 % | 2.5 |
| 25 | 1.18 | ≈ 133/147 | 3.53 % | 10.1 % | 5/23 | 0 / 37 % | 1.8 |
| 27 | 1.15 | ≈ 134/149 | 3.34 % | 8.0 % | 7/34 | 0 / 37 % | 0.7 |

The baseline line is monotone in the gain (0.40 → 3.5 %). The whole-flight RMS (4.7 % at hover 5, 17–26 % at 13–17,
5 % at 27) is dominated by bursts, and from hover 13 up every burst window sits at zero stick (window line vs
throttle r = −0.9 within a log): chops and landing approaches with airmode, gate open. At zero throttle the schedule
ratio is 0, the scale clamps at 1 and the controller runs on the raw 144/160 until the stick returns; it rings at
75–79 Hz (0.48 × `wo`) with only 1–3 °/s in the gyro — the oscillation lives in the motors. At hover 5 a chop only
takes the scale 2.7 → ≈ 2.2 inside the 80 ms schedule filter, so it passes. Conclusions: (1) hover 5 encodes "gain
÷ 2.7" into the schedule and removes the schedule itself (cap 4 reached at 80 % throttle, nothing below hover for
ADRC-031 to act on); the clean equivalent is hover 36 with 88/98; (2) with airmode the gate stays open on landing
(`adrc_liftoff_idle_hold_ms` 0), so a tune that rings at zero stick in the air rings on the ground until disarm and
the ground wc does not return — disarm on touchdown.

## Addendum 2026-09-11: first `adrc_b0_scale_min` flights (ADRC-031, exp5) — AOS 3.5 at 114/120 (PR comment 5636377477)

Archive `AOS35v5_tuned_b0_min_test_btfl_002.zip` (`fe0443658d7926f9a50cc7ea95771a3342b71b130f1da391cee822aab3671385`);
three BBLs gzipped in `8ksal8_aos35_b0min_20260911/`. AOS 3.5, exp5 `6143baff`, 114/120, `b0 = 4466/3350/3350`
(40/30/30 split), SQRT, hover 35 (true hover), TL 0, ground wc 40 / dgain 10, ESC PWM 48 kHz, `adrc_b0_scale_min`
100 / 70 / 50. Loop gain `wc²/b0` = 2.9, ×2.5 the TL-60 tune of addendum 7 (1.16); calm line 0.33 % with 5-s windows to
4.7 % at min 100, i.e. the tune sits at the knee.

| min | flight | frames scale < 1 | calm line (|sp| p90 < 100) | zero-stick flips (|sp| p90 > 400, thr < 15 %): n, scale, line med/max | moves at throttle: n, line med/max | err R/P | overshoot R/P |
|---:|---:|---:|---:|---|---|---|---|
| 100 | 290 s | 0 % | 0.33 % | 6, 1.00, 5.2 / 9.1 % | 9, 1.3 / 4.0 % | 2/2 | 7/7 % |
| 70 | 246 s | 64 % (p10 0.86) | 0.42 % | 7, 0.70, 6.2 / 11.4 % | 5, 1.6 / 2.9 % | 1/2 | 7/6 % |
| 50 | 41 s | 69 % (p10 0.87) | 0.42 % | 3, 0.65, **37.5 / 40.7 %** (71 Hz = 0.59 × wo) | — | 2/2 | 5/7 % |

70 is benign on this tune (same calm line, same tracking, same flip line as 100; ×1.3 gain at 20 % throttle is the
"locked-in" feel). 50 crosses the knee during zero-stick flips: the scale reaches 0.65 inside the 80 ms schedule
filter, ×1.5 on a tune already at the boundary, and the motors ring for the length of the flip; ≈ 93/98 would absorb
it. Roll bounce-back of addendum 7b is gone with the 40/30/30 split (roll overshoot 5–7 % ≈ pitch). The tester's
"failed RTH" (min-70 log, 80–122 s, FC-held throttle, error 1–3 °/s, one 428 °/s wobble at 90 s) is not a rate-loop
event; `adrc_hover_throttle` is read only by the b0 schedule, GPS rescue / position hold have their own hover settings.

## Addendum 2026-09-13: two Petrel75 2S, three b0 laws — and a metric correction (PR comment 5650057288)

Archives `Petral75_2s_b11_x5_.zip` (`1e3c863da867c54e0fbdc702cb2123ff3ac904c4e985aee67fa8bec561386473`) and
`HDZ_Petrel75_2s_b11_x5_b0_law_1_2_3_LOG167.zip` (`b4a1a9d3e11e02ba990537918354c3d4ffa3d6bd5e7fcefb3239618de94b0ab1`,
one SD `.TXT` holding three logs, split on the `H Product:` marker — each fragment is byte-identical to its slice and
decodes with 0 failed frames). Six BBLs gzipped in `8ksal8_petrel75_20260913/`. Both crafts: exp5 `6143baff`, 95/100,
`adrc_hover_throttle` 38 (Petrel75 #1) / 43 (HDZ), TL 0, `adrc_ground_wc` 10 + `dgain` 4.0, SQRT and LINEAR at
`adrc_b0_scale_min` 85, FIXED at 100.

### Metric correction (applies to the earlier addenda)

The "motor line" of addenda 3–8 is the strongest peak in **40–80 Hz**. On these two crafts the dominant oscillation is
at **28–33 Hz**, below that window, so the earlier statistic missed it entirely and the first version of this analysis
wrongly concluded the flights were quiet and the laws indistinguishable. Re-checked the earlier campaigns with a wide
band sweep (25–38 / 38–55 / 55–70 / 70–90 Hz): the Air65 `wc/wo` sweep (55–70 Hz dominant, 22.5 % at 106/120), the AOS
3.5 TL sweep (55–70, 10.2 % at TL 95) and the Air65 hover sweep (70–90, 5.7 → 45.9 %) all have their dominant content
inside 40–90 Hz, so those conclusions stand; only the absolute magnitudes were understated by the ±2 Hz band. **From
here on: search 15–120 Hz, report the band, and use the p90 across windows as well as the median** — the oscillation
here is intermittent and the median hides it.

### What the six logs show, 25–38 Hz motor RMS per motor

| log | law | floor | whole flight | worst-20 % windows: line / scale / thr / vbat | matched windows (thr 42–50 %, no rail): n / median / p90 / scale | worst axis: gyro RMS vs setpoint RMS |
|---|---|---:|---:|---|---|---|
| Petrel75 #1 SQRT | 1 | 85 | 3.19 % | 2.14 % / 1.10 / 45 % / 8.07 V | 37 / 0.53 / 1.29 % / 1.08 | pitch 2.86 vs 0.28 °/s |
| Petrel75 #1 LINEAR | 2 | 85 | 1.09 % | 1.56 % / 1.03 / 38 % / 7.74 V | 18 / 0.51 / 0.82 % / 1.15 | pitch 0.76 vs 0.41 |
| Petrel75 #1 FIXED | 3 | 100 | **11.38 %** | **14.01 %** / 1.00 / 45 % / 7.38 V | 7 / 0.68 / **3.94 %** / 1.00 | pitch **7.86** vs 0.43 |
| HDZ SQRT | 1 | 85 | 1.32 % | 1.85 % / 0.99 / 44 % / 8.13 V | 44 / 0.92 / 1.45 % / 1.04 | roll 1.66 vs 0.38 |
| HDZ LINEAR | 2 | 85 | 1.16 % | 1.48 % / 0.94 / 40 % / 7.58 V | 38 / 0.87 / 1.22 % / 1.06 | roll 1.34 vs 0.52 |
| HDZ FIXED | 3 | 100 | **4.88 %** | **6.25 %** / 1.00 / 50 % / 7.19 V | 33 / 0.85 / **1.70 %** / 1.00 | roll **6.03** vs 0.45 |

Both FIXED flights carry a self-excited oscillation: gyro RMS 6–8 °/s in the band against setpoint RMS 0.4 °/s, i.e.
not commanded. It is present without rail clipping — a hover window at 42.3–44.3 s of the Petrel FIXED flight has no
motor at 2047, median throttle 43.8 %, 14.08 % motor RMS in the band and pitch gyro RMS 10.7 °/s against pitch
setpoint RMS 0.17 °/s. Whole-flight line energy does coincide with rail segments (99.6 % / 96.6 %), but that is
timing, not causality: the law can excite the oscillation which then rails the motors.

Mechanism, measurable in the same windows: at throttle 42–50 % with hover 38–43 the two schedules run `b0` 4–15 %
above its fitted value (scale 1.04–1.15) while FIXED runs it at exactly 1.00, so the schedules fly 4–15 % below the
loop gain FIXED uses, and these tunes sit close enough to the boundary for that to decide whether the mode is
excited. Note the floor moves the other way (85 raises the gain below hover) and the oscillating windows are *above*
hover, so the floor cannot be the cause.

### What this set cannot settle

Flight order is confounded with pack depletion in both sets: SQRT → LINEAR → FIXED, with median vbat 8.16 / 7.72 /
7.49 V and 8.02 / 7.57 / 7.22 V, and the starting voltages already differ (8.88 / 8.17 / 7.81 V, 8.57 / 7.96 /
7.60 V). Sag lowers thrust per command, which raises the true loop gain by itself. On the Petrel set the SQRT flight
also ran `dyn_idle_p/i/d` 25 against 50 in the other two; the HDZ set has no settings confound (identical filters,
dyn idle 50, only law and floor differ). A clean answer needs the law order reversed on a comparable pack.

`adrc_b0_scale_min` 85: the set has no floor-70 flight, so it does not test the tester's "70 floats, 85 does not";
the longest continuous zero-throttle stretch is 0.9–1.2 s. At throttle < 5 % the mean motor output is 416–469 and the
median applied collective 63–91 of 1000 (6.3–9.1 %) in all six, with no ordering by floor. Note also that the floor
scales the ADRC P/I/D only — `pid.c` adds a feedforward term that is not divided by `b0` (max |axisF| 160–224 here).

`adrc_ground_dgain` 4.0 with ground wc 10: the per-axis cap is `dgain·b0/(2·wo)` = 57–97 rad/s, far above 10, so it
never binds and these flights do not exercise it. The closed-gate `G_D` = `2·wc·wo/b0` is 0.41–0.70 per axis
(0.72 for the Petrel pitch axis with the Euler correction at this dT) — the pitch axis is at or just above the ≤ 0.6
"settles clean" boundary of `docs/ADRC_GAIN_GUIDE.md`, which was drawn on Air65 tap tests, and no tap test was flown
on these crafts.

Decoder note: `blackbox_decode` in `.scratch/tools/blackbox-tools` misreads a numeric `H P interval:4` header
(expects `1/4`), which corrupts `loopIteration` and the "frames missing" statistics. All 65 other columns, timestamps
included, are unaffected, so the spectra above stand; do not quote frame statistics from these decodes. Actual PID
`dT` here is 250 µs (gyro 125 µs, `pid_process_denom` 2); the logged rate is ~1 kHz.


## Correction 2026-09-13 to the addendum of 2026-09-10 (Air65 hover sweep)

That addendum measured the motor line with the 40–80 Hz peak search. On that craft at `wo` 160 the mode peaks at
**75.5–86 Hz** and moves up with the hover setting, so the top of the window clipped it and the reported amplitudes
were an order of magnitude low. Recomputed over 70–90 Hz (`bands.py`), whole flight after the gate and per 1-s
window, per-motor RMS over mean motor output:

| hover | peak | whole flight | windows > 5 % | of those, throttle > 15 % | window median / worst tenth | b0 scale in the loudest windows |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 76.5 Hz | 5.5 % | 2/24 | 2 | 0.63 / 4.7 % | 2.22 |
| 7 | 75.5 | 7.5 % | 2/16 | 2 | 0.77 / 14.1 % | 2.10 |
| 9 | 75.5 | 8.6 % | 4/23 | 3 | 1.03 / 10.1 % | 1.90 |
| 11 | 75.5 | 10.8 % | 4/20 | 3 | 1.44 / 30.2 % | 1.62 |
| 13 | 76.0 | 18.7 % | 5/21 | 2 | 1.85 / 56.4 % | 1.33 |
| 15 | 76.5 | 19.5 % | 4/22 | 0 | 2.31 / 59.4 % | 1.31 |
| 17 | 76.5 | 26.8 % | 10/22 | 6 | 4.62 / 51.8 % | 1.35 |
| 19 | 76.5 | 19.0 % | 10/26 | 7 | 4.06 / 35.1 % | 1.32 |
| 21 | 79.0 | 23.0 % | 16/28 | 11 | 5.62 / 71.2 % | 1.26 |
| 23 | 86.0 | 27.7 % | 18/29 | 15 | 5.54 / 60.6 % | 1.25 |
| 25 | 85.5 | 40.6 % | 18/23 | 13 | 15.5 / 75.8 % | 1.18 |
| 27 | 82.0 | 46.4 % | 32/34 | 25 | 45.2 / 79.3 % | 1.17 |

Three statements in that addendum do not survive:

- **"The baseline climbs 0.40 → 3.5 %"** — it climbs 5.5 → 46 %, monotonically; at hover 25–27 the craft oscillates
  in most windows of the flight rather than occasionally.
- **"From hover 13 up every burst window sits at zero stick"** — at hover 27, 32 of 34 windows exceed 5 % and 25 of
  those have median stick throttle above 15 %.
- **"At zero throttle the scale clamps at 1 and the raw 144/160 is exposed"** — the schedule keys on a 2 Hz low-pass
  of the applied collective, not on stick throttle; in the zero-stick windows `debug[7]` reads 1.06–1.32, never 1.00.

What survives, better supported: the amplitude tracks the b0 scale, i.e. the loop gain. The scale in the loudest
windows falls 2.22 → 1.17 across the sweep as the amplitude rises, and `adrc_hover_throttle` 5 on a craft whose real
hover is ≈ 36 % is what held the scale at 2.2 and kept the tune quiet. The further claim that hover 5 at 144/160 is
"the same as 88/98" is withdrawn: equal loop gain is not equal dynamics, because `wo` also sets the frequencies.

## Addendum 2026-09-14: Petrel75 pair on separate packs, tap tests at two dgain values, `adrc_b0_scale_min` sweep — and an exp5 bug (PR comments 5657097336, 5663653554)

Fifteen BBLs gzipped in `8ksal8_petrel_20260914/` (SHA-256 in `SHA256SUMS`; the HDZ flight and tap archives were
single multi-log `.TXT` files split on the `H Product:` marker, byte-identical fragments). Both crafts exp5
`6143baff`, 95/100, ground wc 10. Methodology: `bands.py` (10–150 Hz peak search, 1-s windows, median and worst
windows); events located by the maximum |pidSum| after the gate and read on 100 ms timelines.

### exp5 bug: `adrc_b0_scale_min = 20` acted as off

`b0min_20_btfl_007`: gate open, seven zero-stick intervals of 0.34–0.60 s with applied collective 1.0–6.6 % (raw SQRT
schedule ≈ 0.16–0.23), logged scale 1.00 throughout; the D output implies a divisor of `b0 × 1.0`. Floors 30/40/50/70/80
engaged exactly (logged minima 0.37 / 0.40 / 0.50 / 0.70 / 0.80). Host reproduction with the firmware's flags
(`-O2 -ffast-math -flto -fmerge-all-constants`): `20 × 0.01f` = 0.19999999 < 0.2f, and the clamp-to-floor followed by
the "below floor → reset to 1.0" sanity check folds into a reset; without `-ffast-math` the result is 0.2. Fixed in
`80b790bc` (b11-exp6): integer decision on the setting, sub-floor values clamped up. The tester's "20 seems to do
nothing" was correct; the first explanation offered here ("the craft's idle collective never gets low enough") was
wrong and is withdrawn.

Binding share of frames after the gate: floor 40 0.2 %, 50 4.6 %, 70 14 %, 80 12 %. Raw schedule minima reached in the
zero-stick stretches: 0.37–0.44 (the schedule keys on a 2 Hz low-pass of the applied collective; chops of 0.3–0.7 s do
not take it further). Whether floors below 40 ever bind on this craft is untested (the floor-20 flight is the bug case).

### Events (five of the eleven flight logs)

| log | when | what the log shows | reading |
|---|---|---|---|
| `HDZ_SQRT_h43` log 1 (5.4 s) | gate at 2.63 s (gyro path, 30 % collective) | roll setpoint −150…−170 °/s for 0.31 s before the gate; after it the roll rate reaches the setpoint within 200 ms while ground wc ramps to flight wc and the scale drops to 0.85; tracking break at +0.24 s (gyro −65/−54 vs setpoint −248/+50, motors 1709/1103/847/48); 11.2 g at +1.11 s with roll 2626 °/s; then 9–10 g impacts, pitch to 2847 °/s, pidSum demand to 12 972; ends tilted (roll ≈ −164°) with motors 336/1307/755/892 | deflected stick at arm and a liftoff transition are both in the log; cause not assignable without the tester's account |
| `PET_SQRT_1` | +123.88…124.07 s | roll rate 178 → 946 °/s over 0.3 s while roll setpoint falls 113 → 66; motors 2009/1805/1805/348, eRPM 3390/3371/3158/480–510 (motor 4 low with its command); accelerometer to 5.19 g; 195 frames over a pidSum limit; recovers; log is exactly 16 MiB with no clean end (flash limit is the likely reason) | loss of authority on one corner; contact / prop damage / un-commanded transient not separable from the columns |
| `HDZ_SQRT_h43` log 2 | last 0.1 s, +264.8 s | calm 38–45 % hover, then 6.28 g, roll/pitch −826/+760 °/s, pidSum 3317/3941, a motor at 2047; log ends there ("clean end" = logging closed, not a landing) | impact-like; context unknown |
| `b0min_30` / `b0min_70` | +16.66 s / +25.14 s | throttle to 63 % / 49 %, chop to 0, 0.28 s / 0.15 s below 0.3 g (median ≈ 0.06 g), then 5.13 g / 5.65 g with pitch 1229 / 961 °/s and pidSum 10 359 / 9 134 (any-axis over limit 34–35 ms in total, above 9 000 for 1–3 ms); stick stays at 0 for ≈ 0.4 s after the peak and the demand has decayed before throttle returns; normal flight follows | consistent with the tester's drop test reaching the ground with the gate open (gate closes only on disarm or a controller-epoch reset in this build); surface and sequence to be confirmed |

`b0min_80` also has a 6.23 g peak at +17.2 s with a small angular response (pitch ≤ 182 °/s).

### Matched-pack law pair (25–38 Hz, per-motor RMS over mean motor output)

| flight | whole | window median / p90 / max | matched 42–50 %, no rail: n / med / p90 / scale | worst axis gyro vs setpoint | rail | mean A | 38–55 whole |
|---|---:|---|---|---|---:|---:|---:|
| HDZ FIXED (hover 5, floor 100) | 3.51 % | 0.66 / 2.37 / 17.3 % | 142 / 0.64 / 1.16 / 1.00 | roll 4.32 vs 0.30 | 1.19 % | 5.95 | 1.06 % |
| HDZ SQRT (hover 43, floor 85) | 1.07 % | 0.75 / 1.47 / 3.5 % | 166 / 0.73 / 1.16 / 1.02 | roll 1.35 vs 0.31 | 0.83 % | 6.08 | 1.83 % |
| PET FIXED (hover 5, floor 100) | 1.06 % | 0.55 / 1.32 / 6.6 % | 99 / 0.56 / 0.87 / 1.00 | roll 0.91 vs 0.23 | 0.77 % | 5.63 | 1.37 % |
| PET SQRT (hover 38, floor 70) | 0.82 % | 0.54 / 1.09 / 4.7 % | 126 / 0.53 / 0.71 / 1.08 | roll 0.63 vs 0.24 | 0.49 % | 5.66 | 0.69 % |

Against the back-to-back single-pack session (addendum 2026-09-13: PET FIXED 11.38 %, HDZ FIXED 4.88 %) the FIXED
numbers fell to 1.06 % and 3.51 %. Law and pack state were confounded in that session; this pair still differs in floor
and hover, day and flying, one flight per cell, and the 38–55 Hz ranking is reversed on the HDZ only. No law effect is
identified. Under FIXED the schedule returns 1.00 and the floor cannot apply, so the two FIXED flights are
configuration-identical to FIXED at any hover/floor.

### Tap tests (gate closed, stick at idle)

Effective ground wc `min(10, dgain·b0/(2·wo))`: dgain 4.0 → 10/10/10; dgain 0.4 → HDZ 9.71/7.28/7.28, PET 8.92/5.72/8.23
(the cap binds on all axes, removing 27–43 % of the pitch D gain). 7/8/8/9 excursions above 30 °/s, longest
0.47/0.52/0.57/0.50 s, peak gyro 690/991/722/830 °/s, max motor 1035/1092/1201/811, applied collective to 25/25/30/21 %,
gate never opened, no motor at 2047 (lower endpoint 48 reached in 0.35–1.0 % of frames). Not all decays are monotone
(e.g. 319 → 552 → 547 °/s in one PET tap); a second hand contact cannot be excluded without video.

### Addendum 11, follow-up 2026-09-15: the tester's account of the five events (PR comment 5671567863)

1. HDZ takeoff crash: an ESC problem — a motor sometimes stopped on arm before the throttle was raised, the craft
   flipped on takeoff; fixed by an ESC setting. Not a controller event.
2. Petrel +124 s: the tester calls it "yaw washout", seen on whoops with classic PID too. The log agrees with the
   mechanism: in the second before the departure all three axes demand at once (z3/b0 roll/pitch ±670, yaw −533
   against `pidsum_limit_yaw` 400), the mixer saturates (motors 2009/1843/1843/348) and roll can no longer be held
   (demand −1736, rate 170 → 946 °/s against setpoint 120 → 60) while the yaw rate error never exceeds 245 °/s. On
   classic PID the usual fix is more yaw P/I with D = 0; ADRC's yaw law carries `D = 2·wc·z2/b0` at critical
   damping, so raising yaw `wc` raises yaw D with it. Per-axis `adrc_wc_yaw` / `adrc_wo_yaw` / `adrc_b0_yaw` exist
   (the tester had 95/100 on all axes). Candidate ADRC-032: a per-axis damping ratio ζ (`D = 2·ζ·wc·z2/b0`).
3. HDZ log end: hover at 38 % stick, then within the last 20 ms 6.3 g and roll/pitch 826/653 °/s, then the frame
   with the armed bit cleared (motors 48/1293/1293/2047). Impact and disarm within one frame interval; the tester's
   "runs a little longer after disarm" is not observable in Blackbox (recording stops at disarm).
4. `b0min_30/70`: drop tests that reached the floor and the ceiling — confirmed. `adrc_ground_dgain` 4 was set by
   accident (back to 40); `adrc_hover_throttle` 5 under FIXED was set "to be sure" (inert under FIXED).

## Addendum 12, 2026-09-16: four more "yaw washout" logs — ESO windup on all three axes while the mixer cannot deliver the command (PR comment 5684488326; reply 5693798017)

Six flights on b11-exp6 (80b790bc), Petrel75 2S, `pidsum_limit` / `pidsum_limit_yaw` raised 500/400 → 1000/1000 by
the tester in this batch; logs in `8ksal8_petrel_20260915_yawwash/` (SHA256SUMS). Scripts: `wash.py` (event finder,
per-flight summary), `sat.py` (saturation episodes, I-term growth, recovery time), `washtl.py` (timeline around an
instant). `blackbox_decode` misreads this header's `P interval`, so its frame statistics are wrong; the columns are fine.

| log | wc/wo (r,p / y) | b0 (r,p,y) | scale_min | ground wc / dgain | length | vbat start → end | events \|err\| > 350 °/s | both-end saturation ≥ 30 ms |
|---|---|---|---:|---|---:|---|---:|---:|
| yaw_washout_004 | 95/100 / 120/100 | 41,26,38 | 70 | 40 / 1.0 (set by mistake, per tester) | 147 s | 8.06 → 7.27 | 3 | 2 |
| b0min70_wc_110_001 | 95/100 / 110/100 | 41,26,38 | 70 | 10 / 4.0 | 296 s | 8.83 → 7.28 | 2 | 5 (one event) |
| wc_wo_110_120_004 | 95/100 / 110/120 | 41,26,38 | 70 | 10 / 4.0 | 154 s | 8.06 → 7.17 | 2 | 2 |
| 117_123 btfl_017 | 117/123 all | 41,26,38 | 95 | 10 / 4.0 | 75 s | 8.84 → 8.13 | 1 | 1 |
| 117_123 btfl_018 | 117/123 all | 44,28,41 | 95 | 10 / 4.0 | 69 s | 8.34 → 7.77 | 1 | 2 |
| 117_123 btfl_all log 1 | 117/123 all | 45,29,42 | 80 | 10 / 4.0 | 231 s | 8.83 → 6.72 | 3 (last = crash) | 5 |
| 117_123 btfl_all log 2 | 117/123 all | 45,29,42 | 80 | 10 / 4.0 | 65 s | 7.71 → 7.16 | 0 | 0 |

"Both-end" = a motor pinned at the ceiling (2047, or a flat plateau ≥ 1900 — `vbat_sag_compensation` 100 lowers the
ceiling on a fresh pack) and another at the floor (≤ 350) in the same frames, gate open.

### The four washouts, frame by frame

yaw_washout_004 at 46.0 s (`washtl.py <csv> 46.0 1.2 40`):

1. **Zero-throttle phase, 0.7 s.** Stick at 1000, `adrcState` 67 (liftoff | throttle_idle), motors ≈ 1000/800/950/316
   — airmode holding attitude with one motor on the idle floor. All three I terms (`z3/b0`) are non-zero and drifting
   (roll −68 → −92, pitch 116 → 138, yaw 61 → 103) with gyro error under 10 °/s: whatever needs the low motor to go
   lower is not delivered, and the observer books the shortfall as disturbance.
2. **Throttle rise with forward pitch.** Throttle 1000 → 1317 in 0.4 s, setpoint pitch −180, roll −50. The pack sags
   7.6 → 6.88 V at 21 A; at 45.80 s motor 3 reaches 2047 while motor 4 is still at 348: both ends pinned.
3. **Windup, 160 ms.** Roll I −145 → −888, pitch 245 → 982, yaw 195 → 976 between 45.80 and 45.96 s (up to
   4 600 units/s on one axis). The clamp is `pidsum_limit` per axis (now 1000). pidSum roll/pitch reach −1 589 / +3 400
   (log column ÷ 10) — each alone exceeds the whole motor range.
4. **Departure and recovery.** Roll +403 → +562 °/s against setpoint −38, then pitch −894 °/s against −48; yaw error
   peaks at 325 °/s. The I terms unwind at the rate they charged; roll/pitch error stays under 100 °/s again 0.68 s
   after the saturation began. No crash.

b0min70_wc_110 at 119.9 s and wc_wo_110_120 at 134.2 s repeat this: a zero-throttle phase (I terms 60–250 on all
axes), throttle rise into a sagged pack (6.9–7.2 V under load), both ends pinned, windup to 860–1000 on all three
axes, roll/pitch excursions of 733 and 540 °/s, yaw error 188 and 387 °/s, recovery 0.76 and 0.64 s.

btfl_018 at 43.1 s is the same windup from a different entry: a punch to 1970 with the roll stick at −250 and the pack
at 7.1–7.2 V, then the stick released (42.78–42.82 s). Motor 1 sits on a flat 1957–2018 plateau (the sag-compensated
ceiling) while motor 3 goes to 48 at 42.80 s; from there roll/pitch I go −75/−98 → −760/−858 in 100 ms (7 600/s on
pitch) and yaw 157 → 398, then the excursion (pitch −735, roll 545, yaw 806 °/s — here yaw is the largest), recovery
0.24 s. And btfl_all log 1 at 37.3 s is the full-throttle variant: stick at 2000 for 0.3 s, three motors on the
ceiling with the fourth free (861–991), pitch I charged to the clamp (−1000), pitch excursion 1 379 °/s against a
setpoint of −142. At full throttle the ceiling alone pins the mixer; no floor contact is needed.

Across the seven flights (`sat.py`): every both-end episode ≥ 90 ms and the one full-throttle ceiling episode ended in
a roll/pitch excursion of 449–1 379 °/s; top-only episodes below full throttle (5–32 per flight, seconds in total)
never exceeded 192 °/s, floor-only episodes never exceeded 171 °/s outside the events above. The windup needs the
command to be undeliverable on all axes at once.

Event at 39.5 s of b0min70 (pitch 1 793 °/s): a zero-throttle pitch flip (setpoint 560 °/s for 0.4 s, motors ≈ 300),
then a one-frame jump to 1 727 °/s with the pack dropping 8.46 → 7.44 V — impact-like, not the sequence above. The
btfl_all log 1 ending (229.9–230.8 s) likewise: gyro to −1 905/−1 236 °/s within one 40 ms frame at sticks
−121/−59/132, pack 7.29 → 6.71 V, a one-frame controller reset (P/I/D all zero) 0.5 s later, then a tumble to the
end of the log at 6.0–6.1 V. Whether it hit something at 229.9 s only the tester can say.

### The `pidsum_limit` raise

The z3 anti-windup bound is `pidsum_limit · b0_eff` per axis (adrc.c, "Anti-windup" block), so `|I| ≤ pidsum_limit`:
on 14 Sep (limits 500/400) the washout in `PET_SQRT_1` (126.5 s) clamped exactly at 500/500/400; here the I terms
reach 860–1000. The excursion size did not follow the clamp: 901 °/s on 14 Sep against 540–847 °/s here. The limit
sets how far the integrators wind, not whether they do, and the excursion is driven by the P term (roll/pitch P
2 200–6 800 at the peaks) once the craft is already moving. No recommendation on the limit follows from these logs.

### What it is not

- Not yaw gain: the events occur at yaw wc/wo 120/100, 110/100, 110/120 and 117/123 alike. Yaw winds up like the
  other two axes and, having the least authority, stays at the clamp longest (46.08–46.20 s at 1000 while roll/pitch
  unwind), which is what makes the event look like a yaw problem; in btfl_018 the yaw excursion is in fact the largest.
- Not the b0 floor: 70, 80 and 95 alike.
- Not ground wc: 10 or 40, dgain 1.0 or 4.0, same pattern.
- Not D: at the peaks D is 55–380 against P of 2 200–6 800; the exp7 damping ratio (ADRC-032) does not enter this loop.

### Mechanism, in controller terms

Classic Betaflight's I term grows at `Ki · error` (order 50–100 units/s at these errors); z3 grows at
`β3 · errorEso = wo³ · errorEso`, at the observer's own bandwidth, on every axis whose command is not delivered.
While the mixer is pinned that is all three axes at once, to the clamp in 100–160 ms. The controller is told
`u = constrain(pidSum, ±pidsum_limit)` (pid.c `pidUpdateAdrcAppliedOutput`), not what the mixer delivered
(`motorMixRange` ≥ 1 is deliberately not folded into u — the 2026-07-12 A/B showed that scaling u by the mixer
normalisation over-gains the loop). The ground gate already has the missing conditional (`inhibitZ3Growth`: admit the
observer-error term only when it moves z3 toward zero). Candidate ADRC-033: extend the inhibit to
`!liftoff || mixerSaturatedPreviousLoop`, with `mixerSaturated = motorMixRange ≥ 1` published by the mixer next to the
applied output. Opt-in for A/B, default off, no PG change.

### What the 117/123 set shows

btfl_all log 2 (65 s, the tester's "best") has no event and no both-end saturation, on a pack already at 7.7 V.
btfl_017 (fresh pack, same gains) has one 438 °/s roll excursion at 29.0 s with the I terms at 903–984 on all axes
before it; btfl_all log 1 (same gains) has the full-throttle event and the crash. The gain change is not what
separates the good flight from the others; the manoeuvres (zero-throttle into a punch, full-throttle punches, on a
sagging 2S) are.

## Addendum 13, 2026-09-16: exp8 A/B — `adrc_sat_z3_inhibit` OFF/ON, and a `adrc_zeta_yaw` 100/50/0 sweep (PR comments 5697366799, 5698224382; reply 5699641368)

Six flights on b11-exp8 (e6511d6a), Petrel75 2S, 117/123 all axes, b0 45/29/42, scale_min 80, ground wc 10 / dgain
4.0, td 140, limits 1000/1000. Logs in `8ksal8_petrel_20260916_exp8_ab/`. Inhibit activity is read directly from
`adrcState` bits 4|8|16 (`z3_inhibited_rpy`), so "did the flag act" is measured, not inferred.

| flight | flag | ζ yaw | length | vbat start → end | inhibit-active frames (air) | both-end frames | max \|I\| r/p/y | max \|I\| while pinned | excursions > 350 °/s | recovery |
|---|---|---:|---:|---|---:|---:|---|---|---:|---|
| inhibit_off | OFF | 100 | 175 s | 8.84 → 7.55 | 0 | 1 057 | 995 / 1000 / 1000 | 995 / 1000 / 1000 | 2 (395, 675) | 0.27 / 0.63 s |
| inhibit_on | ON | 100 | 143 s | 8.76 → 7.74 | 166 | 206 | 183 / 252 / 257 | 183 / 239 / 251 | 0 | — |
| zeta_yaw_100_1 | ON | 100 | 73 s | 8.81 → 8.06 | 1 | 13 | 162 / 255 / 241 | 135 / 254 / 206 | 0 | — |
| zeta_yaw_50 | ON | 50 | 65 s | 8.30 → 7.75 | 18 | 18 | 166 / 225 / 202 | 11 / 72 / 31 | 0 | — |
| zeta_yaw_0 | ON | 0 | 51 s | 7.94 → 7.53 | 633 | 893 | 212 / 251 / 310 | 196 / 251 / 282 | 1 (688) | 0.34 s |
| zeta_yaw_100_2 | ON | 100 | 85 s | 7.76 → 7.27 | 76 | 163 | 176 / 285 / 193 | 175 / 274 / 193 | 1 (907, full throttle) | 0.12 s |

### The flag does what it was built to do

OFF reproduces addendum 12 exactly: at 164.0 s a 0.56 s both-end pin charges the I terms 156/254/189 → 995/1000/1000,
excursion 675 °/s, recovery 0.63 s; at 35.3 s a shorter one (542/771/681 → 864/949/1000, 395 °/s). ON, same tune,
same pack state, same session: the inhibit fired in 166 frames, the I terms never exceeded 257 on any axis, no
frame of the flight has a roll/pitch error above 350 °/s, and the both-end frame count fell 5× — the windup was
itself what kept the mixer pinned. Both-end pins still happen (206 frames), but they now end as soon as the
manoeuvre ends instead of after the integrators unwind.

### What remains, and why it is not the controller

Two excursions survive with the flag ON, both with the I terms flat (inhibit active, `adrcState` 93):

- `zeta_yaw_0` at 27.06 s: the addendum-12 entry (1.0 s at zero throttle, then throttle 1000 → 1476 with pitch
  −65), pack 6.8–6.9 V under load, motor 3 on 2047 and motor 4 on 348 for 0.5 s. I terms stay at −139/244/204
  throughout; the excursion (roll 659, pitch −739, yaw −264 °/s) is carried by P alone (pidSum roll −6 241 /
  pitch +7 933 / yaw +4 731 at the peak) and ends 0.34 s after the pin began. With the ceiling reached at ~1 300 of
  stick on this pack there is simply no differential authority left; the observer no longer makes it worse.
- `zeta_yaw_100_2` at 17.63 s: full stick (2000) on a pack at 6.4–6.7 V under load, motors 2047/48/149/281 for
  50 ms, excursion 907 / 846 °/s (roll-pitch / yaw), I terms ≤ 168, recovery 0.12 s.

The tester's "washout at ζ yaw 0" is the first of these. It is one event on the most depleted pack of the sweep
(`vbatref` 796 against 885/833/778), with the yaw I term at 204 and yaw D absent by construction; nothing in it
points at ζ rather than at the pack and the manoeuvre. n = 1 per ζ value on different pack states, so the sweep
cannot rank 100/50/0 either way; the tester feels no difference between them.

### Open

The trade-off written into ADRC-033 (a real disturbance arriving while the mixer is pinned is learned late) has not
been exercised: the pinned intervals here are 50–560 ms and end with the manoeuvre. The tester has not flown a
scenario that would test it and intends to. Default stays OFF until someone has.

## Addendum 14, 2026-09-16: Air65 (1S) on exp8 with the inhibit ON — the same picture on a second craft (PR comment 5700091124; reply 5700665475)

Two flights, Air65 1S, wc/wo 97/110, b0 89/53/35, ground wc 10 / dgain 4.0, td 120, limits 500/1000, flag ON in
both. Logs in `8ksal8_air65_20260916_exp8/`. The tester: "it happened on my Air65", then with ζ yaw 50 and yaw
wc/wo 114/120 "could not duplicate".

| flight | ζ yaw | yaw wc/wo | scale_min | length | vbat start → end | inhibit frames (air) | both-end pins ≥ 30 ms | max \|I\| r/p/y | excursions > 350 °/s | motor at 2047 |
|---|---:|---|---:|---:|---|---:|---:|---|---:|---:|
| btfl_003 | 100 | 97/110 | 80 | 120 s | 3.90 → 3.42 | 725 | 3 (0.27 / 0.15 / 0.32 s) | 169 / 208 / 324 | 1 (480, 0.51 s) | 1.7 % |
| btfl_005 | 50 | 114/120 | 100 | 135 s | 4.14 → 3.35 | 45 | 1 (0.06 s) | 152 / 238 / 237 | 1 (712, 0.14 s) | 11.4 % |

**btfl_003 at 92.3 s** is the Petrel entry on a 1S: pitch −130 at throttle 1108 → 1400, pack 3.2 → 3.1 V under
load, motor 0 on 2047 from 91.98 s and motor 1 on the 305–348 floor for 0.32 s. The inhibit is active the whole
time (`adrcState` 93) and the I terms sit at 92/143/−280; roll drifts to −479 °/s on P alone (pidSum roll +2 424
with motor 0 pinned) and is back under 100 °/s 0.5 s after the pin began. The two other pins in this flight (0.27 and
0.15 s, I terms flat) ended at 261 and 145 °/s. Three pins of 150–320 ms without windup, on a craft whose I limit
is 500: this is what the flag was for.

**btfl_005 at 128.95 s** is not that event: within one 20 ms frame gyro roll goes +3 → −241 → −706 and the motors
jump 1629/920/1343/1128 → 698/48/2047/356 with no stick input (setpoint 1/−35/−86 → 0/−31/−74), then a frame with
all three I terms at zero and P intact — the same one-frame I clear seen at the btfl_all crash and consistent with
an impact-triggered clear (`crash_recovery` state not in this header line set; treated as unknown). Recovery 0.14 s.
"Could not duplicate" holds for the manoeuvre; this excursion is something else. The flight also changed three
things at once (ζ yaw 50, yaw wc/wo 114/120, floor off) and spent 11.4 % of its airtime with a motor at 2047 on a
pack ending at 3.35 V, so nothing about ζ or the yaw gains can be read from it.

Both flights: the I terms never exceed 324 through 770 inhibited frames; every pin ends with the manoeuvre. What
remains on a 1S at 3.1–3.2 V under load is the ceiling, as on the Petrel.

## Addendum 15, 2026-09-17: Pavo20 Pro (3S, F405) on exp8 with the flag ON — a no-op for 230 s (PR comment 5716907562; reply 5719036744)

One flight, 231.6 s, wc/wo 72/110, b0 32/20/48, SQRT law, hover 38, scale_min 100, ground wc 10 / dgain 4.0, td 0,
limits 500/400, `adrc_sat_z3_inhibit` ON, pack 12.38 → 10.03 V. Log in `8ksal8_pavo20_20260917_exp8/`.

- **0–230 s:** the inhibit never fires (0 of 222 846 airborne frames), although a motor touches ≥ 2040 in 862 frames —
  the mixer reaches the ceiling without reporting a clip (inferred from the inhibit bits: the mask is set only when z3 growth is actually suppressed), which is exactly the case the flag must
  leave alone. Roll/pitch error: max 151 °/s, p99 51 °/s, no frame above 350; max \|I\| 118/254/118. This is item 3 of
  the verification plan (a craft whose mixer does not pin: ON must change nothing) on a third airframe.
- **230.53 s to the end:** within one 40 ms frame gyro roll goes +42 → +279 °/s with the sticks at −4/−5/77, current
  10 → 33 A, pack 10.27 → 9.0 V; then a tumble (roll 765, pitch 788, yaw −954 °/s) with two frames of cleared I terms,
  back under control by 231.1 s. The inhibit is active in 346 frames here and the I terms stay ≤ 198. Impact-shaped;
  the log ends 0.5 s later.

The tester's note that DJI O4 RockSteady is smooth across the throttle range on ADRC is an observation about
gyro-band vibration, not something this log can confirm or refute.

## Addendum 16, 2026-09-18: three more OFF/ON pairs on exp8 — Petrel75, HDZ Petrel75, TH3 (PR comment 5724465769; reply 5726524574)

All on e6511d6a. `absum.py` prints, per flight: inhibit frames (from `adrcState` bits 4|8|16), both-end pins, max \|I\|,
frames with roll/pitch error > 350 °/s, and each pin with the I terms before/after. The tester: the Pavo20 ending
(addendum 15) was a bush, then the ground; "lots of crashes at the ends of most of these".

| craft | flag | tune (wc/wo, limits) | length | vbat | inhibit frames | both-end frames | max \|I\| r/p/y | frames err > 350 | what happened |
|---|---|---|---:|---|---:|---:|---|---:|---|
| Petrel75 | OFF | 117/123, 1000/1000 | 84 s | 8.51 → 7.80 | 0 | 1 425 | 1000 / 1000 / 1000 | 988 | three windups: 7.5 s, 44.2 s, 60.3 s |
| Petrel75 | ON | same | 72 s | 8.55 → 7.88 | 402 | 364 | 193 / 230 / 248 | 112 | one pin at 31.2 s, I flat, 563 °/s on P alone |
| HDZ Petrel75 | ON | 95/100, 500/400 | 95 s | 8.46 → 7.66 | 0 | 0 | 137 / 205 / 222 | 0 | clean |
| HDZ Petrel75 | OFF | same | 78 s (+8 ground logs) | 8.43 → 7.64 | 0 | 187 | 230 / 365 / 395 | 63 | clean to 76.4 s, then an impact at full throttle |
| TH3 | ON | 81/90, 1000/1000, LINEAR hover 5 | 180 s | 8.44 → 7.33 | 0 | 0 | 137 / 176 / 161 | 0 | clean; 19 982 frames at the ceiling, no clip |
| TH3 | OFF | same | 106 s | 8.25 → 7.46 | 0 | 677 | 1000 / 1000 / 1000 | 885 | clean to 104.7 s, then an impact and a tumble |

### Petrel75, second pair: same result as the first

OFF has three windups to the clamp. 44.2 s (full stick, pack 7.2–7.5 V, I −140/297/281 → −822/997/1000 in 120 ms,
pitch −873 °/s) and 60.3 s (122/229/196 → 1000/1000/1000, 1 120 °/s) are the addendum-12 shape. **7.5 s is a variant
worth recording:** throttle only 1 400 on a *fresh* pack (8.3 V), motor 0 on the 348 floor and motor 3 flat at
1757–1761 for ~200 ms — that plateau is the ceiling, because `vbat_sag_compensation` 100 lowers `motorRangeMax` on a
full pack. Roll I 336 → 996 and pitch −609 → −1000 in ~180 ms, then 644 °/s. So a pin does not need a sagged pack or
a motor at 2047, and any detector keyed on "≥ 1900" (as `sat.py` was) misses it; with the flag ON the log's own
inhibit bits are the reliable indicator. ON, same tune and pack state: one pin at 31.2 s (throttle 1 410 → 1 700,
pitch −90, motor 3 on a 1947–1971 plateau and motor 4 on 348 for ~250 ms). Inhibit active (`adrcState` 93), I terms
−102/226/211 → −77/151/225, gyro 533/−533 °/s (error up to 563) carried by P; inhibited frames span 31.03–31.77 s and the error is back under 100 °/s at 31.77 s. Two pairs now,
different days and packs, same outcome: the windup is gone, the excursion while pinned is smaller and ends with
the pin.

### HDZ Petrel75 and TH3: the flag is a no-op there, and the endings are impacts

Neither craft pinned its mixer in the ON flight (inhibit 0 frames, no both-end frames), and neither OFF flight shows a
windup before its ending. HDZ OFF at 76.45 s: full stick, one frame with gyro 119/55/−128 and motors
48/1938/262/126, then a tumble — impact-shaped; the eight short logs after it are ground attempts with the gate
closed (roll stick held, `adrcState` 2/28/30). TH3 OFF at 104.78 s: full stick with roll −114, one frame to
296/89/340 °/s, then yaw 1 793 °/s with all P/I/D at zero and motors 2033/348/348/2033 (yaw-spin recovery), then the
I terms charge to the clamp during the tumble. The windup there follows the impact, it does not cause it. These
two pairs therefore say nothing for or against the flag beyond "ON changed nothing", which is what it should do on
a craft that does not pin.

### The trade-off case is still open — and the TH3 shows why it is hard to fly

The tester offered the TH3 pair for the trade-off. In the ON flight the inhibit never fired: 20 s of airtime with a
motor on the ceiling and not one clip report, because at full throttle this craft still has differential room. The
trade-off (a real disturbance arriving while the inhibit holds z3) only exists while the flag is acting, and so
far the only crafts on which it acts are the whoop-class ones on a sagged or sag-compensated ceiling, for 50–570 ms
at a time. A deliberate test would be the Petrel held in a pinned state for seconds (sustained climb on a tired
pack), comparing attitude hold OFF vs ON.

## Addendum 17, 2026-09-18: full-throttle runs OFF/ON on the Petrel75 (the trade-off attempt), a ζ 75 % flight, and the 53 Hz notch (PR comments 5731090482, 5731702346; reply 5732543007)

Petrel75 2S on e6511d6a, 117/120 all axes (ζ flight: 124/130, ζ 75/75/75), b0 45/29/42, scale_min 80, td 140,
limits 1000/1000, `vbat_sag_compensation` 100. Logs in `8ksal8_petrel_20260918_fullthrottle/`; `fullthr.py` lists
every interval with the stick ≥ 1950 for ≥ 0.4 s.

| flight | flag | length | vbat | inhibit frames | max \|I\| | pins / excursions |
|---|---|---:|---|---:|---|---|
| full_throttle OFF | OFF | 117 s | 8.79 → 7.82 | 0 | 1000 / 1000 / 1000 | windup at 88.0 s (156/267/238 → 1000 ×3, 915 °/s); 946 °/s at the end |
| full_throttle ON | ON | 100 s | 8.06 → 7.42 | 1 357 | 210 / 255 / 265 | pin 59.84 s, 0.24 s, I flat, 492 °/s; impact at 98.40 s |
| ζ 75 %, 124/130 | ON | 244 s | 8.60 → 7.24 | 757 | 322 / 301 / 333 | one pin 47.8 s, 584 °/s |

### Sustained full throttle does not pin the mixer

| flight | t0 | length | vbat mean / min | roll-pitch error p50 / p99 / max | yaw max | inhibit | motor on ceiling |
|---|---:|---:|---|---|---:|---:|---:|
| OFF | 57.0 s | 0.6 s | 7.49 / 7.34 | 7 / 23 / 31 | 12 | — | 0 % |
| OFF | 75.7 s | 3.1 s | 7.12 / 6.89 | 5 / 15 / 23 | 10 | — | 56 % |
| ON | 23.1 s | 0.8 s | 7.07 / 6.86 | 10 / 25 / 32 | 25 | 0.0 % | 97 % |
| ON | 47.6 s | 6.1 s | 6.75 / 6.46 | 7 / 23 / 33 | 28 | 0.0 % | 100 % |
| ON | 98.0 s | 0.7 s | 6.92 / 6.39 | 41 / 2 333 / 2 590 | 2 104 | 32 % | 85 % |

The 6.1 s climb is the test the plan asked for — full stick on a pack at 6.5–6.75 V with a motor on the ceiling the
whole time — and the inhibit is active in **none** of its frames: the ceiling is reached through the throttle
constraint, the differential demand still fits — inferred from the inhibit bits staying at zero with the flag ON — so the mixer reports no clip and z3 keeps
learning. Attitude hold is the same as OFF (p99 23 vs 15–23 °/s). The last ON interval is not a control event:
at 98.40 s, tracking within 30 °/s, one frame goes to 1 933/110/1 753 °/s with all P/I/D zeroed and motors
2047/348/348/2047 (yaw-spin recovery) — an impact at full stick.

So the trade-off as written in ADRC-033 (a long pinned interval with a disturbance inside) does not arise from
holding throttle. The inhibit acts only when the *demand* exceeds the motor span, i.e. inside the 50–570 ms events
it was built for, where the measured effect is the removal of the windup. Its exposure is bounded by those
durations. What remains untested is a sustained clip caused by a sustained demand (a damaged prop or a dead motor),
where PID's own integrator is equally unable to help.

### ζ 75 % with 124/130

244 s, one pin (47.8 s, I terms 102/190/211 → 175/227/272, 584 °/s), I ≤ 333, nothing else above 350 °/s. It flies;
one flight, gains and ζ changed together, no comparison possible.

### The 53 Hz notch

Header: `gyro_notch_hz` 53, `gyro_notch_cutoff` 40 (lower edge 40, upper ≈ 53²/40 = 70 Hz), no gyro LPF1, LPF2 1000 Hz, dyn notch ×3 from 140 Hz, RPM filter 1
harmonic. Band amplitudes of the unfiltered gyro over 239 two-second airborne windows of the ζ flight, relative to
10–25 Hz: roll 25–40 Hz 0.45 (peak 30.0 Hz), pitch 0.62 (38.0 Hz), yaw 40–60 Hz 1.08 (45.5 Hz). The setpoint has no
line near 50 Hz (40–60 Hz band 0.15–0.16 of its 10–25 Hz content, peak at 30–32 Hz following the gyro), so an RC
packet-rate origin (jmsweng's hypothesis) is not supported by this log. The energy sits at 30 / 38 / 45 Hz per axis —
the same band as the loop mode tracked since the 13 Sep addendum — and the notch covers only the top of it. Whether
the notch helps by removing noise or by reshaping the loop needs a notch-off flight on the same pack; not
established.

## Addendum 18, 2026-09-19: 53 Hz notch on/off on the Petrel75 — it filters the motor trace, not the craft (PR comment 5734755835; reply 5740475090)

Same tune both flights (122/128, ζ 75/75/75, b0 45/29/42, flag ON, dyn notch ×3 from 140 Hz, LPF2 1000 Hz); only
`gyro_notch_hz`/`cutoff` 53/40 vs 0/0. Logs in `8ksal8_petrel_20260918_notch/`. `notch.py`: 2 s airborne windows in
the first 170 s with mean throttle 1250–1600, throttle σ < 80 and |setpoint| < 150 °/s; band RMS from a Hann-windowed
FFT, median over windows. 46 windows ON (8.05 V mean), 48 OFF (8.19 V).

| signal | flight | 10–25 Hz | 25–40 | 40–70 | 70–120 | 120–250 |
|---|---|---:|---:|---:|---:|---:|
| gyro unfiltered, roll (°/s) | notch ON | 3.00 | 1.16 | 1.01 | 1.08 | 2.11 |
| | notch OFF | 2.33 | 1.04 | 1.19 | 1.07 | 2.49 |
| gyro unfiltered, pitch | ON | 1.71 | 0.72 | 1.45 | 1.16 | 2.63 |
| | OFF | 1.55 | 0.68 | 1.59 | 1.08 | 3.51 |
| gyro unfiltered, yaw | ON | 0.52 | 0.35 | 0.66 | 0.84 | 1.35 |
| | OFF | 0.44 | 0.29 | 0.62 | 1.64 | 1.68 |
| motor, mean of four (DShot units) | ON | 17.2 | 8.5 | 10.2 | 14.2 | 18.6 |
| | OFF | 13.6 | 10.6 | 28.9 | 22.3 | 23.4 |

Mean |gyro − setpoint| roll/pitch/yaw: 3.7 / 2.7 / 2.1 °/s with the notch, 3.6 / 3.1 / 2.6 without. Current in the same
windows: 4.43 A vs 4.44 A (35.0 W vs 35.9 W) at the same mean throttle (1409 vs 1424).

Reading: without the notch the 40–70 Hz content of the *motor command* is 2.8× larger (and 1.6× in 70–120 Hz), which
is why that log "looks the worst" — but the craft's own motion in that band, the unfiltered gyro, moves by
−6 … +18 %, tracking error is unchanged within a degree per second, and the current is identical. The notch was
cleaning the trace, not the flight; the tester's impression ("not noticed in the footage, might even feel a little
better") matches. This also retires the suggestion in addendum 17 that the notch might be reshaping a loop mode: a
loop resonance being suppressed would show as a large change in the unfiltered gyro, and there is none. The one
real difference in motion is yaw 70–120 Hz (0.84 → 1.64 °/s), above the notch's upper edge and small in absolute terms.

Both flights: flag ON, inhibit 386 / 633 frames, I ≤ 299, one excursion each (871 °/s in the last frames of the
notch-ON log; 411 °/s at 65.2 s of the notch-OFF log).

## Addendum 19, 2026-09-19: yaw wc/wo 125 / 128 / "130" on the Petrel75, flag ON — three clean flights, and what the near-miss looks like (PR comment 5743099204; reply 5743503176)

Roll/pitch 114/120, ζ 100/100/25, b0 45/29/42, scale_min 90, td 140, limits 1000/1000, no static notch, flag ON. Logs in
`8ksal8_petrel_20260919_yawsweep/`. The file named `130` carries `yawPID:128,128,42` in its header — the 130 setting
was not in effect (not saved, or the wrong profile); it is a second 128 flight.

| file | yaw wc/wo (header) | length | vbat | inhibit frames | max \|I\| | roll-pitch error max / p99 (last second excluded) | yaw error max |
|---|---|---:|---|---:|---|---|---:|
| 125 | 125/125 | 58 s | 8.48 → 7.95 | 181 | 170 / 240 / 253 | 89 / 34 °/s | 73 |
| 128 | 128/128 | 112 s | 8.19 → 7.57 | 6 | 137 / 179 / 251 | 178 / 51 | 69 |
| "130" | 128/128 | 60 s | 8.81 → 8.19 | 19 | 139 / 231 / 192 | 85 / 36 | 57 |

No excursion in any of them (one 367 °/s sample in the final frames of the third log, at landing). None has a
full-stick interval; all have zero-throttle phases (6–11 s in total).

The tester's "right to the point it would break but doesn't" is at 37.3–37.7 s of the 125 flight, and it is the
addendum-12 entry frame for frame: throttle 1284 → 1361 with pitch −50 after a 1.9 s zero-throttle phase, pack 7.8 → 7.35 V,
motor 4 on the 326–341 floor and motor 3 on a 1961–1976 plateau. The inhibit is active for 0.37 s (173 frames,
`adrcState` 81–93), the I terms stay at −105…−139 / 213…238 / 174…251, the roll/pitch error never exceeds 48 °/s, and
when the throttle eases at 37.69 s the pin ends with nothing to unwind. With the flag OFF this is the interval in
which the I terms went to 1000.

So these flights do not show the washout being tuned out by yaw wc/wo: 125 and 128 both fly clean here, the tester
reports washouts on both values in flights that were not logged or not sent, and the three logs differ mainly in
how often the mixer pinned (181 / 6 / 19 inhibited frames), i.e. in the flying. What decides between a held pin and
an excursion with the flag ON is how far and how long the demand exceeds the motor span (addenda 13, 14, 16), not
the yaw bandwidth. A log of a washout *with the flag ON* at these settings would be the useful next sample.

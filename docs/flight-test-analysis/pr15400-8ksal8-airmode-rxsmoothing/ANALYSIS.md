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

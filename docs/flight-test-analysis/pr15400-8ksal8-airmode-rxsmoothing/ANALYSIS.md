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

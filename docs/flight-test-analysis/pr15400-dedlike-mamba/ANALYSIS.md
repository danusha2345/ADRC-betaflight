# @dedlike's arm-and-go-wild report: a divergent yaw instability on the shipped defaults

**Reporter:** @dedlike, PR #15400 comments of 2026-08-06; **props were on**, confirmed by him
2026-08-08.
**Craft:** MAMBAF722 (DIAT), STM32F7X2; `vbat` ≈ 15.4 V, consistent with 4S (`vbat_scale` 110).
**Firmware:** `6317fe2aa`, built 2026-08-06 14:22:59 — the head of the PR branch
(`bvandevliet:adrc-toggle`). Gate-wise this is **b6-level code**: the only commits between it and
the b6 tag are the fork-side `adrc_b0_law` selector and CI/docs, and his header carries no
`adrc_b0_law` field, so he is on the original QUADRATIC b0 schedule.
**Tune:** ADRC parameters entirely at their defaults — his `diff all` contains no `set adrc_*`
line at all. The header confirms `adrcWC 60,60,60`, `adrcWO 100,100,80`, `adrcB0 2000,2000,2000`,
`adrc_gyro_lpf_hz 150`, `adrc_liftoff_throttle 40`, `adrc_liftoff_gyro_dps 20`.
**Loop:** `looptime 125`, `pid_process_denom 2` (4 kHz), logged at ~1 kHz.

Three logs, all armed, all at **zero throttle stick**:

| file | `pid_type` | duration | motor activity |
|---|---|---|---|
| `btfl_001.bbl.gz` | 0 (PID) | 0.078 s | collective 0.0–0.6 %, spread ≤1.2 pp — **motors at idle** |
| `btfl_002.bbl.gz` | 0 (PID) | 2.809 s | collective 0–17.5 %, spread to 34.8 pp |
| `btfl_003.bbl.gz` | **1 (ADRC)** | **0.211 s** | collective 0.7 → **67.1 %**, spread to **100 pp** |

`btfl_001` is too quiet to serve as a control and is not used for comparison below; `btfl_002` is
the real PID reference.

**Battery:** `vbat_sag_compensation` is 0 (the default), so `motorRangeMax` is not attenuated and
the `motorOutput 158,2047` header range normalises the collective exactly. In `btfl_002` `vbat`
sits at 14.55–15.61 V. In `btfl_003` the reading swings **10.61–18.38 V** inside 0.21 s — the
upper end is above open-circuit for this pack, so that is a measurement artifact (ADC sampling
into switching transients on the rail), not real pack voltage. It is a symptom of how hard the
motors are being driven, not a battery fault.

## 1. This is not ADRC-026

The liftoff gate **never opened**: `debug[7]` is negative in all 205 frames, and `z3` is
**exactly zero** on all three axes throughout. The throttle stick sits at 0.0 % for the whole
log, so `throttleAtIdle` holds and every gate path stays interlocked. The gate behaved as
designed.

His firmware also predates the b7 applied-collective path and the b8 hold-timer fix, so neither
of those could have contributed. Nothing in the recent gate work is implicated.

## 2. It diverges from the moment of arming

The controlling observation is the **time course**, not any window average. In 30 ms windows from
the first logged frame:

| window, ms | collective | yaw gyro RMS | roll gyro RMS | yaw command RMS | motor on the rail |
|---|---|---|---|---|---|
| 0–30 | 7.7 % | 20.3 °/s | 1.1 °/s | 0.082 | 0 % |
| 30–60 | 13.5 % | 29.2 °/s | 1.3 °/s | 0.142 | 0 % |
| 60–90 | 23.5 % | 48.9 °/s | 2.7 °/s | 0.236 | 0 % |
| 90–120 | 36.4 % | **78.3 °/s** | 7.7 °/s | **0.334** | 0 % |
| 120–150 | 40.9 % | 78.4 °/s | 23.5 °/s | 0.315 | 53 % |
| 150–180 | 45.1 % | 73.4 °/s | 37.1 °/s | 0.274 | 60 % |
| 180–210 | 49.6 % | 39.4 °/s | **51.1 °/s** | 0.170 | 78 % |

Three things follow.

**It is a divergent instability, not a limit cycle.** Yaw amplitude grows ×3.9 in the first 90 ms
(e-folding ≈66 ms) while the frequency stays put — 31–41 Hz by zero-crossing count in every
50 ms window, consistent with the 34 Hz spectral peak. Fixed frequency with exponentially growing
amplitude is a pole crossing into the right half-plane. Nothing in the loop stops it; the only
thing that bounds it is **actuator saturation**, which arrives at ~120 ms. After that yaw *loses*
amplitude (78 → 39 °/s) precisely because saturation costs it authority.

**Roll ignites second, after saturation.** Roll gyro RMS grows ×46 (1.1 → 51.1 °/s) and is still
climbing when the log ends, but it only takes off once the motors are railing. Its 23 Hz tone
therefore belongs to the saturated state, not to the initial instability.

**The collective is dragged up at zero throttle stick.** 7.7 % → 49.6 %, because the mixer's
lower clamp (`throttle = constrainf(throttle, -normalizedMotorMixMin, …)`) raises the collective
to fit axis demands the stick never asked for. With props on, that is real and increasing thrust
— which is presumably why the log is only 0.21 s long.

Whole-window figures, for reference only, since averaging a diverging transient understates its
end state:

| axis | gyro RMS | gyro range | command RMS | command range | frames at the pidsum limit |
|---|---|---|---|---|---|
| roll | 34.3 °/s | 209 °/s | 0.138 | 0.747 | 0 % |
| pitch | 15.6 °/s | 100 °/s | 0.068 | 0.377 | 0 % |
| yaw | 57.8 °/s | 263 °/s | 0.241 | 0.800 | 13 % |

That 13 % is itself a window average: 0 % for the first 120 ms, then 53 / 60 / 78 % in the last
three windows.

**Frequency resolution is 4.7 Hz** on this 0.21 s record, so spectral peaks are ±3 Hz. Peak
*amplitudes* are not quoted anywhere: they move by up to 1.8× between a rectangular and a Hann
window on a record this short, so all magnitudes above are window-independent time-domain
statistics.

## 3. It is the loop, not the airframe

Same craft, same session, same zero throttle, `gyroUnfilt` RMS over the whole log:

| axis | `btfl_002` (PID) | `btfl_003` (ADRC) | ratio |
|---|---|---|---|
| roll | 1.89 °/s | 34.3 °/s | **18×** |
| yaw | 1.68 °/s | 57.8 °/s | **34×** |

Roll and yaw are quiet under PID and violent under ADRC. Pitch is excluded: in the PID log he was
moving the pitch stick (RP stick input up to 194 counts, command RMS 0.026), so its 18 °/s is
commanded motion, not a comparable baseline.

**Props were on.** That was the one open question and it is now answered, and it matters in the
direction that makes this worse: full aerodynamic damping was present and the loop diverged
anyway. The alternative reading — that a propless bench removes the damping and manufactures a
yaw instability that would not appear in flight — is ruled out.

The claim this supports is narrow: **the craft does not enter this state under PID at the same
throttle.** It is not that an external vibration exists and only ADRC reveals it; under PID
nothing is there to reveal.

## 4. The D-equivalent path carries it

Under ADRC the firmware logs the control law's own terms into `axisP`/`axisD`
(`pid.c:1113–1115`: `pidData[axis].P = adrcOutput.P`, `.D = adrcOutput.D`), so this is measured,
not inferred:

| axis | RMS `axisP` | RMS `axisD` | D/P (RMS) | D/P at the ring frequency |
|---|---|---|---|---|
| roll | 69.0 | 149.3 | 2.2 | **2.6** |
| pitch | 26.2 | 63.1 | 2.4 | **2.6** |
| yaw | 94.1 | not logged | — | — |

`axisD` on roll spans −529…+330 and `|P + D|` reaches **704** against `pidsum_limit 500`. The
terms are deliberately not clamped individually (`adrc.c`, the comment above the control law);
the bound is applied downstream as `constrainf(Sum, ±pidsum_limit)` in the mixer, which is where
the clipping in 6 % of roll frames happens.

On yaw, `axisP` reaches only 203 and contributes 69.5 at 34 Hz, while the mixer command is pinned
at 400 — so the yaw D-term supplies the balance there too, on the axis that actually goes
unstable. **Blackbox does not record `axisD[2]`**, so the dominant term on the failing axis is
invisible in the log; that is worth fixing for ADRC work.

Reconstructing the law independently from the logged observer states —
`P = wc²·(setpoint − z1)/b0`, `D = −2·wc·z2/b0` — reproduces the actual mixer-axis command with a
**median discrepancy of 0.0009** of full authority. That cross-validates both the control-law
model and the mixer-axis decomposition of §2.

End-to-end gyro→command gain at the ring frequency, measured as the DFT ratio (ratios are far
more window-stable than amplitudes, but not perfectly):

| axis | rectangular | Hann |
|---|---|---|
| roll (23 Hz) | 0.0044 | 0.0054 |
| pitch (24 Hz) | 0.0056 | 0.0063 |
| yaw (34 Hz) | 0.0045 | 0.0044 |

So **0.004–0.006 of full mixer authority per °/s** across all three axes and both windows.

**What this does not explain.** The instantaneous command is not this gain times the instantaneous
gyro: frames at the yaw limit have `|gyro|` anywhere from 2 to 116 °/s (median 65), and the single
largest gyro sample, 119 °/s, produces only 0.356 — unsaturated. The observer states carry phase,
so any instantaneous-gain argument for the saturation is invalid and none is made here.

**A caveat on the mechanism.** The tempting asymptotic story — above `wo` the observer stops
tracking, so `z2 → (3wo²/ω)·gyro` — **overpredicts the measured ratio by a factor of 2.8**
(207.6 predicted vs 74.3 measured on roll). At 23 Hz the ring is only 1.45× above
`wo = 100 rad/s`, not the asymptotic regime, and `z1/gyro = 1.15` shows the observer still
amplifying rather than rolling off. A phase test does not discriminate either, because the LESO
contributes its own phase at these frequencies. The measured gains and the measured D/P ratio
stand; the closed-form mechanism does not, and is not claimed.

## 5. Relation to ADRC-024

Weaker than it first looks, and the time course is why.

The **yaw** instability at 34 Hz is not ADRC-024: that entry is about a 24–27 Hz roll/pitch ring
in disturbance-rich low-collective *flight*, and this is a different axis, a different frequency,
and divergent from arm rather than episodic.

The **roll** tone at 23 Hz does coincide with ADRC-024's band within the ±3 Hz resolution, and the
craft runs the same base tune (`wc 60`, `wo 100`, `b0 2000`) on which that entry's hypotheses were
formed — but here roll only ignites *after* yaw saturates the motors, so it may be a consequence
of the saturated state rather than the same mechanism. Treating this log as a fourth sighting of
the ADRC-024 ring would be over-reading it.

What is solid and new: on the shipped defaults, on a stock 5" with props on, **yaw is unstable at
arm time on the ground** — reproducible without flying, in 0.2 s, at zero throttle stick.

## 6. Open question for the reporter

**A longer log.** 0.21 s gives 4.7 Hz resolution, no view of throttle dependence, and forces the
amplitude caveats above. A few seconds at the same `blackbox_sample_rate 1/4` would settle the
growth rate properly and show whether the instability exists at other collectives. Given that the
craft builds real thrust while diverging, this needs restraint on the ground rather than a longer
brave arm — the useful version is the same log with only `adrc_b0_*` raised to 4000, which tests
the gain story with a single variable and should not diverge at all if the reading here is right.

## 7. Reproduction

```
cd docs/flight-test-analysis/pr15400-dedlike-mamba
gunzip -k *.bbl.gz && blackbox_decode btfl_001.bbl btfl_002.bbl btfl_003.bbl
python3 divergence.py           # the 30 ms time course and the frequency-vs-time check
python3 spectra.py              # peak frequencies, mixer-axis decomposition
python3 compare_pid_adrc.py     # in-band energy, PID vs ADRC
python3 control_law_terms.py    # P/D reconstruction against the actual command
python3 observer_gain.py        # measured |z2|/|gyro| vs the asymptotic prediction
python3 logged_terms.py         # axisP/axisD/axisI/axisF ranges, pidsum clipping
python3 robust_stats.py         # window-independent RMS, window sensitivity, D/P at the ring
```

All scripts expect the decoded `.csv` files in the working directory.

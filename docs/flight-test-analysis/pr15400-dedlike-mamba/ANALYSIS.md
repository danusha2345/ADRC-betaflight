# @dedlike's arm-and-go-wild report: a self-excited limit cycle on the default tune

**Reporter:** @dedlike, PR #15400 comments of 2026-08-06.
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
| `btfl_003.bbl.gz` | **1 (ADRC)** | **0.211 s** | collective 0.7–**67.1 %**, spread to **100 pp** |

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

## 2. What actually happens: a self-excited limit cycle at zero throttle

Decomposing the four logged motor outputs onto the QUAD X mixer axes (`Y = Σ yᵢ·mᵢ / 4`; the
coefficient table is `mixer_init.c:84–89`, and the decomposition is validated in §4):

| axis | gyro RMS | gyro range | command RMS | command range | at the pidsum limit |
|---|---|---|---|---|---|
| roll | 34.3 °/s | 209 °/s | 0.138 | 0.747 | 0 % |
| pitch | 15.6 °/s | 100 °/s | 0.068 | 0.377 | 0 % |
| **yaw** | **57.8 °/s** | **263 °/s** | **0.241** | **0.800** | **13 %** |

Yaw is pinned at `pidsum_limit_yaw` (±0.400) in one frame out of eight. A motor sits at the 2047
rail in **25 %** of frames and the mean collective reaches **67 %** — at a throttle stick of zero.

Spectral peaks (Hann-windowed DFT):

| axis | peak |
|---|---|
| roll | 23 Hz |
| pitch | 24 Hz |
| **yaw** | **34 Hz** |

**Frequency resolution is 4.7 Hz** on this 0.21 s window, so read those as ±3 Hz. Peak
*amplitudes* are not quoted: they move by up to 1.8× between a rectangular and a Hann window on
a record this short, so only the window-independent time-domain statistics above are used for
magnitudes.

The oscillation is small in *angle*: 57.8 °/s RMS at 34 Hz is well under a degree of travel. The
craft is not rotating, it is buzzing, and the loop answers the buzz with full authority.

## 3. It is the loop, not the airframe

Same craft, same session, same zero throttle, `gyroUnfilt` RMS:

| axis | `btfl_002` (PID) | `btfl_003` (ADRC) | ratio |
|---|---|---|---|
| roll | 1.89 °/s | 34.3 °/s | **18×** |
| yaw | 1.68 °/s | 57.8 °/s | **34×** |
| pitch | 18.12 °/s | 15.6 °/s | — |

Roll and yaw are quiet under PID and violent under ADRC. Pitch is excluded: in the PID log he was
moving the pitch stick (RP stick input up to 194 counts, command RMS 0.026), so that 18 °/s is
commanded motion, not a comparable baseline.

The claim this supports is narrow and worth stating precisely: **the craft does not enter this
state under PID at the same throttle.** It is not that an external vibration exists and only ADRC
reveals it — under PID nothing is there to reveal. It is also not independent of ADRC's own motor
output, and that is the point: a self-excited limit cycle is exactly a loop sustaining its own
excitation.

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
at 400 — so the yaw D-term supplies the balance there too, on the one axis that actually
saturates. **Blackbox does not record `axisD[2]`**, so the dominant term on the failing axis is
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

The roll/pitch tone at **23–24 Hz** coincides, within the ±3 Hz resolution, with ADRC-024's
24–27 Hz ring, on a craft running the same base tune (`wc 60`, `wo 100`, `b0 2000`) on which that
entry's hypotheses were formed. Two things here are new:

- it happens at **zero throttle on the ground**, not only in disturbance-rich low-collective
  flight, so it reproduces without flying;
- there is a **separate, stronger yaw tone at 34 Hz** that saturates its axis — ADRC-024 as
  written concerns roll/pitch.

Fourth craft to show the family (after @jmsweng's Air65, @8ksal8's, and the b4 craft) and the
first to show it as a ground-reproducible arm-time event. Consistent with ADRC-024's
phase-margin and b0-calibration hypotheses; it does not discriminate between them.

## 6. Open questions for the reporter

1. **Props on or off?** Not determinable from the log, and it changes the plant completely. With
   props off the yaw loop still closes through rotor reaction torque with almost no aerodynamic
   damping, which would make a yaw limit cycle far easier to excite than in flight.
2. **A longer log.** 0.21 s gives 4.7 Hz resolution, no view of throttle dependence, and forces
   the amplitude caveats above. A few seconds at the same `blackbox_sample_rate 1/4` removes all
   three limitations.

## 7. Reproduction

```
cd docs/flight-test-analysis/pr15400-dedlike-mamba
gunzip -k *.bbl.gz && blackbox_decode btfl_001.bbl btfl_002.bbl btfl_003.bbl
python3 spectra.py              # peak frequencies, mixer-axis decomposition
python3 compare_pid_adrc.py     # in-band energy, PID vs ADRC
python3 control_law_terms.py    # P/D reconstruction against the actual command
python3 observer_gain.py        # measured |z2|/|gyro| vs the asymptotic prediction
python3 logged_terms.py         # axisP/axisD/axisI/axisF ranges, pidsum clipping
python3 robust_stats.py         # window-independent RMS, window sensitivity, D/P at the ring
```

All scripts expect the decoded `.csv` files in the working directory.

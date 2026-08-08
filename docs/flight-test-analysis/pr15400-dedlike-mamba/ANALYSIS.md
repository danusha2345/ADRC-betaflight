# @dedlike's arm-and-go-wild report: a fast-growing yaw oscillation on the shipped defaults

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

The liftoff gate **never opened**: `debug[7]` is negative in all 205 frames (range −100…−120, so
nowhere near the debug clip), and the logged `z3` is zero on all three axes throughout. A zero in
that field alone would only bound `|z3| < 8`, since `adrc.c` divides it by 16 before logging — but
the code closes the gap: the arm reset sets `z3` to 0 and the closed gate at idle rejects any
increase in `|z3|`, so it is exactly zero. The throttle stick sits at 0.0 % for the whole log, so
`throttleAtIdle` holds and every gate path stays interlocked.

His firmware also predates the b7 applied-collective path and the b8 hold-timer fix, so neither of
those could have contributed. **What is proven is narrow: the ADRC-026 failure mode — gate opening
on the ground and z3 winding up — is absent here.**

It does not follow, as the first version of this file implied, that gate dynamics play no part. The
closed gate is an *active* element: it forces `b0·u = 0` in the observer while the motors are
demonstrably moving the craft, so the observer is running against a deliberately falsified input
model for the whole event. And the applied collective crosses the 40 % `adrc_liftoff_throttle`
threshold at **87.017 ms** — the same frame the yaw command first clamps — yet b6 reads the
*commanded* collective, so the gate stays shut. Counterfactually, a build reading the applied
collective (b7 onward) would have opened it mid-event, giving different observer behaviour. Whether
that would be better or worse is untested.

## 2. It grows fast from the moment of arming

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

Four things follow.

**The growth is real, and not an artifact of the 30 ms windows.** An exponential-envelope fit over
the unsaturated first 80 ms gives **f = 37.0 Hz, time constant 65.6 ms, R² = 0.988**, and a
constant-amplitude sinusoid is 9.5× worse by SSE.

**But it must not be called a divergent instability, and the first version of this file did.** Only
about **three cycles** elapse before the first clamp, after which the loop is nonlinear and its
operating point is moving; a finite transient in a discrete, saturating, operating-point-shifting
loop does not establish an unstable pole. A saturation-limited limit cycle is not excluded either —
after saturation the yaw peaks do **not** decay monotonically: 120 °/s @109 ms, 121 @112 ms,
113 @140 ms, **128 @170 ms**, the largest of them last. The earlier claim that yaw fell 78 → 39 °/s
"precisely because saturation costs it authority" is wrong; that fall is a window-RMS effect, not a
decaying envelope.

**Three different limits engage at three different times**, and conflating them was the first
version's main factual error:

| limit | first reached |
|---|---|
| yaw command at `pidsum_limit_yaw` (±0.400) | **87.017 ms** |
| upper motor rail (2047) | **127.025 ms** |
| lower motor rail (158) | active in **205/205** frames from the start |

The lower rail is continuously active but costs no axis authority before 127 ms — the mixer
preserves the range by shifting the collective instead (next point).

**Roll starts with the yaw clamp, not with the motor rail.** Roll `|gyro|` crosses 5 °/s at
**86.017 ms**, 10 °/s at 103.020 ms and 15 °/s at 107.021 ms — all before the upper rail at
127.025 ms. The table above already showed roll RMS rising 2.7 → 7.7 °/s in the 90–120 ms window
at 0 % rail contact, which contradicted the claim it accompanied.

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

That 13 % is itself a window average, and the per-window figures are **0 / 0 / 10 / 53 / 10 / 13 /
0 %** — peaking in the 90–120 ms window and *falling* afterwards. The 53 / 60 / 78 % in the table
above are the **upper-motor-rail** column, a different quantity; the first version of this file
attributed those three numbers to the yaw pidsum limit, which is simply wrong.

**Frequency resolution is 4.7 Hz** on this 0.21 s record, so spectral peaks are ±3 Hz. Peak
*amplitudes* are not quoted anywhere: they move by up to 1.8× between a rectangular and a Hann
window on a record this short, so all magnitudes above are window-independent time-domain
statistics.

## 3. Controller-specific, on the evidence available

Same craft, same session, same zero throttle, `gyroUnfilt` RMS over the whole log:

| axis | `btfl_002` (PID) | `btfl_003` (ADRC) | ratio |
|---|---|---|---|
| roll | 1.89 °/s | 34.3 °/s | **18×** |
| yaw | 1.68 °/s | 57.8 °/s | **34×** |

Roll and yaw are quiet under PID and violent under ADRC. Pitch is excluded: in the PID log he was
moving the pitch stick (RP stick input up to 194 counts, command RMS 0.026), so its 18 °/s is
commanded motion, not a comparable baseline.

**Props were on**, which rules out the reading that a propless bench removes damping and
manufactures a yaw oscillation that would not appear in flight. It does *not* justify saying "full
aerodynamic damping was present", as the first version did: the craft is on the ground, so RPM and
contact constraints vary through the event.

The PID comparison is stronger than the whole-log figures suggest. First 211 ms of the PID log
(matching the ADRC log's length): roll/yaw **0.74 / 0.88 °/s**. Worst 211 ms window anywhere in the
PID log: 5.01 / 3.38. A PID 30 ms window at nearly the same collective as the ADRC log's first
window (7.697 %): 1.18 / 1.71. Against ADRC's 34.2 / 57.9. That disposes of "this is just the arm
transient any controller shows" for this session.

What it does not establish is the heading this section originally carried. Proven: a
controller-specific closed-loop state. **Not** proven: independence from the plant, the contact
condition, or RPM-dependent excitation — the PID log never reaches the 30–67 % applied collective
the ADRC log does. And one arm does not separate a reproducible ADRC defect from a rare
ADRC-specific arm transient.

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
the bound is applied downstream as `constrainf(Sum, ±pidsum_limit)` in the mixer.

Two roll numbers in this file measure different things and must not be read as one: **12 frames
(5.9 %)** have an *input* `|axisP + axisD| ≥ 490`, while **0 frames** have an *applied* mixer-axis
roll command at ±0.49 — the mixer renormalises the whole mix once `motorMixRange > 1`, which yaw's
own clamp guarantees here. The §2 table reports the applied command; this paragraph reports the
input.

On yaw, `axisP` reaches only 203 and contributes 69.5 at 34 Hz, while the mixer command is pinned
at 400 — so the yaw D-term supplies the balance there too, on the axis that actually goes
unstable. Reconstructed from the applied command and `axisP` **before** the clamp, yaw runs at
`D/P ≈ 2.55` (2.52 at 34 Hz), so D dominance holds on the failing axis too.

**Blackbox does not record `axisD[2]`**, because the field is gated on the *legacy* profile D-gain
being non-zero (`blackbox.c:206-208,523-526`) while the shipped default leaves `pid[FD_YAW].D` at 0
and ADRC generates a live D there. A genuine instrumentation bug — fixed on the fork side by keying
the condition on `pid_type == PID_TYPE_ADRC`. It is not true, though, that the term is "invisible":
it is recoverable up to the clamp as above, and only after saturation is it unrecoverable.

Reconstructing the law independently from the logged observer states —
`P = wc²·(setpoint − z1)/b0`, `D = −2·wc·z2/b0` — reproduces the actual mixer-axis command to a max
error of **0.00148** (roll) and **0.00118** (pitch) **over the first 120 ms**, cross-validating both
the control-law model and the mixer-axis decomposition of §2 *in the unsaturated segment*.

The median-over-the-whole-record figure of 0.0009 quoted in the first version was misleading: it
hides the saturated tail, where the same reconstruction reaches p95 0.271 / max 0.420 on roll. Two
reasons — the sum is clipped downstream, and `b0` is not constant: `debug[7]` runs 100 → 120, i.e.
`b0ThrottleScale` 1.00 → 1.20, so the effective `b0` rises 2000 → 2400 as the collective climbs,
while `control_law_terms.py` assumes 2000 throughout.

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
formed. It is still not a fourth sighting — but for a different reason than the first version gave.
That version said roll ignites only after the motors rail, which is false (roll crosses 5 °/s at
86 ms, the rail arrives at 127 ms). The actual reason is duration: the active roll episode lasts
about **0.11 s**, which is two to three cycles at 23 Hz — far too short to identify a mechanism, or
to distinguish this tone from ADRC-024's.

What is solid and new: on the shipped defaults, on a stock 5" with props on, **yaw grew to its
authority limit within 87 ms of arming**, on the ground, at zero throttle stick — no flying
required to see it. "Reproducible" is not yet earned: this is **one** ADRC arm. It is an
observation, awaiting a repeat.

## 6. Open question for the reporter

**A longer log.** 0.21 s gives 4.7 Hz resolution, no view of throttle dependence, and forces the
amplitude caveats above. A few seconds at the same `blackbox_sample_rate 1/4` would settle the
growth rate properly and show whether the instability exists at other collectives. Given that the
craft builds real thrust while the oscillation grows, this needs restraint on the ground rather
than a longer brave arm. The useful version varies **`adrc_b0_yaw` alone** — the failing axis —
over short repeated arms with a hard stop the moment motors move. Note that raising `b0` halves
P and D authority but does **not** guarantee stability; the first version claimed it "should not
diverge at all", which does not follow from anything measured here.

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

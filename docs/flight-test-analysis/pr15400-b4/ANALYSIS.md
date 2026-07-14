# b4 verification flight — measured analysis (2026-07-14)

Source: 4 logs from Bob (bvandevliet), SpeedyBee F7 Mini, shared 13:25 UTC in
[PR #15400](https://github.com/betaflight/betaflight/pull/15400) (STACK share
`ZgLzNj7BccQ4qk99`, downloaded immediately — Bob's shares expire). The `.bbl`
originals and the analysis scripts live in this directory.

## Methods (reproducibility)

- Decode: `blackbox_decode <log>.bbl` (betaflight/blackbox-tools, defaults) →
  one CSV per log; fs = 1592 Hz (median of `time` deltas).
- Run `analyze_b4.py` (per-throttle-bin tone table, b0-scale stats, punch and
  zero-throttle detection, gate epochs) and `analyze_b4_deep.py`
  (time-resolved worst windows with context) from this directory after
  adjusting the `BASE` path to where the CSVs are.
- Tone metric: 1 s Hann windows, 50 % overlap; dominant PSD peak in 10–40 Hz
  (15–35 Hz in the deep script); "tone amplitude" = RMS integrated over
  peak ±2 Hz; "tone fraction" = that RMS over the 5–100 Hz RMS. Windows count
  as airborne when gate (sign of `debug[7]`) is open ≥ 90 % of the window and
  all motors are on.
- Throttle % = `(rcCommand[3] − 1000)/10` (stick, not post-mixer collective).
- Steady-stick windows (for b0-scale stats): max |setpoint roll/pitch| < 30
  deg/s, throttle std < 2 %, gate open.
- Punch→chop event: throttle > 40 % (gate open), then falling below 15 %
  within < 4 s; "calm-stick" = max |setpoint R/P| < 60 deg/s in the 0.6 s
  after the chop; rebound = peak |gyro| in that 0.6 s.
- Zero-throttle segment: throttle < 3 %, gate open, motors on, ≥ 0.8 s.

## Build & tune verification (the A/B property)

- All 4 logs: `Firmware revision: Betaflight 2026.6.0-alpha (08ad602ce) STM32F7X2` =
  tip of `pr15400-builds-b4`; PR-head-at-the-time `79f8b6041d` (the ADRC-018/019
  fixes) **is an ancestor** → genuinely flown on b4. ✓ Note: the later ADRC-020
  removal (`eda3bb16eb`, pushed by the PR author after this flight) is **not**
  in this build — irrelevant here since the opt-in re-arm was off by default.
- Full `adrc_*` header block **byte-identical** to the b3 logs (wc 60/60/60,
  wo 100/100/80, b0 2000×3, hover 22, gyro_lpf 150, scale_max 3, idle re-arm off). ✓
- Logs: btfl_001 (1.8 s, aborted hop), btfl_002 (28.3 s), btfl_003 (41.1 s),
  btfl_004 (22.3 s). Battery 4S, 15.2–16.0 V under load.

## Flight-mode attribution: NOT possible from these logs

Bob: "most are AIR mode, not sure which ones". The logs cannot settle it:
the AIRMODE feature bit (22) is 0 in every log **including his b3 file named
`btfl_AIR2`** (he switches airmode via a mode switch, and box states are not
in the header), and the decoded `flightModeFlags` stream is identical between
his AIR-labeled and ACRO-labeled b3 logs (constant `ANGLE_MODE` = the decoder's
legacy alias for the ARM bit). Motor-floor heuristics did not separate modes
either. **All per-log statements below are therefore mode-unlabeled**; the b3
log names are Bob's, not log-verified.

## Verdicts per tracked item

### ADRC-017/020 chain (arm epochs, no mid-air re-arm) — CLEAN ✓

Every log starts gate-closed with exactly one open transition and zero mid-air
re-gates (idle re-arm off by default). Compare the pre-remediation baseline
(btfl_002-ACRO): 7 gate flips including 3 false in-flight "landings".

### ADRC-019a (b0-scale modulation) — FIXED, flight-confirmed ✓

Steady-stick windows (criteria above), b0-scale (|debug[7]|/100) swing:
b4 p90 = 0.27–0.29, max 1.14 during transients, vs the pre-fix behavior of
1.0↔2.8 at constant stick. The 2 Hz collective LPF visibly does its job.

### ADRC-018 (26 Hz limit cycle) — the always-on regression component is gone; an episodic ring remains

Dominant-tone analysis (gyro roll, median per throttle bin, deg/s; b3 column
names are Bob's file labels, not log-verified modes):

| thr bin | baseline (pre-remed) | b3 "ACRO2" | b3 "AIR2" | b4 log2 | b4 log3 | b4 log4 |
|---|---|---|---|---|---|---|
| 10–15 % | 1.00 | — | 14.0 | **19.1** | — | 1.5 |
| 15–20 % | 0.76 | 3.9 | 20.8 | **18.0** | 1.1 | 0.8 |
| 20–25 % | 0.79 | 4.8 | 24.1 | 5.8 | 1.1 | **10.1** |
| 25–30 % | 0.94 | 4.2 | — | — | 1.2 | **10.9** |

- Frequency unchanged: 24–27 Hz, 93–100 % of error power in the single tone,
  present in `gyroUnfilt` too (not a filter artifact).
- **btfl_003 is baseline-clean end to end** (1.1–1.2 deg/s ≈ baseline 0.8–0.9)
  across the hover band, through punches and 670 deg/s flips — on the b3 head
  no logged flight achieved that. What we can honestly claim: **the always-on
  component of the regression did not reproduce in a full 41 s b4 flight with
  the byte-identical tune.** What we cannot claim: a mode-specific (acro vs
  air) A/B — mode attribution is impossible (above), so "b3 ACRO2 4–5 →
  b4 1.1" is suggestive, not proven.
- **btfl_002/004 still ring episodically**: ignition is event-triggered —
  right at gate open (log2 t=1.5–4.5 s, up to **41 deg/s** — worse than any b3
  window), after a 94 %-throttle punch→chop into own propwash (log4
  t=10.5–11.5 s, 19–26 deg/s), and during the low-throttle landing approach
  (log2 t=25–26.5 s). Between ignitions the same flight is quiet for ~20 s at
  the same stick positions.
- No correlation with battery voltage (raging 15.2–15.6 V vs quiet 15.4–16.0 V)
  or motor-floor clipping fraction.

Tracked as **ADRC-024**. Hypotheses (leading first, none established —
the ADRC-021 doublet data is the discriminator):

1. **b0 under-calibration near hover for this craft** (hovers at 22 % vs the
   35 % craft the default 2000 was derived on → by the quadratic law the real
   control authority at hover is ≈ (35/22)² ≈ 2.5× the calibration point —
   a physically plausible model, **not a measurement of this craft's plant
   gain**). Would leave a standing over-gain and thin phase margin at 26 Hz.
2. Residual feedback mismatch specific to airmode's low-collective mixer
   redistribution (the binary applied-signal fix may not capture it) — needs a
   code-path re-read plus a replay simulation against these logs.
3. Pure phase-margin shortfall at wc=60 for this craft's latency — compatible
   with (1), distinguished by the same doublet data.

### ADRC-019b (punch→chop rebound) — NOT improved

Calm-stick punch→chop events, peak |pitch gyro| in the 0.6 s after the chop:

| build | events | median | max | z3P peak |
|---|---|---|---|---|
| baseline (scale cap 9, pre-remed) | 2 | 152 | 171 | 524k (debug rail) |
| b3 "ACRO2" (cap 3) | 5 | 80 | 95 | 271k |
| b4 (all logs) | 9 | 80–97 | **181** | 498–524k |

The 2 Hz release LPF did not measurably reduce the rebound (Bob's "maybe
slightly improved" matches log3/log4; log2's 87 %-punch produced 181 deg/s —
b3-worst level). The b0-scale still traverses 3.00→1.00 on every chop. z3
excursions during punches: z3P hits the ±524k debug rail in log2 (0.20 % of
samples) and log3 (1.50 %; z3R 0.7 %); log4 peaks at ~478k without railing.
The rebound **coincides with** the z3 transient (thrust-collapse pitch moment
+ observer re-learning after adapting under a ×3-inflated gain frame) — a
consistent mechanism, but correlation, not established causation. Either way
the release *rate* is ruled out as the dominant knob; candidate directions are
the b0 law itself (ADRC-021) and/or an explicit throttle-transition
feed-forward. Tracked as **ADRC-025**.

### AIR zero-throttle drop — WORKS ✓ (Bob's subjective report, consistent with the logs)

Zero-throttle airborne segments (≥ 0.8 s) show controlled behavior; the
high-gyro-RMS ones coincide with commanded maneuvers; median |acc| 0.22–0.62 g
confirms sustained airborne descent states handled with the gate open and no
false re-arm.

## Bottom line

b4 confirmed the two fixes it carried where the logs can speak (scale·u
always-on over-gain: not reproduced, one fully clean flight; d7 modulation:
gone) and falsified two hopes (episodic 26 Hz ring in disturbance-rich states;
punch rebound unchanged). The **leading hypothesis** — to be tested, not yet
established — is b0 calibration/scheduling around and below hover, which is
exactly what the ADRC-021 system-identification flight measures. ADRC-020 was
closed by the PR author right after this flight (`eda3bb16eb`).

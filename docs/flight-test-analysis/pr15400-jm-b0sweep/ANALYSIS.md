# jmsweng DAKEFPV, 2026-07-20 — b0-law hover A/B + FIXED-law b0 sweep

Source: PR [betaflight#15400] comment of 2026-07-20 (`btfl_all.zip` →
`btfl_laws.bbl`, 5 sessions) and the pilot's fork `jmsweng/ADRC-betaflight`
`b0 testing/btfl_all.bbl` (→ `btfl_b0sweep.bbl`, 11 sessions). Both preserved
here verbatim.

**Provenance** (from headers): every session is firmware `543f1a5ff` — exactly
the `adrc-pr15400-b5` tag — on STM32F405 (DAKEFPV), `debug_mode = ADRC`,
tune wc 40 / wo 100 / b0 as listed, `adrc_hover_throttle = 35`,
`adrc_liftoff_throttle = 40`. Laws file: sessions carry `adrc_b0_law`
0,0,1,2,3 (session 1 is a 0.6 s turtle-mode arm — excluded). Sweep file: all
11 sessions `adrc_b0_law = 3` (FIXED), `adrcB0` = 1000…8000 + 5500/6500/7500,
matching the pilot's description. The gate opens exactly once per log; no
mid-air re-gates anywhere.

Reproduce: decode both `.bbl` with the pinned `blackbox_decode`
(`--debug --unit-frame-time us`), then `python3 jm_b0sweep.py`. Methods
corrections vs the first-pass numbers posted nowhere else (caught in internal
review before publication): a spurious ×2 in the band-RMS formula (validated
against a synthetic tone), and gate masking now applied *before* filtering.

## Result 1 — the law A/B was effectively degenerate

The craft hovers at ~27–28 % collective while `adrc_hover_throttle = 35`, so
throttle/hover < 1 essentially the whole flight and the never-below-1× clamp
engages. `debug[7]` (applied scale ×100):

| law | dur | med thr | debug[7] min/max | time > ×1.00 | gyro 18–32 Hz RMS |
|---|---|---|---|---|---|
| QUADRATIC | 10.8 s | 27.6 % | 100/100 | 0 | 3.3 dps |
| SQRT | 11.4 s | 27.8 % | 100/100 | 0 | 3.4 dps |
| LINEAR | 10.7 s | 27.3 % | 100/**103** | 0.27 s (3.0 %) | 3.9 dps |
| FIXED | 12.5 s | 28.2 % | 100/100 | 0 | 3.9 dps |

Three arms sat exactly at ×1.00; LINEAR exceeded it only briefly (×1.03 for
~0.27 s). These logs therefore cannot discriminate the laws — the pilot's
"didn't really notice much of a difference" is the expected outcome, and no
cross-craft conclusion about the b5 ring/law inversion can be drawn from them.
An informative re-fly needs `adrc_hover_throttle ≈ 28` *and* deliberate
above-hover segments (30–40 % collective), with post-flight confirmation from
`debug[7]` that the arms actually separated.

## Result 2 — FIXED-law b0 sweep (gate-open slice, masked before filtering)

| b0 | gate open | thr @ open / med | motor HP-RMS | gyro 18–32 Hz RMS (slice) | dom. peak | calm 1 s windows (n, med/max dps) |
|---|---|---|---|---|---|---|
| 1000 | **0.46 s** | 8.9 / 13.1 % | **175.7** | **40.3** | **21.7 Hz** | 0 |
| 2000 | 3.47 s | 20.7 / 28.7 % | 33.2 | 2.7 | 22.2 Hz | 3, 1.6/4.8 |
| 3000 | 2.98 s | 28.2 / 29.1 % | 95.4 | 9.9 | 6.4 Hz | 2, 1.3/1.8 |
| 4000 | 2.42 s | 28.6 / 29.4 % | 39.6 | 1.0 | 10.3 Hz | 2, 1.0/1.1 |
| 5000 | 3.04 s | 30.2 / 29.3 % | 40.3 | 1.0 | 11.8 Hz | 3, 0.9/1.1 |
| 5500 | 2.68 s | 29.3 / 29.3 % | 29.2 | 1.2 | 6.7 Hz | 2, 1.3/1.4 |
| 6000 | **1.26 s** | 31.2 / 31.5 % | 51.0 | 0.5 | 7.2 Hz | 1, 1.6/1.6 |
| 6500 | 3.30 s | 28.2 / 31.0 % | 32.1 | 1.9 | 5.2 Hz | 3, 0.8/0.9 |
| 7000 | 3.64 s | 28.1 / 30.2 % | 51.5 | 9.6 | 6.0 Hz | 3, 1.0/1.1 |
| 7500 | 3.14 s | 27.8 / 29.1 % | 34.7 | 0.8 | 6.4 Hz | 3, 0.8/1.1 |
| 8000 | 3.36 s | 28.9 / 30.2 % | 56.4 | 13.3 | 8.4 Hz | 3, 1.0/1.1 |

Reading, with scope limits stated:

- **b0 = 1000: a strong ADRC-024-like ~22 Hz limit cycle** — band RMS
  40.3 dps over the 0.46 s the gate was open, motors working hard against it.
  The gate opened during the takeoff transient at ~9 % stick and the log ends
  in a disarm (pilot intent is not recorded), so this demonstrates ignition
  under ~2× loop-gain conditions, **not** steady-hover reproduction, and
  **not** identity with the SPEEDYBEE's 24–26 Hz mode (frequency-range
  similarity only).
- **Calm-stick tone energy drops from b0 = 2000 (med 1.6, max 4.8 dps) to a
  ~0.8–1.6 dps floor at b0 ≥ 3000 and stays flat through 8000** — no high-b0
  rebound in the calm windows (7000/8000: max 1.1 dps). The elevated
  slice-level values at 3000/7000/8000 carry maneuver energy (dominant peaks
  5–10 Hz, not the 22 Hz tone). Caveat: 1–3 calm windows per arm — these are
  point estimates, not distributions; the pilot's observed high-b0 rebound in
  his whole-log motor metric is **not confirmed by the gyro data, but not
  cleanly disproved** either (his metric also integrates pre-liftoff/gated
  samples, and the b0 = 6000 arm has only 1.26 s of gate-open data).
- **The minimum-noise b0 is not a plant calibration.** The band-limited
  doublet estimate on this same craft was ~1800–2100 (analysis-band caveat in
  [`pr15400-doublets/ANALYSIS.md`](../pr15400-doublets/ANALYSIS.md)); raising
  b0 shrinks the direct P/D path by 1/b0, so closed-loop noise falling with
  b0 is expected regardless of the true plant gain — consistent with the
  pilot's "high b0 feels sluggish" whoop observation. That the quieting
  mechanism is loop margin is a *leading hypothesis*, not established: b0
  also enters the ESO feedback (`b0·u`) and the z3 limit, so it is not a pure
  loop-gain knob.

Tracker impact: one line under ADRC-024 — *second-craft ADRC-024-like 22 Hz
instability observed at wc = 40 / wo = 100 / b0 = 1000; similarity of
mechanism and established airborne-hover reproduction remain unconfirmed.*

## Result 3 — law A/B redo with `adrc_hover_throttle = 28` (2026-07-21, `btfl_lawab2.bbl`)

The pilot re-flew the A/B the next day with the hover reference corrected and
deliberate throttle excursions (past 70 % at times). 9 sessions, same b5 tag,
tune 40/100/2000: logs 1,2 = QUADRATIC, 3,4 = SQRT, 5,6,9 = LINEAR,
7,8 = FIXED (headers confirm `adrc_b0_law` 0,0,1,1,2,2,3,3,2). This time the
arms **actually separated**: `debug[7]` max reaches ×2.42–3.00 (QUAD),
×1.28–1.64 (SQRT), ×1.93–3.00 (LINEAR), and stays pinned at ×1.00 (FIXED).
Gate opens exactly once per log. Reproduce with `jm_lawab2.py`.

Calm-stick ring windows (1 s, R/P setpoint std < 30 dps, max-axis 18–32 Hz
band RMS > 10 dps):

| law | logs | ring windows | worst |
|---|---|---|---|
| QUADRATIC | 1, 2 | 1/21 (takeoff, 18 % thr) | 12.2 dps @ 18 Hz |
| SQRT | 3, 4 | 0/18 | 9.1 dps @ 23 Hz (sub-threshold) |
| LINEAR | 5, 6, 9 | 0/33 | 7.5 dps @ 22 Hz |
| FIXED | 7, 8 | **7/24** | **25.6 dps @ 23 Hz** |

FIXED's ring windows sit both in the hover band (23–27 % collective) and
around throttle transients (windows whose p90 throttle reaches 50–100 %) —
exactly where the scheduled laws apply > ×1 b0 and FIXED does not.

Reading: on this craft, **any scheduling shape suppresses the ~22–23 Hz
mode; no scheduling rings**. The SPEEDYBEE's b5 inversion (SQRT ≫ LINEAR >
QUADRATIC incidence) does **not** reproduce here — the fine ordering among
scheduled laws is craft-dependent, while both crafts agree on the extreme:
the unscheduled (highest-gain-above-hover) arm is the worst. That is the
dose-response the gain-sensitivity story predicts, still short of proving
the margin mechanism. Caveats: not randomized, short backyard hovers,
n = 2–3 logs per arm; the pilot reported SQRT and LINEAR "sounded a bit
weird" — nothing law-dependent shows in the gyro above 40 Hz (motor lines
1–2 dps; log 9 carries a 378 Hz line, plausibly prop damage from the
power-line strike he reported), so the audible impression stays unresolved
(no audio sync). The wc/wo 2×2 on the SPEEDYBEE remains the decisive
experiment.

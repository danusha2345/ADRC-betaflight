# The applied-collective gate path, exercised on hardware

**Craft:** MAMBAF722 (DIAT), STM32F7X2, 5", 2207/1300 kv, 6S, **props off**, on the bench.
**Firmware:** built `Aug 8 2026 15:24:42` from `3c85c4b5a` (the z3 fix) plus the `axisD`
blackbox patch on branch `adrc-blackbox-dterm`.
**Tune:** `wc 60/60/60`, `wo 180/180/180`, `b0 4000/4000/4000`, `adrc_liftoff_throttle 10`,
`adrc_liftoff_gyro_dps 255`, `adrc_liftoff_hold_ms 25`, `adrc_hover_throttle 35`,
`thr_expo 0`, `thrust_linear 0`, `throttle_boost 5`, `vbat_sag_compensation 100`,
`dshot_bidir 0`. Full CLI state in `craft_config.txt`.
**Loop:** `looptime 125`, `pid_process_denom 2` (4 kHz), `blackbox_sample_rate 1/2`.

Four arms in one file (`applied_path_btfl_all.bbl.gz`), pilot varying stick and the rate at
which he rotated the frame by hand:

| arm | duration | frames | gate |
|---|---|---|---|
| 1 | 20.2 s | 40 553 | opens 13.4368 s |
| 2 | 39.9 s | 80 006 | **never opens** |
| 3 | 24.3 s | 48 730 | opens 7.8531 s |
| 4 | 22.9 s | 45 906 | opens 15.3960 s |

This is the **first applied-path opening identified in the logs we have reviewed**. It is not
claimed as a historical first: that would need an explicit inventory of every prior session run
through the same branch classifier.

## 1. Branch attribution

`adrc.c:426-503` provides exactly three ways to set `liftoff`: the commanded test
(`commandedThrottle >= adrc_liftoff_throttle`), the gyro test (`gyroPeak > adrc_liftoff_gyro_dps`
sustained `adrc_liftoff_hold_ms`, interlocked on `!throttleAtIdle`), and the applied test
(`throttle >= adrc_liftoff_throttle` sustained `ADRC_LIFTOFF_APPLIED_HOLD_S`, same interlock).

| arm | final commanded at open / max before | gyro at open / max before | applied at open |
|---|---|---|---|
| 1 | 6.3 % / 6.5 % | 110 / 113 °/s | **10.519 %** |
| 3 | 7.3 % / 7.6 % | 128 / 128 °/s | **11.924 %** |
| 4 | 5.5 % / 6.0 % | 120 / 125 °/s | **10.539 %** |

Commanded never reaches the 10 % threshold and gyro never approaches 255 °/s, so neither of the
other two branches can have fired.

**The comparison must use the final commanded collective, not the throttle stick.** Blackbox
records it as `setpoint[3] = mixerGetThrottle() * 1000` (`blackbox.c:1287-1292`). With
`throttle_boost = 5` the two differ; using the stick would be the wrong signal even though it
does not change the outcome here.

**The 250 ms hold is corroborated, not observed frame-by-frame.** At `P interval = 2` half the
PID iterations are unsaved. The saved-frame crossing brackets:

| arm | last saved below 10 % | first saved at/above | gate | first-good → open | last-bad → open |
|---|---|---|---|---|---|
| 1 | 13.186875 s | 13.187374 s | 13.436812 s | 249.438 ms | 249.937 ms |
| 3 | 7.602991 s | 7.603491 s | 7.853071 s | 249.580 ms | 250.080 ms |
| 4 | 15.145352 s | 15.145850 s | 15.395979 s | 250.129 ms | 250.627 ms |

Consistent with the runtime timer; not a proof about every unsaved iteration.

## 2. Arm 2: the idle interlock, on hardware

The applied collective sat at or above the 10 % threshold in roughly **31.6–32.2 thousand saved
frames** (the count depends on reconstruction method) and the gate stayed shut throughout. Final
commanded never exceeded **4.4 %**, below the `0.5 × adrc_liftoff_throttle` = 5 % floor.

Gyro in the same arm reached **359 °/s**, past the 255 °/s gyro threshold — and the gate still
did not open, because the same `throttleAtIdle` term gates the gyro branch at `adrc.c:456`. So
arm 2 is a negative control for the **shared idle interlock across both paths**, not an
applied-only test. That interlock was previously covered by unit tests only.

## 3. `z3` before the gate

`debug[2]/[5]/[6]` are zero for every pre-gate frame: 26 907 / 15 733 / 30 839 in the opening
arms, and all 80 006 in arm 2.

Precisely: the field is `round(z3/16)`, so a logged zero alone only bounds the internal value.
Exact zero follows from the code path — the arm reset sets `z3 = 0` (`adrc.c:186-200, 390-400`),
the inhibit is active for the entire closed-gate interval under `3c85c4b5a`
(`inhibitZ3Growth = !liftoff`), and from an initial zero every growth step is rejected while the
gate is shut.

## 4. The `axisD` blackbox patch, first flight

`axisD[2]` is present for the first time. Statistics:

| arm | `axisD[2]` range | std D | std P | D/P (std) | zero frames |
|---|---|---|---|---|---|
| 1 | −26 … +59 | 9.779 | 35.168 | 0.278 | 9.6 % |
| 3 | −59 … +41 | 10.603 | 38.772 | 0.274 | 19.9 % |

The zeros are `lrintf` quantisation of a continuous term below 0.5 — short runs around crossings,
longer runs when the craft is nearly still. The header carries `axisD[2]` for the whole session,
so the field cannot appear and disappear.

**Why 0.27 here and ≈2.55 on @dedlike's craft are consistent.** For a closed-gate sinusoid with
`z3 = b0·u = 0`, the LESO gives

```
|D/P| = 2·wo·ω / (wc·√(ω² + wo²))
```

which is 0.115 at 0.55 Hz and 0.217 at 1.04 Hz for this craft's `wc 60 / wo 180` — matching slow
bench content — and 2.50 at 34 Hz for `wc 60 / wo 80`, against 2.55 measured. `b0` cancels. The
order-of-magnitude gap is expected and serves as a check on the patch rather than a warning about
it. The high-frequency D/P of *these* logs is not worth quoting: there is almost no gyro energy at
30–38 Hz here, so the ratio would be set by the quantisation floor.

## 5. Normalising the applied collective when sag compensation is on

The first pass on these logs concluded the gate had opened with no condition met — applied 8.84 %
against a 10 % threshold — which sent a search for a firmware bug that does not exist. The error
was in the analysis: with `vbat_sag_compensation = 100` and a fresh 6S pack, `motorRangeMax` is
pulled down, so the real `motorOutputRange` is ~1579–1651 rather than the static 1889 the header
advertises.

Three details are easy to get wrong, and all three were wrong on the first attempt:

- `getBatterySagCellVoltage()` is a **5 Hz PT1 updated on the 200 Hz task** (τ ≈ 31.83 ms) — not a
  per-frame filter and not a half-second one;
- the cell count here is **forced to 6**; `vbatref` is the unfiltered start voltage, not the
  detector input (the auto formula would also give 6 at 25.13 V, but that is a coincidence, not a
  derivation);
- `dyn_idle_min_rpm = 30` is configured but **inactive** because `dshot_bidir = 0`, so
  `motorRangeMin` really is 158.

A cross-check that avoids battery voltage entirely — reconstructing the lower-clamp collective
from logged `axisP+I+D+F` and the QUAD X coefficients with `yaw_motors_reversed = ON` — agrees
with the sag reconstruction to a median 0.044–0.053 percentage points over the relevant windows.

**Scope.** @dedlike's analysis is unaffected: that craft has `vbat_sag_compensation = 0`.
The earlier `test13` bench logs keep their gate verdicts under either cell-count scenario, but the
"1.7 % error on session 1" figure quoted there is a *conditional five-cell calculation*, not a
measured fact — neither `batteryCellCount` nor `force_battery_cell_count` appears in a blackbox
header. Adding a `batteryCellCount` and filtered-sag field would remove the guesswork.

## 6. Reproduction

```
gunzip -k applied_path_btfl_all.bbl.gz
blackbox_decode applied_path_btfl_all.bbl
python3 t14.py    # per-arm branch reconstruction (static normalisation — see §5)
python3 t14b.py   # frame-by-frame view of the arm-1 transition
python3 t14c.py   # sag-corrected collective, the corrected numbers above
python3 t14d.py   # arm-2 negative control, axisD[2] stats, pre-gate z3
```

`t14.py` deliberately keeps the *uncorrected* normalisation: it is what produced the apparent
"no condition met" contradiction, and re-running it shows how the §5 error presents.

`CLAIMS_FOR_REVIEW.md` is what was submitted for adversarial review; `CODEX_REVIEW.md` is the
verdict, including the twelve corrections applied above and the independent recomputation.

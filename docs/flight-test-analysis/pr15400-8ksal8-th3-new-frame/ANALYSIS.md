# TH3 new-frame 2S/3S/4S working points

Date: 2026-08-24, refreshed after the comment edit. Source: @8ksal8's report
and two archives in
[PR #15400 comment 5395710009](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5395710009).
The pilot transferred the TH3 hardware to a new 2.5-inch frame, retuned it for
2S, 3S and 4S, and described it as the best-flying variant by feel so far. One
free-flight log is present for each pack. This records a pilot-reported good
working variant on this craft; one flight per pack is not repeatability or a
general-safety result.

Pilot-reported hardware and weight: 1204.5 5022 KV motors, 100 g without a
battery, and 127/146/152 g with the 2S/3S/4S packs. This is a new airframe
configuration and is kept separate from the earlier
[three-pack TH3 corpus](../pr15400-8ksal8-th3/). The old and new logs do not
form a controlled A/B: the frame, tune and flight input all changed. Most
plainly, yaw moved from `wc=120`, `b0=12500/17319/22050` on the old frame to
`wc=47`, `b0=1965/2624/3133` here.

## Provenance and decode

The byte-identical original/replacement 2S attachment has SHA-256
`69a7a1e9ed8819fa286e584de5e65e9a097039cec8caeef009678c44e7dbcc60`
and contains one 14,667,776-byte BBL. The later 3S/4S attachment is 25,171,810
bytes, has SHA-256
`abb7477cd11d8156e926ffc64a8e148ecb90dba33f0a06abe3c730de0bc684c3`,
and contains 15,519,744-byte 3S and 16,672,768-byte 4S BBLs.

All three decode as one log block with `blackbox_decode` from `blackbox-tools`
commit `f832acf9cd9dbe5ad8220de1a5f4eb4021523d72` (decoder SHA-256
`6b35322c22d5d9e3d23dd171a9ac0424e2fb38f9b8a2232425155d47cd17d23e`).
The decoder reports zero failed frames and 10/1/10 unreadable loop iterations
for 2S/3S/4S. `P interval=4` accounts for the expected 75% unsaved PID
iterations; it is not treated as corruption. Source-artifact hashes are in
[MANIFEST.sha256](MANIFEST.sha256); the attachments and raw BBLs are not
duplicated in this source tree.

## Configurations and mode

All three headers report b9 `919116fed`, board `BEFH BETAFPVF722`, craft name
`THIII+ Freestyle`, ADRC with SQRT law, `wc=110/110/47`, common `wo=150`,
the dedicated ADRC gyro PT2 at 200 Hz, 4 kHz PID and approximately 1 kHz saved
main frames. Configurable gyro/D-term software LPFs/notches and dynamic notch
are disabled. Bidirectional DShot is enabled while RPM-filter harmonics are
zero.

| pack | `b0` R/P/Y | ADRC hover | motor output limit | saved duration |
|---|---|---:|---:|---:|
| 2S | `4912/2947/1965` | 50% | 100% | 264.978 s |
| 3S | `6560/3936/2624` | 36% | 100% | 285.400 s |
| 4S | `7832/4699/3133` | 32% | 85% | 309.816 s |

The ordinary decoder labels these sessions `ANGLE_MODE`, but the raw mode mask
is `1` after the initial pre-S-frame rows. Against the matching firmware
`boxId_e`, that is ARM only: these are Acro flights. `FEATURE_AIRMODE` is off
and no `BOXAIRMODE` bit appears. The gate opens 3.304/2.301/3.057 s after the
first 2S/3S/4S saved frames and never closes.

## Flight metrics

| pack | frames | tracking median R/P/Y | tracking p90 R/P/Y | pre-terminal max `abs(P+I+D+F)` R/P/Y |
|---|---:|---|---|---|
| 2S | 266,980 | `7/10/14` deg/s | `24/28/36` deg/s | `191/256/188` |
| 3S | 287,464 | `9/11/15` deg/s | `27/27/38` deg/s | `197/324/184` |
| 4S | 312,022 | `10/11/16` deg/s | `29/28/41` deg/s | `135/304/165` |

The 2S and 4S logs contain zero raw controller-sum limit hits. The 3S exception
is confined to its final 12 main frames, covered separately below; excluding
the final 20 ms leaves zero hits and the tabled maxima. Exact upper-motor-rail
contact is likewise sparse and concentrated at high commanded throttle:

| pack | upper-rail frames | share | throttle setpoint min / median / max on those frames |
|---|---:|---:|---|
| 2S | 1,011 | 0.3787% | `789/985/1000` |
| 3S | 1,264 | 0.4397% | `813/1000/1000` |
| 4S | 601 | 0.1926% | `926/1000/1000` |

This is high-command saturation, not the zero-command mixer-driven spool-up
signature from ADRC-028.

For a command-neutral check, each saved timeline was resampled to 1 kHz. A
fourth-order 20–100 Hz band-pass was applied to `gyro - setpoint`; two-second
windows with 0.5 s hop were accepted when at least 90% of samples had all three
`abs(setpoint) <= 30 deg/s`.

| pack | accepted windows | max 20–100 Hz residual RMS R/P/Y | maximum axis |
|---|---:|---|---:|
| 2S | 53 | `1.0992/1.6167/1.1516` deg/s | 1.6167 deg/s |
| 3S | 85 | `3.2792/1.9757/1.8552` deg/s | 3.2792 deg/s |
| 4S | 69 | `2.3435/4.9821/1.7776` deg/s | 4.9821 deg/s |

No sustained high-frequency self-excitation is detected in the accepted
command-neutral windows. This is a negative result scoped to three flights and
this detector; it does not establish a universal margin for `wo=150`.

## The terminal 3S transient

The final 12 saved frames of the 3S log span 11.915 ms and carry a sudden
multi-axis gyro/P/D transient. Raw controller sums reach
`3642/2980/1469`, motors redistribute across their range, and the BBL ends
immediately. No raw sum reaches its configured limit before this terminal
group; excluding the last 20 ms gives `197/324/184` maxima.

The sequence is consistent with a terminal impact/contact rather than a
preceding in-flight self-excitation. A hard landing, catching an object or a
fall are plausible physical contexts, but the PR comment does not annotate the
event. The physical cause therefore remains unconfirmed by the public artifact;
the log-supported statement is the timing distinction.

## ADRC-029 instrumentation

These are b9 logs, so `z3` still uses the legacy `/16` signed-int16 debug field.
Saved-frame rail shares are:

| pack | roll | pitch | yaw |
|---|---:|---:|---:|
| 2S | 0.3877% | 0.0172% | 0% |
| 3S | 0.5197% | 0.2616% | 0.0017% |
| 4S | 0.5198% | 0.1378% | 0% |

The small rail fractions censor peak `z3` comparisons but are not a failure
classification. Outside the terminal 3S group, controller sums remain below
their limits while the telemetry field clips, which is the ADRC-029
instrumentation distinction.

## Metadata discrepancy

The comment reports 1204.5 5022 KV motors, while all three Blackbox headers
store `motor_kv=1960`. In this source revision `motor_kv` is a
configuration/header metadata field and has no control-law reader, so the stale
value does not alter these flights. It should nevertheless be corrected before
later logs are used for hardware-provenance comparisons.

## Supported conclusion

The three long Acro logs are consistent with the pilot's statement that this is
a good working variant for the rebuilt TH3: tracking remains controlled, calm
windows contain no detected sustained self-excitation, and ordinary motor-rail
contact is sparse and high-throttle-associated. The terminal 3S event is
separated explicitly rather than counted as a flight-wide instability. One
flight per pack does not establish repeatability, a cross-craft safe `wo`, or a
replacement default.

## Reproduction

```bash
DEC=/absolute/path/to/blackbox_decode
ROOT=/absolute/path/to/downloaded-and-extracted-artifacts

for pack in 2s 3s 4s; do
  "$DEC" --debug --unit-frame-time us --unit-flags raw --save-headers \
    --output-dir "$ROOT/decoded-raw-flags" \
    "$ROOT/TH3_Freesyle_${pack}_new_frame_tune_btfl_001.bbl"
done

uv run --with numpy --with scipy analyze.py \
  --pair "$ROOT/decoded-raw-flags/TH3_Freesyle_2s_new_frame_tune_btfl_001.01.csv" \
         "$ROOT/decoded-raw-flags/TH3_Freesyle_2s_new_frame_tune_btfl_001.01.headers.csv" \
  --pair "$ROOT/decoded-raw-flags/TH3_Freesyle_3s_new_frame_tune_btfl_001.01.csv" \
         "$ROOT/decoded-raw-flags/TH3_Freesyle_3s_new_frame_tune_btfl_001.01.headers.csv" \
  --pair "$ROOT/decoded-raw-flags/TH3_Freesyle_4s_new_frame_tune_btfl_001.01.csv" \
         "$ROOT/decoded-raw-flags/TH3_Freesyle_4s_new_frame_tune_btfl_001.01.headers.csv"
```

The expected output is preserved in [analysis-report.txt](analysis-report.txt).

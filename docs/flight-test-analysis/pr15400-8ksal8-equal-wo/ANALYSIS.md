# Air65 equal-`wo` working points and fitter follow-up

Date: 2026-08-23/24. Source:
[PR #15400 comment 5387719868](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5387719868).
Independent reply:
[comment 5392312959](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5392312959).

Three ZIP files and six contained BBL files were hashed and decoded with
`blackbox_decode` from `blackbox-tools` commit
`f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`. All six files decode as one clean
log block with zero failed frames. Hashes are in
[MANIFEST.sha256](MANIFEST.sha256). The manifest identifies the original
attachments, extracted BBL files and derived fitter adapter; the 41 MiB raw
corpus is not duplicated in this source tree.

## Provenance and configurations

All six logs report:

- firmware `Betaflight 2026.6.0-alpha (919116fed) STM32G47X`;
- board `BEFH BETAFPVG473_V2`, craft `AIR65 R`;
- ADRC selected (`pid_type=1`), SQRT throttle law;
- bidirectional DShot enabled, RPM filter harmonics zero;
- configurable software gyro LPF1/LPF2, dynamic notch and gyro notch disabled;
- dedicated ADRC gyro PT2 at `adrc_gyro_lpf_hz=135`.

`gyro_hardware_lpf=0` means the sensor's normal hardware mode, not a literal
absence of every hardware filter. The pilot's "only filter" description is
accurate for the added configurable software path feeding ADRC, not for the
physical IMU front end.

The raw mode masks correct the normal decoder's legacy labels:

- `Y_wc_38/40/42` and `fit_fly_btfl_003`: raw mask `1` (ARM only), therefore
  Acro;
- `btfl_077` and `fit_wobble_btfl_001`: raw mask `3` (ARM + ANGLE), therefore
  Angle;
- `FEATURE_AIRMODE` is off and no saved slow frame contains the `BOXAIRMODE`
  bit. Airmode is not active in these logs.

The flight configurations are:

| log group | `wc` R/P/Y | `wo` R/P/Y | `b0` R/P/Y |
|---|---|---|---|
| equal-`wo` sweep | `84/84/38`, `84/84/40`, `84/84/42` | `140/140/140` | `5849/3509/2340` |
| fitter input (`btfl_077`) | `84/84/42` | `140/140/140` | `5849/3509/2340` |
| post-fit wobble/flight | `47/47/28` | `140/140/140` | `5398/3404/1676` |

## Equal-`wo` flight evidence

The three `wc=38/40/42` logs run for 71.89, 126.47 and 105.62 seconds. A
time-aware check resampled the real saved-frame timestamps to 800 Hz, trimmed
five seconds from each end, and measured the yaw gyro in 30–80 Hz:

| yaw `wc` | peak | band RMS | start/min/end voltage |
|---:|---:|---:|---|
| 38 | 56.05 Hz | 1.89 deg/s | 3.80 / 2.96 / 3.50 V |
| 40 | 57.42 Hz | 1.69 deg/s | 4.24 / 2.78 / 3.50 V |
| 42 | 55.47 Hz | 2.12 deg/s | 4.23 / 2.97 / 3.47 V |

The weak ~55–57 Hz descriptor persists across all three cells. These logs do
not show the fast arm-time growth pattern recorded in ADRC-028/Mamba, and their
length is consistent with the pilot's report that the tune is flyable.

The evidence does not identify a universal boundary at yaw `wc = 0.5 ×`
roll/pitch `wc`: only successful 38/40/42 cells are present, each is a single
flight, starting pack state differs, and no immediately higher cell is in this
archive. The supported result is an Air65 working heuristic and existence
point, not a cross-craft stability rule.

## Post-fit logs

The two post-fit logs carry the exact selected values
`wc=47/47/28`, `wo=140/140/140`, `b0=5398/3404/1676`. `fit_wobble` is the
deliberately excited Angle session; `fit_fly` is a 168.53 s Acro session. This
is practical flight evidence for the selected tune, not a controlled A/B
against the original tune.

ADRC `z3/16` logging clips in parts of the post-fit Acro log (roll 6.61%, pitch
2.51%, yaw 0.72% of saved frames). That is the known ADRC-029 instrumentation
limit in b9-and-earlier logs, not by itself a flight failure, but it censors
peak `z3` comparisons.

The fitter replay, input limitation, recovered `b0` table, `wc` brackets and
constant-`wo/wc` sweep semantics are documented separately in
[`pr15400-jmsweng-autotune/`](../pr15400-jmsweng-autotune/).

## Supported conclusion

The corpus supports two useful, flight-tested Air65 working tunes and confirms
the stated modes/configuration. It does not establish the half-`wc` heuristic
as a general stability boundary, and the fitter does not independently select
`wo`. No additional flight programme is prescribed here.

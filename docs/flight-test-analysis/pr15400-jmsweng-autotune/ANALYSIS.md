# ADRC plant fitter/autotune audit

Date: 2026-08-22, refreshed 2026-08-24. Source release comment:
[PR #15400 comment 5376183361](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5376183361).
The initial public audit is
[comment 5380715005](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5380715005).

The audited source is `jmsweng/ADRC-betaflight` commit
`be20527781ebb4bd4586bdba2299ad954130dd7c`. The local `plant_fit.py` Git blob
`05d65521125012277ee6d7869866832b57a3ccc4` matched the file at that commit.
Artifact SHA-256 values are in [MANIFEST.sha256](MANIFEST.sha256). The manifest
identifies the pinned source and replay outputs; those upstream/replay files
are not duplicated in this source tree.

## Included example replay

The uploaded notebook and `chirp flight.csv` complete from a clean Python
environment. Re-running the current code on 2026-08-24 reproduces:

| axis | controller-free `b0` | eRPM `b0` | gap | max `wc` @45° | max `wc` @60° |
|---|---:|---:|---:|---:|---:|
| roll | 5631 +/- 501 | 5157 +/- 66 | 9% | 74 +/- 0.9 | 57 +/- 0.8 |
| pitch | 3852 +/- 341 | 3134 +/- 54 | 21% | 72 +/- 0.9 | 55 +/- 0.8 |
| yaw | 3650 +/- 475 | 6533 +/- 146 | 57% | 87 +/- 1.8 | 82 +/- 1.7 |

The published code therefore no longer produces the earlier unsafe yaw
`wc=271–281` values. The identification-band guard bounds the uploaded example
near 82–87 rad/s instead.

The notebook's own warnings remain part of the result, not optional prose:

- no axis has a sustained measured -3 dB point inside the coherent band;
- closed-loop peaks are about +10 dB roll, +13 dB pitch and +21 dB yaw;
- all axes have an unresolved second pole and a warning that `wc` may be
  inaccurate;
- yaw crossover lies above the identified band, so its phase margin is an
  extrapolation;
- yaw controller-free/eRPM `b0` differs by 57%.

These are useful diagnostics. They do not support treating every printed
number as an automatic tune recommendation. The current UI warns but does not
fail closed.

## Input contract

The tool consumes a Blackbox Explorer-style CSV containing `axisSum[]`. A plain
`blackbox_decode` CSV contains the individual P/I/D/F terms but not `axisSum`.
The notebook still lists direct BBL import as a TODO and does not pin a
Blackbox Explorer export version or requirements file.

For a general corpus, synthesizing `axisSum=P+I+D+F` is ambiguous when output
is clipped, recovery logic is active, or another term/path changes the applied
sum. The uploaded example itself contains rows where that equality is not
exact. Raw-BBL input or a pinned exporter/column contract remains necessary
for a fully reproducible public autotune workflow.

## Air65 non-chirp `btfl_077` sensitivity replay

@8ksal8 later supplied the raw `btfl_077` wobble log in
[comment 5387719868](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5387719868).
Its reconstructed sums remain below their configured limits (maximum absolute
R/P/Y sums `83/179/269`), so `P+I+D+F` is a useful sensitivity adapter for this
specific log. It is still not a byte-identical replay of the unavailable
Blackbox Explorer CSV.

The current fitter reproduces the pilot's remembered controller-free `b0`
values to display precision:

| axis | controller-free `b0` | max `wc` @45° | max `wc` @60° | flight choice |
|---|---:|---:|---:|---:|
| roll | 5398 +/- 131 | 57 | 40 | 47 |
| pitch | 3404 +/- 85 | 52 | 37 | 47 |
| yaw | 1676 +/- 40 | 28 | 28 | 28 |

Thus `47/47/28` is a manual choice between the two printed roll/pitch margins,
with yaw matching the table. It is not an obviously mistaken reading.

## `wo` is not estimated

The current tool accepts `wo` as an input and does not independently recommend
it. More specifically, `suggest_bandwidth()` computes `ratio = wo_cfg/wc_cfg`
and evaluates each candidate `wc` with `wo = ratio*wc`. The displayed
`wc_max` values therefore belong to a constant-`wo/wc` path.

If a pilot copies the new `wc` but leaves the old `wo` fixed, the final pair is
not the pair evaluated by that sweep. A direct sensitivity check of the
flight-tested `47/47/28`, common `wo=140`, and fitted `b0` values changes the
reported margins and retains model/band warnings, especially on yaw. Because
this is a non-chirp log with the warnings above and a derived `axisSum`, those
margins are guidance rather than a verdict on the flight-tested tune.

The least ambiguous future tool output would show the paired `wo` beside every
`wc_max` and separately evaluate an explicitly selected final
`wc/wo/b0` triple. This is a tool-output recommendation, not a request for more
flight testing.

## Status

- Example execution: **reproducible** at the pinned commit.
- `b0` recovery on the supplied Air65 wobble log: **closely reproduced with a
  stated derived-input limitation**.
- Independent `wo` recommendation: **not implemented**.
- Automatic/fail-closed tune recommendation: **not established**; warnings and
  input provenance must travel with the numeric tables.

# Repeated Air65/Petrel yaw `wc`/`wo` sweeps (28 flights)

Date: 2026-08-21/22. Source: @8ksal8's six archives in
[PR #15400 comment 5371353409](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5371353409).
The independent public summary is
[comment 5380714469](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5380714469),
with the later mode-label correction in
[comment 5385346816](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5385346816).

All six ZIP files were hashed, all 28 BBL files were extracted and decoded with
`blackbox_decode` from `blackbox-tools` commit
`f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`, and every cell contains two
flights after grouping by Blackbox headers. Archive and per-BBL hashes are in
[MANIFEST.sha256](MANIFEST.sha256). The manifest identifies the original
attachments and extracted inputs; the 252 MiB raw corpus is not duplicated in
this source tree.

## Provenance corrections

- `Petrel75_yaw_wc_50_1.bbl` carries yaw `wc=60`, while
  `Petrel75_yaw_wc_60_1.bbl` carries `wc=50`. The names were swapped; header
  grouping restores two flights in each cell.
- Those two logs retain `Craft name=AcroBee75`. Their device UID and board match
  the other Petrel logs, so this is stale craft-name metadata, not a third FC.
- The normal decoder labels raw mode bit 0 as `ANGLE_MODE`. Firmware stores
  `rcModeActivationMask` in the legacy field named `flightModeFlags`; raw values
  are `1` (ARM only) throughout these flights. They are Acro flights, consistent
  with the pilot's correction, not Angle flights.

## Pre-specified 30–80 Hz descriptor

The original metric was the yaw-error Welch argmax in 30–80 Hz with
`nperseg=4096`, after resampling to a uniform timeline and trimming three
seconds from each end. At the same yaw `wc`, lowering `wo` moves this descriptor
downward at `wc=50/60` on both craft:

| craft | `wc` | fixed `wo=80` mean peak | lower `wo` mean peak |
|---|---:|---:|---:|
| Air65 | 50 | 47.79 Hz | 32.27 Hz (`wo=50`) |
| Air65 | 60 | 50.17 Hz | 38.56 Hz (`wo=60`) |
| Petrel | 50 | 62.71 Hz | 46.51 Hz (`wo=50`) |
| Petrel | 60 | 63.50 Hz | 43.83 Hz (`wo=60`) |

That table is reproducible, but its interpretation is deliberately narrow:

- on Air65 the peaks are weak (prominence about 1.6–4.4), seven of 28 corpus
  peaks move by more than 3 Hz when the Welch window changes, and 13 of 28 move
  by more than 3 Hz between flight halves;
- Air65's integrated 30–80 Hz centroid remains about 53–56 Hz instead of
  following `wo`, so Air65 does not establish a shift of the whole spectral
  shape;
- Petrel gives the stronger same-`wc` association: its integrated band shape
  moves in the same direction at `wc=50/60`, although some low-`wo` repeats are
  non-stationary;
- in 16 of 28 logs, including all 14 Air65 logs, the largest 10–100 Hz component
  is near 10–11 Hz. The 30–80 Hz result is a band-limited descriptor, not the
  globally dominant aircraft motion.

The supported statement is therefore an observed, estimator-sensitive
association. It is not a confirmed cross-craft observer mode and does not
identify a mechanism.

## Motor-order and command-neutral checks

Motor phase was integrated from each eRPM stream and the 30–80 Hz yaw signal
was regressed against orders 1–6 for all four motors. Even after selecting the
best of 24 motor/order candidates per log:

- median explained variance: `0.0089%`;
- maximum explained variance: `0.0332%`;
- maximum coherent RMS fraction: `1.82%`;
- the same pipeline recovers `66.39–66.95%` from a synthetic phase-locked
  signal on the measured motor phase.

No detectable phase lock to orders 1–6 was found. This negative result does
not exclude every possible alias, structural mode, electrical line, or
closed-loop interaction.

The two Petrel `80/80` flights have whole-log 30–80 Hz RMS values of
`34.55/25.51 deg/s`. In their trimmed command-neutral intervals those values
fall to `3.02/1.62 deg/s`. The large whole-log amplitude is therefore
manoeuvre/excitation-associated rather than continuously self-sustaining at
neutral command.

## The earlier short `60/60` event

The earlier 12.82 s `wc=wo=60` event is not an isolated test of that pair. It
also used yaw `b0=878` (versus `2340` here), different deadbands, and other
header differences. Its band RMS was `55.53 deg/s`; the two new `60/60` logs
use yaw `b0=2340`, run for 111/108 s, and measure `1.29/1.16 deg/s`. The old
event belongs to the combined configuration. The repeated cells do not
reproduce it with the current `b0`.

## Impact on the A–E investigation plan

- **A, documentation:** the verified signal/filter path and delay/margin cost
  can be documented; the 30–80 Hz line must not be attributed to the ESO.
- **B, minimal filtering:** no second-craft RPM-only A/B exists; no general
  filter recommendation follows from this corpus.
- **C, separate gyro tap:** still an architectural option, not a demonstrated
  correction for the measured line.
- **D, voltage compensation:** reduced to an offline fitter discriminator; the
  flight corpus does not justify a new compensation feature.
- **E, attribution:** the `wo` sweep and orders 1–6 phase check are complete.
  The result is mixed: a stronger Petrel association, a weak/sensitive Air65
  descriptor, and no detected motor-order phase lock.

No new flight programme is prescribed by this document. It records what the
published corpus establishes and where the evidence stops.

# AcroBee75 filter ladder: the gyro stages one at a time

**Data**: seven short test arms by @8ksal8 on the same AcroBee75 and the same ADRC tune as the
[filters pair](../pr15400-8ksal8-acrobee/) (`wc 100/100/50`, `wo 120/120/80`,
`b0 3923/2353/1569`), posted 2026-08-15 in PR #15400. Exactly **three intended profile keys**
change across the ladder (`overview.py` checks the union): `gyro_lpf1_dyn_hz` (250,500 when
on), `gyro_lpf2_static_hz` (500 when on), `rpm_filter_harmonics` (1 when on); the remaining
per-arm differences are the measurement/runtime keys — `vbatref` and the two `rc_smoothing_*`
values, all printed per arm. No dynamic notch, no `yaw_lowpass`, no dterm filters are
configured in any log — fewer stages in play than in the first pair. One runtime state is
not controlled by the profile: the measured RC-smoothing values follow the ELRS link rate, and
the LP2 arm ran at a different measured link (cutoffs 125,125 / rx 334 Hz against 62,62 /
166–167 Hz for the rest — `overview.py` prints all seven). The seven configurations cover
seven of the eight {LP1, LP2, RPM} cells (LP1+LP2 without RPM was not flown). **One arm per
configuration** — every number is a single observation, and pilot input, segment length and
pack state differ per arm. Every AcroBee-derived number below is printed by a script in this
directory; none is hand-copied.

Each arm contains one BOXAIRMODE activation on a fresh-ish pack (median pack voltage over the
first second of each activation: 8.30–8.62 V) —
deliberately the regime where the first pair's full stack was reported unflyable. `ladder.py`
restricts all metrics to those segments (numeric mode mask, first 0.3 s after the flip
trimmed).

## The ladder, inside the airmode segments

| config | dur | vbat in seg | yaw 30–80 gyro | cmd P+D | band peak | 45–55 prom | rail |
|---|---|---|---|---|---|---|---|
| off | 17.2 s | 7.60–8.58 | 4.08 | 13.8 | 63.0 Hz | 2× | 17 |
| LP1 | 10.2 s | 8.28–8.83 | 10.60 | 42.5 | 53.2 Hz | 1030× | 0 |
| LP2 | 15.9 s | 8.06–8.70 | 5.51 | 21.4 | 55.6 Hz | 31× | 0 |
| RPM | 15.3 s | 7.78–8.57 | 7.21 | 28.8 | 54.2 Hz | 255× | 0 |
| LP1+RPM | 13.8 s | 7.22–8.44 | 30.59 | 123.2 | 52.7 Hz | 9684× | 51 |
| LP2+RPM | 14.7 s | 8.08–8.81 | 8.74 | 35.1 | 52.7 Hz | 125× | 0 |
| LP1+LP2+RPM * | 2.2 s | 6.97–8.66 | 27.75 | 110.3 | 51.1 Hz | 5290× | 114 |

\* the full-stack segment ends with the arm after 2.2 s (post-trim) with the pack sagging
hard — censored by whatever ended the arm, not rankable against the full-length segments.

Observations, all within single-observation limits (`ladder.py`; the prominence is a
spectral-shape descriptor with no validated threshold — no binary presence/absence claims):

- The all-off segment's 45–55 Hz prominence is 2× (band peak 63.0 Hz); the six on-config
  segments show prominences of 31×–9684× — a large descriptor difference, directionally
  consistent with the tester's "individually, all do something to some degree".
- The largest full-length values are in a combination cell, **LP1+RPM** (gyro 30.59, command
  123.2, 9684×, 51 rail samples in the segment), with its pack sitting lower than the
  single-stage segments — directionally consistent with his "combined ... multiplies"; with
  one arm per cell and the LP1+LP2 cell not flown, no interaction is estimated.
- The LP1-only segment shows a larger 30–80 Hz RMS than the LP2-only segment (10.60 vs 5.51,
  1030× vs 31×) — one segment each, and the LP2 arm ran on a different measured link rate.
- Whole-log error medians (`overview.py`; they mix pre-airmode hover with the segment and are
  not frequency-decomposed): off runs 20/20/27 deg/s alongside the tester-reported buzz,
  RPM-only reaches 4/4/5, and the RPM-only airmode segment carries a 30–80 Hz gyro RMS of
  7.21 deg/s with zero rail samples — stated as the joint observation on one arm, not a
  ranking and not a buzz-removal proof.

## Caveats

- One arm per cell; arms flown back-to-back with different pack states, segment lengths and
  stick input. The table is seven observations, not a factorial analysis.
- The 45–55 Hz prominence is a spectral-shape descriptor, not a detector with a validated
  threshold; the per-segment RMS values are the amplitude comparison.
- The association direction is the same as in the [first pair](../pr15400-8ksal8-acrobee/):
  configurations with gyro-chain stages in the loop show more 30–80 Hz yaw content. As there,
  this is an observed association; single non-randomised arms establish no causal edge, and a
  stage's attenuation and phase effects are not separable.
- z3 telemetry rails are negligible in this corpus (`overview.py`); the liftoff gate was open
  84.9–92.4 % of the arms.

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 overview.py
python3 ladder.py
python3 summaries.py --check
```

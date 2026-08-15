@8ksal8 You flew the ladder faster than I could ask for it. Across your seven logs three
profile keys move (LP1 dyn 250,500 / LP2 static 500 / RPM 1 harmonic) — no notches, no yaw
lowpass, no dterm filters, same tune everywhere; one uncontrolled rider is that the LP2 arm
ran at a different measured RC link rate (334 vs 166–167 Hz, printed in the write-up).
Analysis:
[`pr15400-8ksal8-acrobee2/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-acrobee2).

Inside the airmode segments (one per arm, from the mode mask), the 30–80 Hz yaw picture per
configuration — one arm per cell, so these are seven single observations, not a ranking:

- **All off**: the 45–55 Hz prominence sits at 2× (a shape descriptor, no threshold claimed);
  the whole-log medians are 20/20/27 deg/s — alongside the buzz you reported (the medians
  themselves aren't frequency-decomposed).
- **The three single-stage segments** recorded prominences of LP2 31×, RPM 255× and LP1
  1030× — directionally consistent with your "individually, all do something". The LP1-only
  segment shows a larger 30–80 Hz RMS than the LP2-only one (10.60 vs 5.51 deg/s) — one
  segment each, and your LP2 arm was the different-link-rate one.
- **LP1+RPM carries the largest full-length segment values** (30.59 deg/s, 9684×, 51 rail
  samples), pack sitting lower than the single-stage arms — directionally consistent with your
  "combined, the effect multiplies"; with one arm per cell and no LP1+LP2 cell, I can't
  estimate an interaction.
- The **full stack's airmode segment ended with the arm about 2 s after the flip** with the
  pack sagging and 114 rail samples — censored by whatever ended it, so it isn't rankable; a
  short activation ending with the arm on a fresh-ish pack is also the pattern your first
  report described.
- On these single arms, **RPM-only jointly shows whole-log medians of 4/4/5, a segment
  30–80 Hz gyro RMS of 7.21 deg/s and zero rail samples** — a joint observation on one arm,
  not a ranking.

Same limits as before: single non-randomised arms, association not causation, and a stage's
attenuation vs phase effects aren't separable from flight logs. Thank you for flying it — this
ladder plus the first pair give a per-stage view of the filter-chain/ADRC association on one
craft.

@8ksal8 The test flight is analysed —
[`pr15400-8ksal8-b0calc/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-b0calc)
— and your C vote is noted in the tally. Taking the three parts in turn:

**The flight.** Tracking medians 10/10/11 deg/s (p90 28/29/31) over 190.0 s — a flyable tune
you attribute to the estimator, which is the practical point of one. (Provenance note: the
flown b0 header, 5849/3509/2340, sits about 1.6 % below the comment's worked example
5945/3567/2378 — close, but "derived from the estimator" is your report, not a log fact.) One header note first: with your filter set zeroed the ADRC observer's own input
PT2 is still active (`adrc_gyro_lpf_hz = 185`), so this is "main profile chain out of the
loop", not "no filtering at all". On the tail wag, I have to stop short of confirming it from
this log: the cruise yaw error content sits at very low frequency (spectrum maximum 1.57 Hz)
but your yaw *setpoint* has substantial content right there too (setpoint–error coherence
0.59), so the log can't separate a wag from ordinary tracking of your own yaw input — a
stick-still segment would separate them. What the header does say: your yaw runs
`wo/wc = 80/78 ≈ 1.03` against 1.67 on roll/pitch, and wanting yaw wc/wo up at roll/pitch
levels is exactly your case for option C. (For accuracy: jmsweng's earlier warning was about
`wc > wo`, which this tune avoids — barely; he has also floated `wc = wo` as a workable
default.)

**The formula.** The honest split: the log can't validate the inputs directly — mass and
wheelbase aren't recorded, and while `vbat × amperage` gives a pack-level electrical proxy (it
peaks at 68.57 W here), that isn't per-motor continuous mechanical power, so the K chain still
needs your external numbers. K is calibrated on two quads so far, by your own account. One
arithmetic note on the axis-weighting section as posted: the 50/30/20 split is equivalent to
roll-relative 100/60/40, while your corrected ratios say 100 / 75–85 / 40–50 — the two
prescriptions agree on yaw (both allow 20 %) but disagree on pitch, worth reconciling before
others copy either. The cleanest check coming is jmsweng's fitter: fit this log, compare the
fitted per-axis b0 with the formula's prediction — and with your mass/wheelbase plus a stated
power estimator that comparison could also feed K another calibration point (the comment
doesn't say whether this Air65 is already one of your two). As a pre-first-flight seed feeding the
fit→fly workflow, the formula and the fitter are complementary, not competing.

**The punch event.** As recorded: the throttle first reaches 2000 at 169.22 s on a sagging
pack (a motor first touches the rail at 169.17 s; vbat bottoms at 2.85 V), the craft tumbles
(gyro peaks of 2828/2829/2000 deg/s), the tumble subsides while the throttle is still high,
and in the 170.5 s slice the gyro peaks are back to 31/189/28 deg/s with the flight continuing
to the end of the log. I'll stay strictly with the observed sequence: the ordering doesn't
establish what triggered or ended the tumble, and the recovery settings aren't recorded in the
header (your report says Betaflight crash recovery was off) — the recovery is in the log;
which mechanism produced it isn't.

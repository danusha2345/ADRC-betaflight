# The b0-formula test flight (Air65, main filter stages disabled)

**Data**: one 190.0 s acro flight by @8ksal8 on the Air65 R (b9 firmware `919116fed`), posted
2026-08-18 in PR #15400 alongside his power-to-inertia b0 estimator. The tester attributes the
flown tune to that estimator ("I re-tuned ... New numbers"); the flown header reads
`wc 84/84/78`, `wo 140/140/80`, `b0 5849/3509/2340`, which sits about 1.6 % below the
comment's worked-example b0 (5945/3567/2378) — the estimator provenance is his attribution,
not something the log proves. The main Betaflight
gyro/dterm filter stages are disabled (activation keys printed by `analysis.py`), while the
ADRC observer's own input PT2 remains active at `adrc_gyro_lpf_hz = 185` — so the correct
reading is "main profile chain out of the loop", not "no filtering". One flight — every
log-derived number below is a single observation printed by `analysis.py`; the formula's own
numbers are quoted from the tester's comment and are not derived here. (The formula uses craft
constants — mass, wheelbase, per-motor continuous power — that the log does not record
directly; the log does carry a pack-level electrical proxy, `vbatLatest × amperageLatest`,
which is not the same quantity.)

## How the tune flew

Tracking error medians 10/10/11 deg/s (p90 28/29/31) over 190.0 s — a flyable tune that the
tester attributes to his estimator. The liftoff gate was open 98.5 % of frames. The 4153
per-motor rail samples are spread across the flight, not concentrated in the punch: 41.0 %
before 150 s, 29.2 % in 160–168.5 s, 29.8 % in the 168.5–171.5 s punch window.

On the reported "tail wagging", this log cannot separate it from commanded motion: in a 60-s
cruise window the yaw error spectrum maximum sits at **1.57 Hz**, the yaw setpoint has
substantial PSD at that frequency and the setpoint–error coherence there is 0.59 — the
low-frequency error content coincides with commanded yaw motion, and no wag attribution is
made. The 30–80 Hz band the filter campaigns tracked holds 1.37 deg/s in the same window. Two
header facts are printed next to that, without attribution: yaw runs `wo/wc = 80/78 ≈ 1.03`
while roll/pitch sit at 1.67 (not the lowest ratio in the archive — earlier corpora contain
yaw wo/wc down to 0.68), and the tester's own stated wish is to raise yaw wc/wo toward the
roll/pitch values.

## The end-of-pack punch event

Within the punch window the throttle first reaches 2000 at 169.22 s and a motor first touches
the rail at 169.17 s, on a sagging pack (an earlier full-throttle excursion near 167 s shows
gyro peaks ≤ 405 deg/s). In the 169.5 and 170.0 s slices the craft tumbles (gyro peaks
2828/2829/2000 deg/s, motors swinging rail to floor, vbat bottoming at 2.85 V); slice labels
are 0.5-s bins, not event timestamps. In the 170.5 s slice the peaks are back to
31/189/28 deg/s and the log continues to 190.0 s. Observed sequence only: punch, rail, a ~0.6 s tumble that
subsides while the throttle is still high, flight resumes — the ordering does not establish
what triggered or ended the tumble. The `crash_recovery` / `yaw_spin_recovery` settings are
not recorded in this header; the tester reports Betaflight crash recovery was off (his report,
not a log fact). The log shows the recovery itself, not which mechanism produced it.

## Caveats

- One flight, one craft, uncontrolled input and conditions; nothing here is a comparison.
- The tester's formula and its constant K (calibrated, per his post, on two tuned quads) are
  not evaluated here. A per-axis check becomes possible once jmsweng's fitter is refactored —
  fit this log and compare per-axis b0 with the formula's prediction. Turning that into a
  further K calibration point additionally needs the craft's mass, wheelbase and a stated
  power estimator; the comment does not say whether this Air65 is already one of the two
  calibration quads.
- The 1.57 Hz / 0.59-coherence reading is one window of one flight.

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 analysis.py
B0CALC_REPLY=DRAFT_reply.md python3 summaries.py --check
```

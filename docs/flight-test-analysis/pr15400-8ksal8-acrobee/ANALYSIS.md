# AcroBee75: the gyro filter chain in and out of the ADRC loop

**Data**: two flight logs by @8ksal8 on an AcroBee75 (b9 firmware `919116fed`, 8k gyro / 4k
PID, "580 lava 2s" pack), posted 2026-08-15 in PR #15400. Identical ADRC tune — `wc 100/100/50`,
`wo 120/120/80`, `b0 3923/2353/1569` — and identical profile except the filter set: one flight
with `gyro_lpf2` 500 Hz + 3 dynamic notches + RPM filter (plus dterm filters and
`yaw_lowpass` 100), one with all of it zeroed (`overview.py` prints the diff). Two separate
flights with uncontrolled inputs and conditions. Every AcroBee-derived number below is printed
by a script in this directory; the cross-campaign quotes (the Air65 bench range and the Pavo20
yaw line) are quoted from the named neighbouring campaigns' published analyses and are not
re-derived here.

**Why this pair matters.** On this firmware the profile **gyro** chain sits inside the ADRC
loop: `pid.c` feeds `gyro.gyroADCf` — the output of that chain — into the controller
(`pid.c:1360` → `applyAdrcControl`), and the ESO adds its own dedicated PT2 on top
(`adrc.c:599-604` at the b9 tag). The dterm filters shape a classic D that ADRC then
overwrites, and the yaw P-term lowpass is applied before the ADRC overwrite — neither enters
the nominal ADRC P/I/D output (the filtered gyro delta does still feed the crash-detection side
path, whose enablement these headers do not record). So the toggle is a **gyro-filter-chain
ON/OFF experiment**: it changes the chain's whole transfer function, magnitude and phase/group
delay together — the two are not separable from this pair.

## The airmode story, read off the mode mask

The tester: "on a fresh bat with filters on, Airmode would turn the quad into a flyaway. It
wasn't until around mid pack I could fly with Airmode on." The numeric mode mask records
(`attempts.py`): in the filters-ON flight the airmode box was activated **seven times** — the
three activations shorter than 5 s all started at 8.30 V or above (consistent with the reported
bail-outs; intent is the tester's account, not a log field), the four longer ones (12.4–60.3 s)
all started at 8.16 V or below. Across the first six chronological activations the yaw error
RMS decreases (73.5 → 20.5 deg/s) while start voltage generally decreases — the variables
co-vary, with pilot input and duration uncontrolled, and no voltage effect is identified; the
seventh contains the terminal event below and breaks the ordering (220.3) — the full sequence
is in the script output, nothing excluded silently. In the
filters-OFF flight the box went active at 10.1 s (8.67 V, fresh pack) and stayed active for
294.5 s — the whole usable pack, including the fresh-pack region where the ON flight's
activations were being cut short. Consistent with the report; not a controlled voltage
experiment (pack voltage, elapsed time and pilot caution all fall together), and an aborted
activation cannot show what an uninterrupted one would have done.

The ON flight ends, inside its last and longest activation, with a slice peaking above
2000 deg/s on all three axes, motors at the rail, pack sagged to its minimum — a terminal
high-rate event of unknown type (a tumble, crash, catch or hard landing are all consistent with
it); one such event in one flight supports no conclusion about the tune.

## The ~50 Hz yaw band on another craft, and its association with the filter chain

Matched windows (10 s, sliding inside airmode activations with a 5-s step — overlapping, not
independent; median vbat 7.6–8.2 V in both flights; every window's start, vbat, in-band peak
and 45–55 Hz prominence printed by `spectra.py`). Presence and dominance are kept separate:
**every ON window has its 30–80 Hz band maximum at 45–55 Hz** (and 22 of the 33 OFF windows do
too — the per-window RMS values in the script output are the comparison), so no
presence/absence claim is made. What the split below
separates is whether the ~50 Hz component dominates the whole 8–400 Hz spectrum:

| ON windows | n | yaw 30–80 Hz gyro | vs OFF median | command P+D | vs OFF |
|---|---|---|---|---|---|
| ~50 Hz globally dominant | 3 | 20.49 | **8.5×** | 81.18 | **10.6×** |
| higher-frequency dominant | 3 | 2.44 | 1.01× | 9.25 | 1.21× |

(The pooled ON medians, 2.2×/2.7×, fall between the subset medians — printed for
completeness, not a typical effect; the per-window values are in the script output.) The band
is the same ~50 Hz seen on the [Air65 bench corpus](../pr15400-8ksal8-propsoff2/) across yaw wc
80–120 (47.9–54.2 Hz) and in the [Pavo20 Pro II b0-sweep corpus](../pr15400-8ksal8-b0sweep/)
(a sustained 48.75 Hz yaw line) — with the AcroBee75 at yaw wc = 50 / wo = 80 that is three
crafts and three tunes with a yaw feature in the same band (the Pavo20's separate 6–10 Hz
propwash band is a different phenomenon and not part of this count). What this pair supports
is an **association** between the filter-chain state and the measured 30–80 Hz amplitude at a
matching intended profile; two non-randomised flights establish no causal edge, and the chain's
magnitude and phase effects are not separable here.

Whole-log numbers (`overview.py`): filters OFF runs 21/19/27 deg/s error medians against 4/3/7
with filters ON. The higher OFF medians co-occur with the visible micro-oscillation the tester
described — a central cruise window places its dominant error content in the high hundreds of
Hz near the motor band (yaw peak near the folded rotor fundamental; attribution loose) — but
the whole-log medians themselves are not frequency-decomposed here. The OFF flight's error maxima are 210/145/289 against the ON flight's 2197/2131/2152, but
the ON maxima all belong to the one terminal event, so that row compares a flight containing
such an event against one without, not two steady regimes. Motor-rail exposure, normalized:
21.62 samples/s (0.5366 % of motor samples) ON against 10.39 samples/s (0.2589 %) OFF. The log
cannot decide the long-term costs of the buzz (motor heating, wear); the tester reports cool
motors and about 6.5 minutes of flying.

## Caveats

- Two separate flights with uncontrolled inputs and conditions; matched windows control pack
  voltage and airmode state, nothing else. All ratios are observations.
- The matched windows overlap (5-s step) and come from one flight each — the window counts are
  not independent sample sizes and no formal inference is drawn from them.
- The ON flight's dynamic notches are constrained to 100–600 Hz centres — a notch cannot be
  centred on 50 Hz, though its off-centre magnitude/phase response still reaches there;
  attributing the 50 Hz effect to any single chain property is not possible from this pair.
- z3 telemetry: both logs rail the roll/pitch z3 debug channels for a few thousand frames
  (`overview.py`); yaw clips 430 frames (ON) / 0 (OFF) — the b9 int16 ceiling (ADRC-029), not
  the controller clamp.
- The liftoff gate was open 97.4–98.1 % of the two flights — normal flying, LESO fully in the
  loop, unlike the props-off bench corpus.

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 overview.py
python3 attempts.py
python3 spectra.py
python3 summaries.py --check
```

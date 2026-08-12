# Props-off corpus 2: the yaw line with its confounds removed one at a time

**Data**: 21 bench arms by @8ksal8 on the Air65 R (b9 firmware `919116fed`), posted 2026-08-11
in PR #15400, props off, throttle stick at zero throughout. Three runs, each requested to break
one confound left open by the [first props-off corpus](../pr15400-8ksal8-propsoff/) (same craft,
same firmware, 2026-08-10):

| run | cells | what changes against the first corpus |
|---|---|---|
| CLASSIC with yaw D | 4 + 4 arms (Airmode feature on / switch) | `yawPID` D 0 → 26; `simplified_pids_mode` 2 → 1 (needed to set it) |
| ADRC with dynamic idle | 4 + 4 arms (feature on / switch) | `dyn_idle_min_rpm` 0 → 30 and its consequence `motorOutput` low endpoint 158 → 48 |
| yaw-wc sweep | 5 arms | within the run, only yaw `wc` = 80/90/100/110/120 (`wo` 125, `b0` 5848 fixed) |

The configuration claims are checked programmatically over the union of all header keys
(`provenance.py`), not asserted from memory. One thing the profile diff does NOT control: the
runtime-measured RC-smoothing state (`rc_smoothing_active_cutoffs_ff_sp_thr`,
`rc_smoothing_rx_smoothed`) follows the ELRS link rate and differs between arms — the old
corpus ran at a measured 166 Hz link (62 Hz cutoffs), most new arms at 333 Hz (124 Hz cutoffs),
and within the sweep the wc80 arm ran at 333 Hz against 166 Hz for the other four. So every
old-vs-new pair also carries a link-rate difference, and the sweep's wc80 point is not
configuration-identical to its neighbours. Sticks were untouched in every arm, which bounds how
much a stick-path filter can matter, but the caveat stands and `provenance.py` prints the
per-arm values. Every number below is printed by a script in this directory; none is
hand-copied.

**Verdict in one paragraph.** The ADRC-vs-CLASSIC yaw gap survives both removed confounds:
giving CLASSIC a yaw D moves its 30–80 Hz band from 5.98 to 10.37 deg/s RMS (1.73×), turning
dynamic idle on under ADRC moves ADRC from 42.68 to 60.26 (1.41×, pack state differs, not
attributable) — the clean feature-on ratio is **5.8×** (was 7.1×). The line's frequency does not
move with yaw wc (47.9–52.0 Hz across a 50 % wc sweep) or with the rotor's median rate
(per-motor medians 60 to 593 Hz across the ADRC cells), but its **amplitude tracks wc
monotonically, 4.8× from wc 80 to wc 120** (3.7× within the wc90–120 subset — same 62 Hz
cutoffs, measured link 166–167 Hz). The whole corpus was flown with the liftoff gate shut and the observer's
disturbance estimate pinned at zero — so whatever oscillates does it with the **z3 disturbance
channel out of the loop**, through the P/D pair (kp = wc², kd = 2wc) acting on the ESO's z1/z2
state estimates. What the bench cannot do is name the loop element that sets the ~50 Hz: the
rotor rates rise with wc too, and a driven motor is itself a vibration source with a path back
into the gyro (§2–§3, with the follow-ups that would separate this).

## 1. A decoder default hid a phase structure in both corpora

The blackbox "flightModeFlags" field carries the low 32 bits of `rcModeActivationMask`, and
`blackbox_decode`'s default flag rendering silently discards bit 24 — `BOXAIRMODE` (this was
first established in [`pr15400-8ksal8-b0sweep2/`](../pr15400-8ksal8-b0sweep2/)). The same
decoder emits the numeric mask with `--unit-flags raw`, which is what `modemask.py` uses (an
earlier draft used a hand-written parser instead; it mishandled GPS frames and shifted phase
boundaries — everything here now comes from the pinned decoder). Recovered: **in every "Airmode
switch" arm of BOTH corpora the BOXAIRMODE box became active mid-arm** — arm, ~3–8 s off, a few
seconds active, off again, disarm. The mask proves the box state, not the intent behind it (a
linked mode or aux programming would look identical). The five sweep arms and the feature-on
cells are single-regime; every switch cell is a two-regime mixture.

That matters because at zero throttle the mixer scales axis authority by 0.5 with airmode off
and 1.0 with it on (`applyMixerAdjustment`), and the published whole-arm medians of the first
corpus mixed those regimes. Split by phase (`spectra.py`), yaw 30–80 Hz RMS, medians over
phases ≥ 1.5 s:

| cell | airmode-off phases | airmode-ON phases |
|---|---|---|
| ADRC dynIdle=0 (first corpus, "feature off" cell) | **5.20** (n=8) | **45.53** (n=4) |
| CLASSIC yawD=0 (first corpus) | 3.93 (n=8) | 5.00 (n=4) |
| CLASSIC yawD=26 (this corpus) | 4.23 (n=7) | 11.40 (n=4) |
| ADRC dynIdle=30 (this corpus) | 16.70 (n=8) | 59.77 (n=4) |

So the first corpus's "ADRC, feature off = 28.66" was mostly its airmode-on phase: with airmode
genuinely off and static idle, ADRC on this tune sits at 5.20 — near the CLASSIC floor. The
oscillation needs authority. The group ratios published earlier survive (both sides of each
ratio were mixed the same way), but the regime labels did not, and the first corpus's
ANALYSIS.md now carries a correction note pointing here.

## 2. The paired comparisons

Whole-arm group medians, yaw 30–80 Hz RMS on gyroUnfilt, same estimator as the first corpus
(Welch, nperseg 2048, uniform-grid resample; `spectra.py`):

| group | yaw 30–80 (deg/s RMS) | yaw peak (Hz) |
|---|---|---|
| ADRC dynIdle=0, Airmode on (first corpus) | 42.68 | 53–54 |
| ADRC dynIdle=0, Airmode off (first corpus) | 28.66 | 53 |
| CLASSIC yawD=0, Airmode on (first corpus) | 5.98 | 56 |
| CLASSIC yawD=0, Airmode off (first corpus) | 4.51 | 55 |
| CLASSIC yawD=26, Airmode on | 10.37 | 72–74 |
| CLASSIC yawD=26, Airmode off | 9.57 | 69–71 |
| ADRC dynIdle=30, Airmode on | 60.26 | 53–54 |
| ADRC dynIdle=30, Airmode off | 46.51 | 53–54 |

- **Yaw D was not the explanation.** It roughly doubles the CLASSIC band content (5.98 → 10.37
  feature-on), and the new CLASSIC peak sits at 69–74 Hz — on top of the rotor medians
  (58–88 Hz), with 12.7–22.1 % of frames having a time-varying 1× within 2 Hz of the peak. The
  CLASSIC 30–80 Hz content is consistent with rotor vibration through the D path (proximity
  alone cannot exclude a control-loop contribution) — either way it is a conservative (high)
  baseline. The ADRC gap above it: **5.8×** feature-on.
- **Dynamic idle does not remove the ADRC line.** Peak pinned at 53–54 Hz as before; the
  amplitude moved up 1.41× feature-on, but the dyn-idle cells were flown on a lower pack
  (vbat min 3.70–3.79 V vs 3.83–4.16 V elsewhere; `provenance.py`), so the direction is not
  attributable. What is attributable: removal did not happen.
- **The rotor's 1× does not carry the group result — but "not a rotor order" outright is not
  available.** The line stays at 47.9–54.2 Hz while per-motor rotor medians range from 60 to
  593 Hz, and the nearest aliased median 1× sits 9.4–314.7 Hz from the line per arm; the
  time-varying 1× brushes the line mostly in the wc80/wc90 sweep arms (16.1 / 20.7 % of frames
  within 2 Hz), ≤ 3.7 % elsewhere. Higher orders are a different story: per-order worst dwell
  reaches 12.2 % (12×), 9.8 % (4×), 9.5 % (3×), 7.6 % (6× — the electrical fundamental of these
  12-pole motors) in individual arms (`spectra.py`), so a higher-order vibration contribution
  is not broadly excluded. And since the rotor rates rise with wc, an
  oscillation-driven-motor-vibration path back into the gyro is a competing explanation the
  bench cannot separate from the control loop itself.

## 3. The wc sweep

All five arms single-regime (airmode fully off), dyn idle 30, only yaw wc moves in the profile
(`sweep.py`; the wc80 arm's measured link rate differs, see the intro):

| yaw wc | yaw 30–80 (deg/s RMS) | peak (Hz) | vbat min | rotor median (Hz) | measured link |
|---|---|---|---|---|---|
| 80 | 8.07 | 48.7 | 4.22 V | 60–68 | 333 Hz / 124 Hz cutoffs |
| 90 | 10.40 | 52.0 | 4.18 V | 61–70 | 167 Hz / 62 Hz |
| 100 | 22.01 | 49.8 | 4.15 V | 119–129 | 166 Hz / 62 Hz |
| 110 | 30.03 | 47.9 | 4.10 V | 181–198 | 166 Hz / 62 Hz |
| 120 | 38.79 | 49.6 | 4.00 V | 256–275 | 166 Hz / 62 Hz |

Amplitude strictly monotonic in wc, **4.8×** over the sweep and 3.7× within the
wc90–120 subset (same profile except wc; same 62 Hz cutoffs, measured link 166–167 Hz);
frequency 47.9–52.0 Hz and not monotonic; the
per-second 30–80 Hz RMS (same band as the headline number) is flat within each arm, so the
short spans (4.4–5.4 s) do not censor a still-growing oscillation. Consistency cross-check: the
dyn-idle cell's airmode-off phases ran this same regime at yaw wc 96, and their pooled median
16.70 lands between the wc 90 and wc 100 sweep points.

Confounds to state, not argue away: pack state declines monotonically with wc (4.22 → 4.00 V
min — the arms were flown back-to-back in ascending wc order); the rotor medians rise with wc
(60–68 up to 256–275 Hz), so motor-vibration intensity rises with wc alongside loop gain; and
the wc80 arm ran at a different link rate. The measurement — monotonic 30–80 Hz amplitude in
wc at a pinned frequency — is solid; **which mechanism carries it is not established by this
sweep alone.** No bench configuration separates the two paths, because no configuration pins
the rotor speed while the loop drives the motors (the first corpus's dyn-idle-OFF arms still
ran their rotors at 146–611 Hz). What would move the attribution: a yaw **wo** sweep at fixed
wc (the observer dynamics were fixed at wo = 125 here, so their role in the ~50 Hz is
untested), and an **order-tracking analysis** — integrate motor phase from eRPM(t) and measure
how much of the line is coherent with the motors versus not.

## 4. What state the controller was in

In all 13 ADRC arms (`arms.py`): the liftoff gate never opened (`debug[7]` negative throughout),
the logged z3 is exactly zero on all three axes for the whole arm (bounding runtime |z3| ≤ 8, since
the channel stores `lrintf(z3/16)`), and `axisI` — which ADRC reports as −z3/b0 — is identically
zero. The z3 growth inhibit and the closed gate hold the disturbance channel out of the loop for
the entire corpus. What remains of the ADRC law is `u = (kp·(setpoint − z1) − kd·z2)/b0`
(`adrc.c`) — the controller pair over the ESO's z1/z2 state estimates, which continue to track
the measured rate through the wo-tuned gains even with the gate shut.

The line is present in the command path: the yaw P+D spectrum peaks at the same frequency as
the gyro line in every ADRC arm (`spectra.py`, match within 1 Hz; with z3 at zero these two
terms are the whole logged ADRC P/I/D contribution — yaw `axisF` is negligible here, a handful
of frames at −1). Two signals inside one closed loop are expected to share a limit-cycle
frequency, so this establishes presence, **not which element of the loop sets the frequency**.
A fine detail consistent with the authority mechanism: the off-phase line sits at 48–50 Hz and
moves to 51–54 Hz in the full-authority phases.

**What this does NOT establish**: whether the same behaviour exists with props on (props add
aerodynamic damping and change the plant entirely), in flight, or which loop element sets the
~50 Hz. It is a bench characterisation of the zero-throttle regime the ADRC-026 gate work
already made important; its practical upshot for testers is that a zero-throttle bench buzz on
ADRC yaw scales directly with yaw wc, and that a wo sweep plus an order-tracking pass over the
existing logs are the cheapest ways to finish the attribution.

## 5. Honest limits

- All between-group comparisons carry pack-state differences (`provenance.py` prints the
  per-group vbat ranges); only the within-sweep trend and the phase splits are same-pack.
- Both old-vs-new pairs also carry the measured link-rate change (166 → 333 Hz) described in
  the intro; `provenance.py` prints the per-arm values, including the one inhomogeneous arm
  inside the new ADRC switch cell.
- The saved stream is decimated (~800 Hz of a 3.2 kHz loop); everything spectral interpolates
  onto a uniform grid, and per-motor order checks use the arm-average frame rate. Treat small
  percentages in the order-dwell columns as indicative, not exact.
- The phase split drops phases shorter than 1.5 s (Welch needs data); n per cell is printed.
- `provenance.py` asserts `rcCommand[3]` max = 1000 in every log — these are all stick-down
  arms; no motor sample reaches the upper endpoint anywhere in the corpus.
- CLASSIC arms ran `debug_mode 19`, so they have no ADRC debug channels — the controller
  identity is verified from `pid_type`, the field layout (axisD[2] present exactly when yaw
  D ≠ 0), and the ADRC channels where present.
- `summaries.py --check` is a drift guard, not a proof: it verifies phrase presence and that
  every number in the prose occurs in script output, but it cannot verify that a number is
  attributed to the right log or claim (its docstring lists the known blind spots).

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 modemask.py      # BOXAIRMODE recovery via --unit-flags raw, both corpora
python3 provenance.py    # paired header diffs, rc-smoothing state, battery, controller identity
python3 arms.py          # per-arm basics; gate/z3/axisI/axisF state
python3 spectra.py       # group tables, phase split, paired ratios, rotor-order checks
python3 sweep.py         # the wc sweep and its cross-check
python3 summaries.py --check   # regression guard over this file's numbers
```

The first props-off corpus must sit at `../pr15400-8ksal8-propsoff/` (it does, in this repo).

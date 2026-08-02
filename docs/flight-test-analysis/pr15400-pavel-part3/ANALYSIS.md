# Pavel_M., Air65 II and Meteor75 Pro, 2026-08-01 (part 3) — a two-craft wc sweep at fixed b0, and what "borderline unflyable" looks like in numbers

Source: two archives posted to the `FPV ADRC Development` Discord,
`#test-flights-and-logs`, threads "Air 65 Racing 0702 30000KV part 3" and
"Meteor 75 Pro 1102 22000KV part 3", both 2026-08-01 (15:35 / 15:40 MSK).
Pilot's design: best-flying b0 from part 2 per craft, wo held at 100,
`wc ∈ {20, 40, 60}` on all three axes, two ~30 s flights per setting
(three at Meteor wc 60), very light wind. Pilot's warning kept in mind
throughout: he could not remember which flights were recorded, "so there
might be a crash or two in the logs".

| archive | SHA-256 |
|---|---|
| `AIR65_tune_varied_wc_100_6400.BBL.zip` | `574a8bcd4605c881f4a814c379f4aa26bd8d59ac2bff8004ebba1f857f2830ba` |
| `METEOR_tune_varied_wc_100_3200.BBL.zip` | `6def679a8939c70c1b36ab0e033928742036c87522514b63897e8fb6b2fd2488` |

Both are Betaflight b5 (`543f1a5ff`, STM32G47X), `pid_type = ADRC`,
`debug_mode = ADRC`, `adrc_b0_law = 1` (SQRT), ~2 kHz logging,
`motorOutput 48-1847`, `adrc_gyro_lpf_hz = 150`. Headers match the stated
plan exactly:

| craft | sessions | wc R/P/Y | wo | b0 (all axes) | anchor | vbatref per session (1S) |
|---|---|---|---|---|---:|---|
| Air65 II (BMI270) | 6 | 20, 40, 60 ×2 each | 100 | 6400 | 35 | 4.01 / 3.95 / 4.09 / 3.91 / 4.16 / 3.97 |
| Meteor75 Pro (ICM42622P) | 7 | 20 ×2, 40 ×2, 60 ×3 | 100 | 3200 | 40 | 4.02 / 3.89 / 4.05 / 3.91 / 3.78 / 3.69 / 3.84 |

Unlike part 2 the yaw axis is configured identically to roll/pitch on both
crafts (part 2 ran the Meteor at `wc_yaw = 100`; here it is the swept value).

Reproduce:

```bash
unzip -n AIR65_tune_varied_wc_100_6400.BBL.zip
unzip -n METEOR_tune_varied_wc_100_3200.BBL.zip
blackbox_decode --unit-acceleration g --unit-frame-time us --save-headers \
  AIR65_tune_varied_wc_100_6400.BBL
blackbox_decode --unit-acceleration g --unit-frame-time us --save-headers \
  METEOR_tune_varied_wc_100_3200.BBL
python3 ../pr15400-8ksal8-yawb0/analyze_round.py *.0[0-9].csv
python3 excursions.py *.0[0-9].csv   # §2 counts + §3 onset context
```

All the usual caveats apply: free flights, uncontrolled manoeuvre content,
pack state varying between sessions (the Meteor wc 60 sessions sit on the
saggiest packs of the set, 3.69–3.84 V). These are trends and event records,
not controlled A/Bs.

## 1. The wc sweep dominates the rankable measurements

Tracking error as % of the command sd (σ-ratio methodology as in the part-2
write-up: 15 Hz-lowpassed commanded segments, |setpoint| > 50 dps; "gain" is
σ_gyro/σ_cmd on those segments, a std-dev ratio, not a proper closed-loop
gain). Pitch windows in several logs are short (1–4 s) — treat those cells as
weak. Saturation = fraction of samples with any motor at the upper rail.

**Air65 (b0 6400, wo 100):**

| log | wc | dur | sat | roll err %/gain | pitch err %/gain | yaw err %/gain |
|---|---:|---:|---:|---|---|---|
| .01 | 20 | 25.9 s | 0.65 % | 1298 % / 11.69 | 193 % / 1.84 | 194 % / 2.40 |
| .02 | 20 | 32.0 s | 0 % | 286 % / 2.64 | n/a | 103 % / 1.63 |
| .03 | 40 | 30.7 s | 0.57 % | 46 % / 1.22 | 31 % / 1.10 | 17 % / 1.03 |
| .04 | 40 | 36.1 s | 0 % | 35 % / 1.17 | 102 % / 1.47 (n=1.9 s) | 29 % / 1.09 |
| .05 | 60 | 30.1 s | 0 % | 14 % / 1.05 | 12 % / 1.00 | 14 % / 1.05 |
| .06 | 60 | 27.6 s | 0 % | 19 % / 1.10 | 37 % / 1.25 (n=3.7 s) | 19 % / 1.08 |

**Meteor75 (b0 3200, wo 100):**

| log | wc | dur | sat | roll err %/gain | pitch err %/gain | yaw err %/gain |
|---|---:|---:|---:|---|---|---|
| .01 | 20 | 29.3 s | 10.1 % | 275 % / 3.22 | 483 % / 4.01 | 115 % / 1.54 |
| .02 | 20 | 7.7 s | 25.0 % | crash record — see §4 | | |
| .03 | 40 | 26.9 s | 12.9 % | 38 % / 1.17 | 130 % / 1.35 | 36 % / 1.17 |
| .04 | 40 | 31.9 s | 6.2 % | 50 % / 1.25 | 32 % / 1.12 | 36 % / 1.15 |
| .05 | 60 | 22.2 s | 19.6 % | crash episode at ~21 s — see §4 | | |
| .06 | 60 | 35.2 s | 0 % | 29 % / 1.12 | 28 % / 0.91 | 14 % / 1.03 |
| .07 | 60 | 33.6 s | 2.3 % | 24 % / 1.14 | 247 % / 2.09 (n=2.2 s) | 14 % / 1.04 |

The pilot's ranking — wc 20 borderline unflyable, wc 40 noticeably better,
wc 60 "more or less okay" — is reproduced by the roll and yaw columns and by
§2's event counts; the short-window pitch cells are too noisy to rank (.04's
102 % on 1.9 s, .07's 247 % on 2.2 s), and the extreme 1298 % roll cell is a
departure-dominated window with a small command sd, not a standalone
measurement (§4). On the clean logs the direct P-path coefficient `wc²/b0`
moves 0.06 → 0.25 → 0.56 (Air65) and 0.13 → 0.50 → 1.13 (Meteor) across the
sweep — a 9× swing in the P-path stiffness per unit error, which is the
plain reading of why the rankable columns follow wc here.

One cross-craft echo of part 2, stated carefully: the Meteor at wc 40
(`wc²/b0` = 0.50) and the Air65 at wc 60 (0.56) sit at almost the same
nominal coefficient, yet the Air65 tracks several-fold tighter — consistent
with the part-2 finding that the 0702/30000KV craft has a much higher real
control gain than its configured-b0 twin, and a reminder that the configured
b0 numbers are not comparable across crafts. (`wc²/b0` is the direct P-path
coefficient only — the D path scales as `2wc/b0` and the ESO and scheduled
b0 also shape the closed loop — so it is a reading aid here, not a stiffness
measurement.)

## 2. Uncommanded high-rate events, counted

Definition (in `excursions.py`): a per-axis *interval* is |gyro| > 200 dps
sustained ≥ 100 ms on an axis while |setpoint| < 30 dps on that same axis
(first and last 1.0 s of each log excluded); intervals overlapping in time
across axes are merged into one *event*. The merge only joins overlaps — an
oscillatory departure with short sub-threshold gaps can still appear as more
than one event. The reported angle is the integrated body-axis angle
|∫gyro dt| on the event's dominant qualifying axis (net body-frame rotation,
not an attitude reconstruction). The detector cannot distinguish a tune
departure from a crash impact, so §4's crash logs are kept separate.

| craft | wc 20 | wc 40 | wc 60 |
|---|---|---|---|
| Air65 | **2 + 10 events** (peaks to 592 dps; four events integrate ≥ 90°: 92–118°) | 0 | 0 |
| Meteor75 | **4 events** in the clean log (peaks to 735 dps; two ≥ 90°: 144° and 242°) + 2 in the `.02` crash record | **1 + 2 events** (peaks 1071 / 1073 dps; angles 133° / 165°) | 0 detector events outside the excluded `.05` crash tail (§4); both clean logs zero |

The pilot's report is quantitatively supported: the largest clean-log events
integrate to 92–242° of body-axis rotation — his "random unexpected
rotations of 90 degrees or more" — they are endemic at wc 20 on both crafts,
persist at wc 40 on the Meteor with peaks above 1000 dps, and are absent
from every wc 60 log outside the excluded `.05` crash tail.

## 3. Context of the biggest departures (observations, mechanism open)

Onset-anchored context, emitted per event by `excursions.py` (saturation =
any motor at the true upper rail of `motorOutput`, the same definition as
§1's saturation column):

- **Meteor wc 40 — the two biggest departures begin after ≥ 100 ms of
  continuous upper-rail saturation.** `.03 @19.073 s` (133°, 1071 dps):
  100 % saturation duty through the preceding 100 *and* 300 ms and 100 %
  during; |I| before onset 448/338/342 against bounds 500/500/400, railing
  at the bound during. `.04 @21.980 s` (165°, 1073 dps): 100 % saturation
  over the preceding 100 ms (48.3 % over 300 ms), 100 % during; |I| before
  onset 338/262/270, at the bound during. (A separate small precursor at
  `.04 @21.795 s`, 31°, has no pre-onset saturation and stays below the
  bound.) The safe statement: both largest wc-40 departures begin after
  ≥ 100 ms of continuous upper-rail saturation — at least one motor is at
  the configured high rail in every sample — and remain continuously
  saturated during the detected event, with the I-path railing during the
  event rather than winding up ahead of it. Whether saturation causes the
  departure or a developing departure drives the saturation is still not
  resolvable from two events.
- **wc 20 events: 15 of the 16 clean-log events have no pre-onset
  saturation.** All ten Air65 events show 0 % saturation before *and during*
  — pure unsaturated departures — with |I| well inside the bound; the
  Meteor's big events (242°, 144°) also start unsaturated (saturation
  appears only during, 43–52 %, as the recovery uses full authority). The
  single exception, `.01 @3.979 s` (46°), chains 0.6 s behind the 242°
  departure and its pre-onset saturation belongs to that recovery. The
  b0-schedule multiplier is locally steady within each pre-onset window
  (1.18–1.53 applied, differing *between* events but not stepping within
  one). The one common factor is the soft direct path (`wc²/b0` =
  0.06–0.13); the specific trigger of each departure is unidentified. An
  earlier revision framed these as a "schedule-transient family" — that
  overread the data (the 1.00 → 1.48 multiplier range was a min/max across
  different windows, not a transient within one) and is withdrawn.

## 4. Crash-log inventory (so nobody treats these seconds as tune data)

- `METEOR….02` — 7.7 s record, 25 % saturation, gyro RMS ~380 dps on all
  axes: a crash record from arm to impact (wc 20). Its 2 events are listed
  separately in §2 and excluded from tune claims.
- `METEOR….05` — contains a crash at ~21.2–21.6 s (yaw peak at the 2000 dps
  sensor clip, 19.6 % saturation overall), consistent with the pilot's "one
  crash at wc = 60 … clipped some shrubs". It falls inside the counter's
  excluded final second, hence the 0 in §2; the first ~20 s of the log are
  ordinary flight.
- `AIR65….01` — no crash signature, but its two events plus 0.65 %
  saturation dominate the tracking row (the 1298 % roll cell is what a
  departure does to a σ-ratio over a short window).

## 5. The "wc should be 20–30 % of wo" rule did not bind here

Textbook LADRC guidance (wo ≈ 3–5 × wc) would cap wc at 20–33 at wo = 100.
In these flights that cap did not bind: of the tested {20, 40, 60}, both
whoops fly far best at wc 60 / wo 100 (ratio 0.6) — and as an existence
point, the Pavo20 in the PR thread flies at wc 125–130 / wo 160 (≈ 0.8) with
`wc_yaw = 300 > wo`. This is evidence that the ratio rule is not a hard
constraint in this implementation, not a universal refutation of it, and it
does not establish that wc 80 is safe. The practical limits actually
observed in this corpus are actuator authority (saturation duty) and
gyro-path noise at high wo. For the pilot's planned wc 80 / wo 100 point,
the numbers to watch are saturation duty (already 6–20 % in the aggressive
Meteor logs at b0 3200 — where §3's wc-40 departures live) and the
20–80 Hz band, which so far stays flat (0.7–2 dps in every clean log of this
set — chatter is not the active constraint at these settings).

## 6. Day-to-day reproducibility caveat

The Meteor's wc 60 / b0 3200 / wo 100 configuration here is nominally the
same roll/pitch tune as its part-2 "3200" sessions, but tracks 24–29 % (roll)
against ~10 % in part 2. Different day, different packs (3.69–3.84 V here —
the saggiest of the set), different manoeuvre content; whichever of those it
is, a 2–3× spread on the same nominal tune across days is itself a finding:
single-session σ-ratio comparisons between tunes are only meaningful for
large effects (like §1's), and the ADRC-021 doublet protocol remains the
instrument for anything finer. (The pilot has said he will look into the
ADRC-021 protocol after a 1–2 week break.)

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| wc dominates whoop flyability at fixed b0/wo in this set | POSITIVE | §1: roll/yaw tracking and §2 event counts monotone with wc on both crafts (short-window pitch cells too noisy to rank), 9× `wc²/b0` swing | high |
| wc 20 produces uncommanded high-rate events on both crafts | POSITIVE | §2: 12 (Air65) and 4 (Meteor) clean-log merged events, peaks to 735 dps | high |
| the biggest clean-log events match the pilot's "90°+ rotations" | POSITIVE | §2: integrated body-axis angles 92–242° | medium-high |
| events persist at wc 40 on the Meteor | POSITIVE | §2: 3 events, peaks > 1000 dps | high |
| the two biggest wc-40 departures begin after ≥ 100 ms of continuous upper-rail saturation | POSITIVE (observation) | §3: ≥ 1 motor at the high rail in every sample of the preceding 100 ms at both onsets and throughout the events, \|I\| railing during, below bound before | high |
| saturation *causes* those departures | OPEN | §3: direction not resolvable from two events | — |
| wc-20 events start unsaturated | POSITIVE (15 of 16) | §3: 0 % pre-onset saturation in all clean-log events except one 46° follow-on chained to the 242° departure's recovery | high |
| wc-20 events are b0-schedule transients | WITHDRAWN | §3: debug[7] locally steady within each pre-onset window | — |
| "wc = 20–30 % of wo" binds in this implementation | NEGATIVE (in these data) | §5: best-of-set at ratio 0.6 on both whoops; Pavo20 at ≈ 0.8 (yaw 1.9) as existence point; not a universal refutation, wc 80 untested | medium-high |
| Meteor part-2 vs part-3 same-tune difference is a real tune change | NEGATIVE (confounded) | §6: day, pack, content all differ | high |
| chatter (20–80 Hz) constrains the wc range flown here | NEGATIVE | §5: 0.7–2 dps in every clean log | medium-high |

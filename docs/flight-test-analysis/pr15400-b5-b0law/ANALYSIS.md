# 2026-07-19 b5 A/B flights: adrc_b0_law (ADRC-021/022/024/025)

**Verdict up front**:

1. **ADRC-021 (accuracy)**: the b5 A/B corpus re-confirms the July-15 result
   with law-controlled flights — pooled law scoring (559 windows, one craft):
   **sqrt 0.157 < linear 0.173 < fixed 0.186 < quadratic 0.253** (RMS
   log-error, per-law best-fit hover b0). Precisely stated, this scores each
   *candidate schedule shape* against the pooled plant-gain estimates from
   all arms (the plant is law-independent), **not** per-arm in-flight
   accuracy — the FIXED row is fit on the same 559 windows even though the
   FIXED arm contributed only 2 of them. The ordering is robust: SQRT wins
   all 12 leave-one-flight-out refits and ~98 % of 2000 flight-level
   bootstrap resamples. Measured plant gain grows
   ~2290 → ~2970 from hover to 40–60 % collective (×1.3), nowhere near the
   quadratic's ×2.3–3. The ESO residual agrees: z3~u slope is most negative
   and steepest-vs-collective under QUADRATIC, flattest under SQRT.
2. **ADRC-024 (the surprise, and the reason not to just ship sqrt)**: the
   26 Hz hover ring is **law-dependent in the opposite direction** —
   ring incidence in hover-band windows is **29–41 % under SQRT** (all three
   flights, 25–26 Hz, worst 17 deg/s), **2–7 % under LINEAR**, **0–2 % under
   QUADRATIC** (this script's stricter window gate; the committed
   `ring_sensitivity.py` criterion gives 41–58 / 8–15 / 3–12 % with the same
   ranking — see Method). Ring windows sit at 24–26 % collective, right
   above hover, where quadratic already applies ×1.2–1.4 b0 — a ~17–29 %
   cut of the direct-path gain vs scale 1 (~12–25 % vs sqrt's ≈×1.05;
   b0 also enters the ESO feedback, so the full-loop change is approximate).
   That modest gain difference flips the mode from quiet to ringing. The
   **measured** fact is: the b0 law controls the 26 Hz ring incidence on
   this craft, and the accuracy-optimal law exposes what the quadratic's
   over-scaling was suppressing. The **leading interpretation** is a
   marginally-damped ~26 Hz mode short on loop margin at hover-band gain —
   a hypothesis, not yet established; the decisive test is a SQRT flight at
   wc ≈ 40–50 (see below).
3. **ADRC-025 (rebound)**: calm punch→chop rebounds — SQRT median 51 / max
   114 (n=10), LINEAR 58 / 111 (n=17), QUADRATIC 71 / 145 (n=11) deg/s.
   Direction consistent with less high-collective over-scaling ⇒ smaller
   stored observer error at the chop; not conclusive at these n.
4. **FIXED arm is lost**: its single flight is 12 s — brief hop, long
   zero-throttle low glide over tall grass, grass strike (1915 deg/s tumble,
   both z3 railed at the debug clip; DVR frames confirm grass contact).
   2 usable identification windows, 0 hover-band ring windows. **Not a
   control failure** — but the null-hypothesis control arm still has no data.

**Practical read**: on current loop code, LINEAR is the best compromise
(near-best accuracy, lowest ring short of quadratic, mid rebound); SQRT
becomes the right law *if* giving the 26 Hz mode margin works — wc/wo
shaping is the testable path, the fork's `adrc-dterm-lpf` z2-LPF is a
separate untested candidate (its effect on stability margin is itself
unverified). QUADRATIC buys its quiet hover by over-scaling b0 ~×2 at
35–45 % collective, which the identification and the rebound numbers both
bill.

## Data & provenance

12 flights by @bvandevliet, 2026-07-19, same SPEEDYBEEF7MINIV2 as the
July-15 corpus (`NLDj4wldvf6akwve`, hover 22 %). Build `543f1a5ffc` =
release tag `adrc-pr15400-b5` (PR head `eda3bb16eb` + fork-only
`adrc_b0_law` selector). All four profiles are defaults 60/100/2000 with
`adrc_hover_throttle = 22`, `adrc_liftoff_throttle = 30`; **the only
difference between profiles is `adrc_b0_law`** (see the committed
`diff all`): p1 = SQRT, p2 = FIXED, p3 = QUADRATIC, p4 = LINEAR (header
`adrc_b0_law` 1/3/0/2 — cross-checked per log).

Flights per arm: SQRT ×3, QUADRATIC ×4, LINEAR ×4, FIXED ×1 (the grass-strike
flight), spread over 3 packs in mixed order. Originals (`.bbl`, `diff all`)
are preserved here; DVR/OSD archived offline (`blackbox/b5`, 2.6 GB).

The active law is verified *from telemetry*, not just headers: debug[7]
carries the applied b0 scale ×100, and its median per collective bin matches
the arm's law prediction in every log (sanity table in `b5_ab.py` output).

## Method

`b5_ab.py`, run from this directory after `blackbox_decode --debug
--unit-frame-time us *.bbl`. Identification and z3-residual estimators are
the committed `pr15400-doublets` methods (`identify_b0.py` is imported, its
CSV loader patched only to tolerate the truncated tail rows these logs
carry); punch criteria match `punches_20260715.py`. **The ring windowing
deviates from `ring_sensitivity.py` in two ways**: the motor gate is
stricter (all four motors above floor, `min > 50`, vs mean `> 68` — drops
windows where any motor rides the floor) and the axis test is
first-axis-meeting-criteria vs loudest-axis. Under the original criterion
the incidences are SQRT 58/41/57 %, LINEAR 13/8/8/15 %, QUADRATIC
3/5/5/12 % — same ranking, higher absolutes; the FIXED flight then yields
5 hover windows of which 4 ring (consistent in sign with the gain story,
but n=5 from the aborted flight — not evidence). Caveats carried over: absolute b0 is analysis-band-dependent;
z3~u is a model-residual cross-check, not an independent estimate; maneuvers
were pilot-flown, not scripted, so per-arm exposure differs (ring incidence
is normalized per hover-band window to compensate).

## Key numbers

Pooled identification bins (all arms, mixer-collective %):
10–16 %: n=16 med 2036 · 18–27 %: n=355 med 2288 · 30–40 %: n=71 med 2727 ·
40–60 %: n=15 med 2969. Hover-band b0 again supports `b0 = 2000` as a
conservative default (ADRC-022) with best-fit hover b0 2030–2320 depending
on law frame.

z3~u slope medians (roll+pitch pooled), hover bin 18–27 % / high bin
40–60 %: SQRT −403 / −736 · LINEAR −479 / −931 · QUADRATIC −691 / −1460.

Ring incidence per flight (hover-band windows, 18–32 Hz tone > 5 deg/s,
tone fraction > 0.5): SQRT 36 / 29 / 41 % · LINEAR 6 / 2 / 2 / 7 % ·
QUADRATIC 1 / 0 / 2 / 0 % · FIXED — (0 usable windows).

## What would settle the remaining questions

- **FIXED needs flights** (ADRC-021's null control): 1–2 hover + doublet
  flights on p2. Prediction if the gain-margin story is right: ring ≥ SQRT's.
- A SQRT (or FIXED) flight with wc ≈ 40–50 to test that margin, not the law,
  controls the 26 Hz mode (ties into ADRC-024 and jmsweng's "wc ≈ 40
  quiets it").
- Second craft (jmsweng): even QUADRATIC vs SQRT hover pairs would show
  whether the ring inversion is craft-specific.

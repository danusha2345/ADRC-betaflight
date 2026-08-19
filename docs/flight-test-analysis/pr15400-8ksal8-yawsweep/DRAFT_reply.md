@8ksal8 This set is exactly the missing piece — the filter campaigns never varied
`wo`, and you just flew it. All eleven logs analysed:
[`pr15400-8ksal8-yawsweep/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-yawsweep)

**The ~50 Hz yaw band tracked wo more closely than wc in this set.** With `wo` pinned at 80
the band peak stays at 47.0–53.5 Hz for every `wc` in 50–80; when `wo` comes down with `wc`
the peak comes down with it (wo=50 → 34.43 Hz, wo=60 → 40.73 Hz, wo=70 → 50.95 Hz,
wo=80 → 55.09 Hz). The cleanest contrast is your wc=50 pair: wo 80 → 47.01 Hz vs
wo 50 → 34.43 Hz — the one pair where `wc` and the link rate both hold still; in the wc=wo
sweep the two parameters move together. Observed association, one flight per cell, no
mechanism established — but the frequency tracks the observer bandwidth more closely than the
controller bandwidth here. One confound to name: your rx link rate differed between flights
(~166 Hz in some cells, ~332–339 Hz in others), so for future sweeps pinning the link rate
would remove that variable from every pair, not just the same-rate ones.

**Your 80/80 tune got flown twice** (once in each sweep) — the only repeated cell in this
set: 53.50 vs 55.09 Hz, prominence 9.6 vs 6.3, band RMS 1.56 vs 1.49 deg/s. One repeat is one
realised between-flight difference, not a variance estimate — but it's the only repeat in
this 11-log set, and worth doing again on purpose.

**The lowered yaw b0 cells are the sharpest result.** At `wc = wo = 50` the redistribution
(2340 → 878) flies but the band grows: RMS 1.06 → 2.25 deg/s, prominence 2.2 → 24.1 (that
pair is same-link-rate, so it's the cleaner of the two). At `wc = wo = 60` the log shows a
sustained 46.24 Hz yaw component (band RMS 55.53 deg/s, yaw median 48 deg/s vs 18 stock) and
the log ends after 12.8 s — vbat floor 3.61 V early in the flight, final sample 3.95 V; the
log doesn't record why it ended, so that part is yours to tell. One honest
caveat: your stock-b0 60-cell was flown at ~166 Hz link rate and the adjusted one at ~333 Hz,
so the b0 change isn't isolated in that pair. Directionally the picture fits the margin story
from the option-D thread — lower b0 scales the controller output up, raising small-signal
loop gain — but with one flight per cell and that confound, it stays a hypothesis. On "yaw b0
probably needs to be lower": that comes from your PID-toolbox latency matching — your
recommendation, and these logs don't test latency. What they show is that the measured band
metrics rose after the b0 reduction in both cells (band RMS 1.06 → 2.25 deg/s with the peak
at 34.43 → 43.28 Hz in the 50-cell; band RMS 1.25 → 55.53 deg/s with the peak at
40.73 → 46.24 Hz in the 60-cell).

**The 88/88 cell** carries the largest band RMS among your 10 logs of ≥ 30 s (58.03 Hz,
prominence 2667.9, band RMS 7.68 deg/s) and yaw median 19 vs 11 deg/s against the 80/80 cell.
One thing to keep in view: that flight also lowered roll/pitch to wc 76 / wo 126, so it's a
whole-tune change — the numbers describe the cell, not the yaw raise alone.

Three asks, all cheap: a stick-still hover segment in any future yaw log would let the wag
question from the previous flight be separated from commanded motion; one link rate throughout
any future sweep; and a second flight of any cell you consider settled — the 80/80 repeat is the only one in
this 11-log set, and repeats are what turn these single observations into numbers with error
bars.

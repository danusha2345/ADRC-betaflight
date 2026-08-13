@8ksal8 Thanks for digging out the pre-reduction log — analysis added to the same directory
([`pr15400-8ksal8-pavo20/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-pavo20),
`initial.py` + an addendum in ANALYSIS.md):

**These two logs don't separate the tunes much.** The pre-reduction flight is 338.2 s of acro
with tracking medians 1/1/1 deg/s (p90 5/4/6) — the same rounded headline numbers as the
finished flight — and zero windows anywhere that pass the strict quiet-setpoint oscillation
test. In hard-turn windows (|roll/pitch setpoint| > 300 deg/s, 5–30 Hz band error, the finished
flight's rescue span excluded) the observed median is 19.3 deg/s on the initial tune vs 12.1 on
the finished one — but the distributions overlap, the single worst window actually belongs to
the finished flight, and with one flight per tune and 50 %-overlapped windows I'm not claiming
a formal comparison. On the oscillation question: these two logs provide no separating evidence
that the −5 % step removed an instability, and none that one existed — a turn always has an
active setpoint, and inside active-setpoint windows my instruments can't tell propwash,
manoeuvre lag and loop instability apart.

No need to apologise about the deadbands: the header diff records what changed alongside the
tune step — `deadband` 0→3, `yaw_deadband` 0→10, `thr_hover` 30→27, `altitude_prefer_baro`,
`ap_hover_throttle` 1300→1270 and a `d_max` value — so it's all on the table; with two single
flights none of the difference is attributable to any one knob anyway.

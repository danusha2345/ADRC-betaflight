@8ksal8 On the Pavo20 logs — analysis published in
[`pr15400-8ksal8-pavo20/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-pavo20):

**The numbers behind your "flying amazing" impression, and both rescues, are on the record.**
Median tracking error 2/1/2 deg/s (roll/pitch/yaw) with p90 at 7/6/8 over the 320.5 s finished
flight. The RTH log shows `FAILSAFE_GPS_RESCUE` from **61.03 s to 85.59 s** — a 24.6 s rescue
with not one motor sample at the rail anywhere in that flight — and the finished flight
contains the second one, 145.04 s to 189.98 s. Both follow the failsafe box going active
(about 1.5 s before each rescue entry — the failsafe state machine walks its rx-loss stages in
between), i.e. the switch-simulated RX loss; the GPS-rescue box itself never appears in the
mask. Your POSHOLD/ALTHOLD activity after each rescue is in there too.

**The "wobble" log's bursts coincide with logged setpoint activity — with one honest caveat.**
Its worst windows all have the logged setpoint and the gyro moving together at ~2–3 Hz — but
the numeric mode mask shows that flight ran in ANGLE mode (the other two flights are acro with
the airmode box on), and in ANGLE mode the logged setpoint is the self-level loop's output,
not your stick. So I can say no quiet-setpoint window anywhere in that log shows an
oscillating gyro; I cannot separate your stick rhythm from the level loop's own response — in
a feedback loop those traces look the same. The only windows in the whole set that pass the
strict quiet-setpoint test total 3.02 s in the finished flight, roll at 7.0–11.0 Hz — and they
sit inside that flight's GPS rescue and at its exit, on a pack sagged below 10 V; the phase
then returned to IDLE and the flight continued. Tight-turn oscillation is untestable from
these logs by construction (a tight turn always has an active setpoint), so if you still have
a log on the pre-reduction numbers, that comparison is the one I'd run.

One config note from the header diff: between the wobble flight and the finished one the ADRC
numbers did not change — what changed is `deadband` 0 → 3, `yaw_deadband` 0 → 10, `thr_hover`
30 → 27 (plus ANGLE vs acro). So these two logs don't record a before/after of the −5 % step
you described.

**Your b0 yaw = 12307 makes the z3 telemetry ceiling very visible**: the yaw z3 debug channel
saturates in **5.5 / 8.3 / 14.2 %** of frames across the three logs. That's the b9 logging
rail (32767·16 = 524 272), not the controller clamp — the controller's own yaw clamp on your
numbers is `pidsum_limit_yaw · b0` = 4 922 800, and everything between the two is invisible in
a b9 log. The next build writes an `adrc_z3_log_scale` header line sized per-profile; exactly
this tune is what it was built for.

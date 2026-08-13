@8ksal8 The TH3 set is analysed and published:
[`pr15400-8ksal8-th3/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-th3).
Three things worth reporting back:

**The one-tune-three-packs result holds up in the logs.** Tracking error medians 2/2/4, 2/2/3
and 2/2/3 deg/s (roll/pitch/yaw) on 2s/3s/4s with wc/wo fixed and your per-pack b0. Motor-rail
samples fall with pack headroom exactly as you'd hope: 8346 → 1759 → 765. One header note: your
`angle_limit` also moved between packs (40 on 2s, 60 on 3s/4s) — that shapes the ANGLE-mode
wobble logs' setpoint, so those rows aren't comparable across packs either. (The dterm filter
changes I would normally flag turn out not to touch the ADRC D path on this firmware — classic
D gets filtered and then overwritten, and the observer uses its own gyro filter — so they are
not a control-law confound here.)

**Your watt-hour rule vs the measured voltage.** Your b0 steps: 3s/2s = 1.386, 4s/3s = 1.273.
The measured flight-median voltage gives ratios 1.526 and 1.359 — each voltage step sits above
your b0 step (by 10.2 % and 6.7 %), and across the whole 2s→4s range the voltage-proportional
endpoint is 17.6 % above your configured b0 scale. All three configs still flew with similar
rounded tracking metrics. What I can honestly conclude from three uncontrolled flights: the
metrics did not visibly degrade with those b0 offsets on this craft. What I can't: which
scaling rule is "right", or what absorbed the difference — the observer is a natural candidate,
but the true thrust-per-command law isn't exactly voltage-proportional either, and nothing here
separates them. A bench thrust ramp per pack (like the earlier dT/dcmd runs) would.

**Heads-up on your yaw z3 telemetry again**: with yaw b0 = 12500–22050 the yaw z3 debug channel
rails in up to 10.7 % of flight frames and 21.1–26.6 % of the wobble-log frames on b9 — the
logging ceiling again (your yaw clamps sit 9.5–16.8× above it), controller clamp not
implicated. The b10 header-scale fix is exactly for these tunes.

(Your wobble logs are the ANGLE-mode rocking procedure again — noted as such; their numbers
aren't comparable to the acro flights. The eight tuning arms in the archive are preserved in
the PR attachment; I didn't carry them into the repo.)

On the `adrc_hover_throttle` you mentioned forgetting: all six logs record it at 40 on every
pack. It anchors the b0 throttle schedule, so on the packs where your true hover collective
sits away from 40 % the schedule engages at the wrong point — worth setting per profile next
time, as you said.

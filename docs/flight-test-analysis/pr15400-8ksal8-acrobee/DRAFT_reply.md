@8ksal8 This filters pair is a genuinely useful experiment — the ADRC wc/wo/b0 stayed
unchanged while the two flights showed different observed yaw behaviour. Analysis published:
[`pr15400-8ksal8-acrobee/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-acrobee).

**What the toggle actually toggles, from the code.** The profile *gyro* chain (lpf2 + your
three dynamic notches + RPM filter) sits inside the ADRC loop — `pid.c` feeds the filtered
`gyro.gyroADCf` into the controller, and the observer adds its own PT2 on top. The dterm
filters and `yaw_lowpass` don't enter the nominal ADRC P/I/D output (they shape classic terms
that ADRC overwrites). One precision on the intuition you quoted from my TH3 note: turning the
chain off changes both its attenuation *and* its phase/group delay at once, so this pair can't
say which property carries the difference — and two non-randomised flights don't establish
causation at all, only an observed association at an otherwise matching profile.

**The logs record your airmode story.** Filters on: the airmode box went active seven times;
the three activations shorter than 5 s all started at 8.30 V or above (consistent with your
bail-outs — intent isn't a log field, so I'm reporting your account alongside the durations),
the four you flew (12.4–60.3 s) all started at 8.16 V or below. Across the first six the yaw
error decreases while the pack sags — those co-vary with your own input, so no voltage effect
is identified. The seventh activation ends in a terminal high-rate event (over 2000 deg/s,
motors railed, pack at its minimum; the log can't tell a tumble from a crash, a catch or a hard
landing, so no conclusion drawn). Filters off: airmode from 10.1 s at 8.67 V — fresh pack —
held for the whole flight.

**Your yaw oscillation lives in the ~50 Hz band again.** In matched windows (airmode active,
same pack-voltage band; per-window numbers in the write-up) *every* filters-ON window has its
30–80 Hz maximum at 45–55 Hz. In half of them that component dominates the whole spectrum and
sits **8.5× (gyro) / 10.6× (command)** above the filters-OFF median; in the other half a
higher-frequency component dominates and the 30–80 Hz level is near the OFF median
(1.01×/1.21×). Most OFF windows also put their in-band maximum at 45–55 Hz; the per-window RMS values in the
write-up are the amplitude comparison, so this is not a clean presence/absence switch. Same band as your Air65 bench sweeps
(47.9–54.2 Hz across yaw wc 80–120) and the Pavo20 b0-sweep's sustained 48.75 Hz yaw line —
three crafts, three tunes, one band.

**The trade as recorded**: filters off, whole-log error medians rise to 21/19/27 deg/s — that
co-occurs with the visible micro-buzz (a cruise window puts its dominant error content up near
the motor band) — and motor-rail exposure roughly halves (10.39 vs 21.62 rail samples/s). The
error-maxima comparison (210/145/289 vs 2197/2131/2152) is less meaningful than it looks: the
ON maxima all come from that one terminal event. Long-term cost of the buzz (motor heat, wear)
isn't answerable from one pack; your cool-motors report is the only evidence there. If you ever
feel like one more pair on this craft: OFF vs RPM-filter-only would isolate the RPM filter's
incremental contribution (and RPM-only vs full stack would leave lpf2+notches combined) —
though even that separates configuration stages, not attenuation from delay.

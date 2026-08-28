# ADRC plant fitter

This notebook/tool identifies an angular-rate plant from a Betaflight log and
checks an explicit final `wc/wo/b0` triple. It does **not** select a production
`b0` scheduling law and it does not issue a tune recommendation when the input
or fitted model is weak.

## Reproducible environment

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

The included `chirp flight.csv` is the original Air65 example. `Fit_plant.ipynb`
shows the notebook workflow; `plant_fit.py` contains the reusable functions.

## Input contract

The logged controller output must come from one of these exact sources:

1. `adrcPidSum[0..2]` plus `adrc_pid_sum_scale` in a CSV decoded from a newer
   ADRC observability build. These fields are direct snapshots of
   `pidData[].Sum` and are preferred.
2. `axisSum[0..2]` from a Blackbox Explorer CSV export. The exporter and its
   version must travel with the data.

`P+I+D+F` reconstruction is intentionally rejected: it is not generally equal
to the applied/clipped PID sum during recovery, limiting or output clipping.

Raw `.bbl` input is accepted only through `blackbox_decode` built from the clean
`betaflight/blackbox-tools` commit
`f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`. The tool verifies the decoder's
source checkout, writes the exact command and SHA-256 values to a
`*.decode.json` sidecar, and then consumes direct `adrcPidSum[]` if the log has
it.

```bash
git clone https://github.com/betaflight/blackbox-tools.git ~/storage/blackbox-tools
git -C ~/storage/blackbox-tools checkout --detach f832acf9cd9dbe5ad8220de1a5f4eb4021523d72
make -C ~/storage/blackbox-tools
export BLACKBOX_DECODE=~/storage/blackbox-tools/obj/blackbox_decode
```

## Fail-closed output

Every axis gets a `FINAL TUNE CHECK`. A recommendation is blocked when any of
these conditions holds:

- too few coherent fit bins or no sustained measured -3 dB bandwidth;
- the final gain crossover is outside the identified band;
- the `wc` ceiling is unbounded/band-limited by the data;
- the final phase margin is below the requested target or cannot be measured;
- the loop is resonant, the actuator/second pole is unresolved, or independent
  `b0` methods disagree beyond their fit error.

The `wc` ceiling is diagnostic and is always printed together with the `wo`
used by that constant-`wo/wc` sweep. The final table separately prints and
checks the exact `wc/wo/b0` triple passed by the caller.

For the pack-sag discriminator, run `fit_pack_segments(...)`. It fits early and
late sections independently and refuses the paired comparison unless both
segments pass the excitation/model checks. Even a passing within-log ratio is
an offline association, not proof that firmware voltage compensation is
needed: maneuver mix, propwash and temperature still change over the flight.

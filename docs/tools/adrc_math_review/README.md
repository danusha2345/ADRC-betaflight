# ADRC math review — scripts

- `adrc_math_review.py` … `adrc_math_review4.py`: the loop model (symbolic equivalent PID, discrete frequency
  response of the controller as coded, margins vs motor lag, per-path noise, step/disturbance simulation,
  motor-pole-in-ESO variant). `OUTPUT.txt` is their combined output.
- `log_check3.py`: closed-loop fit of a lagged plant (b_acc, τ, delay) to logged stick moves and replay of the
  moves through the law as coded and through the motor-pole variant. Needs the CSV + `.headers.csv` from
  `blackbox_decode --save-headers` (raw units). `log_check.py` holds the loaders; `nolag_fit.py` is the no-lag
  baseline with its gain re-fitted. `logcheck3_out.txt`, `logcheck3_rows.json`, `nolag_rows.json`: results on
  the 23 logs of 2026-10-01 (8ksal8, Petrel75 / Air65 / THIII+ / AOS 3.5 / Pavo20).

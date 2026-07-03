Ready-to-flash Betaflight-ADRC firmware for flight testing — no compiling needed.

**How to flash:** Betaflight Configurator → Firmware Flasher → *Load Firmware [Local]* → pick the `.hex` for your board → *Flash Firmware* (Full chip erase recommended on the first flash).

**Before the first flight:** read the [README](https://github.com/danusha2345/ADRC-betaflight#where-to-enter-the-values-betaflight-configurator-pid-tuning-tab) — ADRC parameters go into the ordinary P/I/D cells of the PID Tuning tab (P = control bandwidth, I = observer bandwidth, D = system gain), and `set pid_at_min_throttle = off` is strongly recommended. The tuning procedure and example tunes are in the README; what changed vs the original ADRC code is in [ADRC_FIXES.md](https://github.com/danusha2345/ADRC-betaflight/blob/master/ADRC_FIXES.md).

**Your board is not in the named list?** Use the **generic hex for your board's MCU** — e.g. `STM32F7X2` for any F722 board, `STM32F405` for F405 boards, `STM32H743`, `AT32F435M/G`, etc. (this is exactly how official Betaflight releases ship). On first connect the Configurator will offer to *Apply custom defaults* for your board — accept it. If you'd rather have a board-baked build, open an [issue](https://github.com/danusha2345/ADRC-betaflight/issues) and we'll add it to the matrix, or build it yourself with `make <TARGET>`.

⚠️ Experimental flight-controller firmware, so far tested by a handful of pilots. Fly in an open area, keep props away from people, and please report results (good or bad) in [issue #1](https://github.com/danusha2345/ADRC-betaflight/issues/1).

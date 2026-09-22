
<img width="1376" height="768" alt="na" src="https://github.com/user-attachments/assets/eb513be2-56d0-4fa1-88e8-2a53b7f61d74" />


# Betaflight ADRC Controller (Active Disturbance Rejection Control)
[![Boosty](https://img.shields.io/badge/Boosty-Buy_me_a_coffee-FF7143?logo=boosty&logoColor=white&style=for-the-badge)](https://boosty.to/danusha/donate)

**English** | [Русский](README.ru.md)

This repository implements **Active Disturbance Rejection Control (ADRC)** on Betaflight, completely replacing the traditional PID loop. ADRC acts as a "PID Killer"—providing incredible stability, robust wind resistance, and smooth handling even with uncalibrated parameters, changing propeller sizes, or extreme, unbalanced dynamic payloads.

> ⚠️ **Experimental fork with ADRC robustness fixes — more flight testers wanted!**
> This fork carries a series of small, independent ADRC robustness fixes on top of
> `Boyyt357/ADRC-betaflight`: anti-windup on the disturbance estimate, saturation-aware
> observer feedback, ADRC-tuned defaults, zero-throttle observer handling, a liftoff gate
> for the observer, a per-craft System-Gain multiplier, and blackbox logging of the
> observer states. Several are **validated in real flights** (5" and 65 mm whoop, one
> independent pilot — takeoff bounce fixed, leaf-blower/stick-strike/prop-cut survival,
> blackbox-confirmed); hardware diversity is still tiny, so results from other stacks are
> the most valuable thing you can contribute. Each fix is its own commit
> (`git revert <sha>` to A/B). Details and flight evidence in [`ADRC_FIXES.md`](ADRC_FIXES.md).
> **Report in [issue `#1` — Call for flight testers](https://github.com/danusha2345/ADRC-betaflight/issues/1).** 🙏

> 🚀 **Heading upstream: [betaflight/betaflight#15400](https://github.com/betaflight/betaflight/pull/15400)** —
> ADRC is on its way into official Betaflight as an opt-in feature (`pid_type = ADRC` per
> profile, classic PID untouched), a draft PR by @bvandevliet carrying this fork's fixes with
> attribution plus a joint review/fix round. This fork remains the fast-iteration testbed and
> its releases stay the easiest way to fly ADRC today; everything validated here feeds
> straight into that PR.

> 📦 **Don't want to compile? [Prebuilt hex files are in Releases](https://github.com/danusha2345/ADRC-betaflight/releases)** — b11 contains 629 board hex files plus generic per-MCU images. F446 images are classic-PID-only because ADRC does not fit in their flash budget. Flash via Configurator → *Load Firmware [Local]*.

---

## For more Info

[![ADRC Betaflight](https://img.youtube.com/vi/BLTQN-Gw7LE/0.jpg)](https://www.youtube.com/watch?v=BLTQN-Gw7LE)



---

## Key Features
- **No Heavy Tuning Required:** Flies exceptionally well even out of the box with rough, uncalibrated values.
- **Unbalanced Payload Handling:** Actively estimates and cancels external forces dynamically, allowing stable flight even with swinging weights attached to a single motor arm.
- **Propeller Versatility:** Dynamically handles transitions between different prop sizes on the fly without changing parameters.

---

## How to set it up (b11 and later)

ADRC is an opt-in control law per PID profile: `set pid_type = ADRC`. Classic PID is untouched. Its parameters
have their own CLI names — the P/I/D cells of the PID Tuning tab are **not** used (that was the pre-PR scheme of
this fork's early versions; a current Configurator with the ADRC page is in
[bvandevliet/betaflight-configurator#5302](https://github.com/betaflight/betaflight-configurator/pull/5302)).

| Setting | Per axis | What it is |
| :--- | :---: | :--- |
| `adrc_b0_roll/pitch/yaw` | yes | **System gain** — how hard the craft accelerates per unit of command. Hardware-dependent; get it from a log with the fitter, do not guess. |
| `adrc_wo_roll/pitch/yaw` | yes | **Observer bandwidth** (rad/s) — how fast disturbances are estimated. Bounded by gyro noise: too high and the motors chatter. |
| `adrc_wc_roll/pitch/yaw` | yes | **Control bandwidth** (rad/s) — response speed. Keep it below `wo`. |
| `adrc_hover_throttle` | | Your real hover throttle (%). The b0 schedule keys on it; a wrong value is a wrong gain. |
| `adrc_b0_law` | | Shape of the throttle→b0 schedule; **SQRT** by default since b11. |
| `adrc_ground_wc` / `adrc_ground_dgain` | | Low `wc` while the liftoff gate is closed (**10 / 4.0 by default since b11**) — the fix for the arm-time lift-off on the ground. |
| `adrc_b0_scale_min`, `adrc_sat_z3_inhibit`, `adrc_zeta_*` | | Opt-ins, off by default: b0 floor below hover, integrator inhibit while the mixer is pinned, per-axis damping ratio. |

**Quick start** (the community procedure, maintained by @jmsweng with an in-browser fitter and a parameter
sandbox: **https://jmsweng.github.io/ADRC-utils/**):

1. Fly one pack on classic PID with Blackbox on; note the hover throttle; do a few brisk stick moves on each axis.
2. Drop the log into the fitter, take the `ctrl-free` b0 per axis **×2**.
3. In the CLI:
   ```
   set pid_type = ADRC
   set adrc_hover_throttle = <your hover %>
   set adrc_b0_roll = <fit>   # and _pitch, _yaw
   set adrc_wc_roll = 80      # and _pitch, _yaw
   set adrc_wo_roll = 90      # and _pitch, _yaw
   save
   ```
4. Filters: keep the RPM filter and a dynamic notch; turn the rest off. ADRC's observer *is* the filter, and
   every low-pass ahead of it is delay that caps `wo`.
5. Props on, airmode on, arm, tap the frame a few times. It must settle within a second and no motor may hit 2047.
   If it rocks or lifts, lower `adrc_ground_wc` (never to 0).
6. Then raise `wo` until the motor line appears in the log and back off ~10 %; `wc ≈ 0.9·wo`.

The reasoning behind every knob, the knee, the gain multipliers and the ground test are in
[`docs/ADRC_GAIN_GUIDE.md`](docs/ADRC_GAIN_GUIDE.md).

### Tunes that fly (September 2026, b11 line)

| Craft | wc / wo | b0 (r / p / y) | notes |
| :--- | :---: | :---: | :--- |
| 5" freestyle, 1750 kV, 4S (jmsweng) | 80 / 90 | from the fitter | flies home on a prop with a missing blade |
| Petrel75 2S whoop (8ksal8) | 84 / 88 | 41 / 26 / 38 | props-in, HQ props; floor 40, LPF1 off / LPF2 525 |
| Air65 1S (8ksal8) | 95 / 106 | 80 / 55 / 36 | |
| Pavo20 Pro 3S (8ksal8) | 72 / 110 | 32 / 20 / 48 | |
| 2.5" (8ksal8, ex-TH3) | 81 / 90 | 49 / 29 / 19 | FIXED law (hover 5); ground wc 40 / 1.0 |

The whoops and the 5" fly `adrc_ground_wc` 10 / `adrc_ground_dgain` 4.0 (the b11 defaults). Whoops that fly zero-throttle into punches want
`adrc_sat_z3_inhibit = ON` (see the guide, §5a).

---

## Prebuilt firmware (no compiling)

The latest tester release, **`adrc-pr15400-b11`**, is on the
[**Releases page**](https://github.com/danusha2345/ADRC-betaflight/releases/tag/adrc-pr15400-b11): 629 board
hex files built by CI from the tagged source (Betaflight master of 2026-09-19 + the ADRC line), plus generic
per-MCU images. Pick your board, or the generic image for your MCU, flash with *Load Firmware [Local]* and accept
*Apply custom defaults*.

> ⚠️ **b11 resets all four PID profiles on upgrade — deliberately.** Save `diff all` first and paste it back
> afterwards. The exp2…exp8 builds claimed to preserve profiles across upgrades; that was wrong (see the erratum
> on their release notes). If you flashed one exp build over another without a full chip erase, check
> `get adrc_` on every profile you fly.

> **F446:** classic-PID-only images — ADRC does not fit its flash. **NEXUSXR:** not built — it overflows ITCM
> on upstream master itself.

## Compiling ADRC-Betaflight
Compiles exactly like standard Betaflight (full docs [here](https://betaflight.com/docs/category/building)). On a normal x86_64 Linux / macOS / WSL host:
```
git clone https://github.com/danusha2345/ADRC-betaflight
cd ADRC-betaflight
make arm_sdk_install   # one-time: downloads the pinned arm-none-eabi GCC (13.3.1)
make configs           # one-time: hydrate the board configs submodule
make DAKEFPVF405       # build your target — replace DAKEFPVF405 with your board
```
The `.hex` lands in `obj/`. (Verified: builds clean for `DAKEFPVF405` / STM32F405 with GCC 13.3.1.)

<details>
<summary>Building on an ARM host (e.g. Raspberry Pi)</summary>

The toolchain `make arm_sdk_install` fetches is x86_64-only, so on an ARM host use the system toolchain instead. Tested on a Raspberry Pi 3B running Raspbian Trixie 13.5:

1) Install the toolchain
```
sudo apt update && sudo apt upgrade
sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential
```
2) Clone and enter the repo
```
git clone https://github.com/danusha2345/ADRC-betaflight
cd ADRC-betaflight
```
3) Comment out the `$(error No toolchain URL defined ...)` line in `mk/tools.mk` (line 43) so the build uses the system toolchain instead of downloading one.
4) Point the build at the system compiler version
```
echo "GCC_REQUIRED_VERSION = $(arm-none-eabi-gcc -dumpversion)" >> mk/local.mk
```
5) Hydrate configs and build
```
make configs
make DAKEFPVF405
```
</details>

---

## 🧪 Testers wanted

Five airframes (5", 2.5", three whoops) and two pilots have flown the b11 line; every claim in the docs is
backed by a Blackbox log in `docs/flight-test-analysis/`. What helps most now: **a craft that is not on that
list**, flown on b11 with Blackbox on, and reported in
[betaflight/betaflight#15400](https://github.com/betaflight/betaflight/pull/15400) with the exact tag, `diff all`,
craft/pack/prop context and the raw log. Props off first, then an open area.

---

## Hardware Issues

Betaflight does not manufacture or distribute their own hardware. While we are collaborating with and supported by a number of manufacturers, we do not do any kind of hardware support.

If you encounter any hardware issues with your flight controller or another component, please contact the manufacturer or supplier of your hardware, or check [Discord](https://discord.gg/n4E6ak4u3c) to see if others with the same problem have found a solution.

## Releases

**ADRC firmware releases (this fork): [github.com/danusha2345/ADRC-betaflight/releases](https://github.com/danusha2345/ADRC-betaflight/releases).**
Stock (PID) Betaflight releases live [here](https://github.com/betaflight/betaflight/releases), with detailed [release notes](https://www.betaflight.com/docs/category/release-notes) at [betaflight.com](https://www.betaflight.com).

## Open Source / Contributors

Betaflight is software that is **open source** and is available free of charge without warranty to all users.

For a complete list of contributors (past and present) see [Github](https://github.com/betaflight/betaflight/graphs/contributors).

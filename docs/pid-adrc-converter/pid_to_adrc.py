#!/usr/bin/env python3
"""
Convert a classic Betaflight PID tune into its mathematically equivalent
second-order bandwidth-parameterized ADRC tune (wc, wo, b0), constrained to
Betaflight's actual CLI-valid ranges.

Background / references
------------------------
Betaflight's ADRC (see src/main/flight/adrc.c) is Gao's standard linear
"bandwidth-parameterized" ADRC:

    kp = wc^2, kd = 2*wc                    (virtual PD control law)
    beta1 = 3*wo, beta2 = 3*wo^2, beta3 = wo^3   (ESO observer gains)

Fredrik Bagge Carlson, "Linear ADRC is equivalent to PID with set-point
weighting and measurement filter" (arXiv:2501.11374,
https://arxiv.org/abs/2501.11374), Appendix A, gives the *exact* PID+filter
controller with identical measurement-to-output response for this exact
parameterization, using Tsettle = 6/wc and g = wo/wc:

    Kp = (72*g^3 + 108*g^2)              / (b0 * (3*g^2 + 6*g + 1) * Ts^2)
    Ki = 216*g^3                         / (b0 * (3*g^2 + 6*g + 1) * Ts^3)
    Kd = (6*g^3 + 36*g^2 + 18*g)         / (b0 * (3*g^2 + 6*g + 1) * Ts)

This is the actual, verified source of every equation in forward() and the
exact branch of solve_exact() below - checked three independent ways: (1)
against the paper's own text, (2) against the reference implementation,
ActiveDisturbanceRejectionControl.jl's `equivalent_pid(Tsettle, ogain, b0;
order=2)` (matches line for line), and (3) against a from-scratch symbolic
derivation of Betaflight's own ESO recursion in adrc.c (z1'=z2-beta1(z1-y),
z2'=z3+b0*u-beta2(z1-y), z3'=-beta3(z1-y), u=(kp(r-z1)-kd*z2-z3)/b0) -
the resulting closed-form transfer function matches this paper's Kp/Ki/Kd/
Tf/d decomposition with zero symbolic discrepancy.

Note: Stankovic, He & Madonski, "From PID to ADRC and back" (arXiv:2305.16705)
is NOT the source of anything implemented here, despite covering similar
ground (PID<->ADRC equivalence, the same wc/wo bandwidth-parameterization
idea). That paper analyzes error-based ADRC (eADRC) - an observer driven by
the tracking error e=r-y directly - which is a different control structure
from what adrc.c implements (an observer driven by the raw measurement y,
i.e. Gao's original output-based ADRC, matching Bagge Carlson's paper
above). Verified: substituting Betaflight's kp=wc^2/kd=2wc/beta_i(wo) into
that paper's eq. (540) general eADRC->PID formula does NOT reproduce the
Kp derived above (Ki and Kd happen to agree; Kp does not) - confirming it
describes a genuinely different scheme, not an equivalent derivation of
the same one.

Two-part strategy
------------------
1. EXACT (preferred): both Ki/Kp and Kd/Kp are independent of b0, so

       Q = Ki * Kd / Kp^2 = (g^2 + 6g + 3) / (2g + 3)^2

   is a plain quadratic in g. This has a real, positive, physically valid
   (g > 1 - see below) root only when Q falls in the family's achievable
   band, (0.25, 0.4) - open at 0.4 too, since Q = 0.4 would require exactly
   g = 1, which the g > 1 rule excludes. When it does, Tsettle follows from Ki/Kp, wc = 6/Ts,
   wo = g*wc, and b0 comes straight out of the Kp equation - an exact,
   zero-residual match. Even then, the resulting (wc, wo, b0) must still be
   checked against Betaflight's CLI ranges (wc: 5-300, wo: 10-600, b0:
   100-65535) - an exact algebraic root is not automatically flyable.

   Why g > 1 specifically: the quadratic has TWO positive roots (verified
   numerically: both forward-map to the identical Kp/Ki/Kd), but g = wo/wc
   must exceed 1 for the observer to be faster than the controller - the
   other root is a spurious artifact of squaring away b0 during elimination,
   not a second usable design.

2. CONSTRAINED BEST FIT (fallback): real Betaflight tunes routinely have
   Q outside (0.25, 0.4) entirely - e.g. the stock roll/pitch defaults give
   Q ~= 0.15-0.16, nowhere near the achievable band, because classic D is
   small relative to P/I in a way this exact ADRC family cannot reproduce
   at ANY (wc, wo, b0). Searching for the "closest" g without bounds is
   degenerate: the achievable Q approaches (never reaches) 0.25 as g -> oo,
   so an unconstrained search runs g (and wo) off to nonsensical values.

   Instead, this searches directly over Betaflight's own CLI box
   (wc in [5,300], wo in [10,600]) for the point that minimizes a weighted
   sum of squared log-errors across Kp, Ki, Kd (b0 has a closed-form
   optimum - a weighted log-mean - for any fixed wc/wo, so the search is
   only 2-D). This is a real constrained optimization, not a heuristic
   default: for the stock roll tune it lands with wo pinned at its CLI
   ceiling (600) and wc settling at an interior optimum (~42), giving
   roughly balanced ~10-20% errors across all three gains instead of an
   exact match on two gains and an arbitrarily large miss on the third.

A note on D = 0 (classic Betaflight yaw defaults to D=0)
---------------------------------------------------------
Kd = 0 only solves the exact system at g = 0 (wo = 0), which adrc.c's own
defense code already treats as "freezes the observer entirely" - so there
is no ADRC equivalent for a D=0 axis in isolation. Betaflight's own
adrcResetProfile() defaults keep wc equal across roll/pitch/yaw and only
lower wo for yaw, so --pin-wc (typically roll's solved wc) reproduces that
convention: wc is held fixed, and Kp/Ki are matched exactly by solving the
resulting *linear* equation for g (Ts is fixed once wc is fixed, so only
one unknown remains).

Caveats (read before trusting the output)
------------------------------------------
- This is an exact equivalence for the *idealized, continuous, linear*
  measurement-to-output path only. The reference-path equivalence is a
  close approximation, not exact (see the paper's own conclusion).
- TPA, anti_gravity, D_max, feedforward, iterm_relax have no ADRC-side
  counterpart in the current implementation. Matching Kp/Ki/Kd at one
  operating point says nothing about behavior where those engage - strip
  them out (e.g. supply gains at TPA=1, away from D_max boost) before
  converting, or expect the "equivalent" tune to diverge from the classic
  tune's feel exactly where those mechanisms matter.
- The derived measurement filter implied by (wc, wo) is not your current
  dterm_lpf1/lpf2 + gyro_lpf1 stack; matching Kp/Ki/Kd does not imply
  matching noise/filtering behavior.
- This is a linear starting point for flight-testing, not a claim that
  pid_type=ADRC with these values reproduces the classic tune's feel.

Usage
-----
    python pid_to_adrc.py --p 45 --i 80 --d 30 --axis roll
    python pid_to_adrc.py --p 45 --i 80 --d 0 --pin-wc 42 --axis yaw
    python pid_to_adrc.py --stock                                    # roll/pitch/yaw defaults
    python pid_to_adrc.py --p 45 --i 80 --d 30 --w-p 1 --w-i 1 --w-d 0.3
"""

import argparse
import math
from dataclasses import dataclass, field

# From src/main/flight/pid.h. Hardcoded copies, not read from the firmware source -
# if these constants or the CLI ranges below ever change upstream, this file goes
# stale silently; re-check against pid.h/settings.c if results look surprising.
PTERM_SCALE = 0.032029
ITERM_SCALE = 0.244381
DTERM_SCALE = 0.000529

# From src/main/cli/settings.c (adrc_wc_*/adrc_wo_*/adrc_b0_* clivalue_t ranges)
WC_MIN, WC_MAX = 5.0, 300.0
WO_MIN, WO_MAX = 10.0, 600.0
B0_MIN, B0_MAX = 100.0, 65535.0

# Stock defaults from src/main/flight/pid.h (PID_ROLL/PITCH/YAW_DEFAULT)
# Results from running this script on the stock defaults are:
# ┌───────┬─────┬─────┬────────────────────────────┬─────────────┬────────────┐
# │ Axis  │ wc  │ wo  │             b0             │ Kp/Ki match │  Kd error  │
# ├───────┼─────┼─────┼────────────────────────────┼─────────────┼────────────┤
# │ Roll  │ 37  │ 149 │ 2328                       │ exact       │ +137.9%    │
# ├───────┼─────┼─────┼────────────────────────────┼─────────────┼────────────┤
# │ Pitch │ 38  │ 150 │ 2252                       │ exact       │ +118.1%    │
# ├───────┼─────┼─────┼────────────────────────────┼─────────────┼────────────┤
# │ Yaw   │ 37  │ 149 │ 2328 (pinned to roll's wc) │ exact       │ n/a (Kd=0) │
# └───────┴─────┴─────┴────────────────────────────┴─────────────┴────────────┘
STOCK_PID = {
    "roll": (45, 80, 30),
    "pitch": (47, 84, 34),
    "yaw": (45, 80, 0),
}


@dataclass
class AdrcSolution:
    g: float          # wo / wc
    Tsettle: float     # 6 / wc
    b0: float
    wc: float
    wo: float
    achieved: tuple[float, float, float]   # (Kp, Ki, Kd) actually produced
    method: str = ""   # "exact" or "constrained-fit"
    cli_valid: bool = field(init=False)

    def __post_init__(self):
        self.cli_valid = in_cli_range(self.wc, self.wo, self.b0)


def in_cli_range(wc: float, wo: float, b0: float) -> bool:
    return WC_MIN <= wc <= WC_MAX and WO_MIN <= wo <= WO_MAX and B0_MIN <= b0 <= B0_MAX


def forward(g: float, Ts: float, b0: float) -> tuple[float, float, float]:
    """ADRC (g, Tsettle, b0) -> equivalent classic (Kp, Ki, Kd)."""
    denom = 3 * g * g + 6 * g + 1
    kp = (72 * g**3 + 108 * g**2) / (b0 * denom * Ts**2)
    ki = (216 * g**3) / (b0 * denom * Ts**3)
    kd = (6 * g**3 + 36 * g**2 + 18 * g) / (b0 * denom * Ts)
    return kp, ki, kd


def cli_to_gains(p: float, i: float, d: float) -> tuple[float, float, float]:
    """Raw Betaflight CLI P/I/D -> internal Kp/Ki/Kd (see pid_init.c)."""
    return PTERM_SCALE * p, ITERM_SCALE * i, DTERM_SCALE * d


def _validate_positive_gains(kp: float, ki: float, kd: float | None = None) -> None:
    """Kp/Ki appear as denominators or inside log() in every solve path below;
    a non-positive value crashes with an unhelpful ZeroDivisionError/ValueError
    deep in the math instead of a clear message. Kd is only checked when given
    (Kd=0 is a legitimate case - e.g. classic yaw - handled by the D=0 branch
    in main() instead of this validator; Kd<0 is never legitimate)."""
    if kp <= 0:
        raise ValueError(f"Kp={kp:.6g} must be positive (classic P gain must be > 0).")
    if ki <= 0:
        raise ValueError(f"Ki={ki:.6g} must be positive (classic I gain must be > 0).")
    if kd is not None and kd < 0:
        raise ValueError(f"Kd={kd:.6g} must be non-negative.")


def _validate_weights(weights: tuple[float, float, float]) -> None:
    """--full-fit's weighted log-mean (in _residual_and_b0) silently produces
    a nonsensical fit for negative weights (no error, just a badly-fit answer
    that looks like any other result) and crashes with ZeroDivisionError if
    every weight is <= 0 (total_w == 0)."""
    if any(w < 0 for w in weights):
        raise ValueError(f"Fit weights must be >= 0, got {weights}.")
    if sum(weights) <= 0:
        raise ValueError(f"At least one fit weight must be > 0, got {weights}.")


# --------------------------------------------------------------------------
# Exact closed-form solve
# --------------------------------------------------------------------------

def _quadratic_roots(a: float, b: float, c: float) -> list[float]:
    # a = 4Q-1 approaches 0 as Q approaches the family's 0.25 achievable-band
    # floor (g -> infinity) - no explicit stability guard here for that near-
    # singular case; not observed to misbehave in testing, but not proven
    # robust arbitrarily close to that boundary either.
    if abs(a) < 1e-15:
        if abs(b) < 1e-15:
            return []
        return [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    sq = math.sqrt(disc)
    return [(-b + sq) / (2 * a), (-b - sq) / (2 * a)]


def solve_exact(kp: float, ki: float, kd: float, min_g: float = 1.0) -> list[AdrcSolution]:
    """Invert classic (Kp, Ki, Kd) -> candidate exact ADRC (wc, wo, b0)
    solutions. Returns all physically-valid (g > min_g) candidates, sorted
    by ascending residual (should be ~0; a nonzero value only reflects
    floating-point error, not model error)."""
    _validate_positive_gains(kp, ki)
    if kd <= 0:
        return []

    q = ki * kd / (kp * kp)
    a = 4 * q - 1
    b = 12 * q - 6
    c = 9 * q - 3

    candidates: list[AdrcSolution] = []
    for g in _quadratic_roots(a, b, c):
        if g <= min_g:
            continue
        ts = 6 * g / ((ki / kp) * (2 * g + 3))
        if ts <= 0:
            continue
        denom = 3 * g * g + 6 * g + 1
        b0 = (72 * g**3 + 108 * g**2) / (kp * denom * ts**2)
        if b0 <= 0:
            continue
        achieved = forward(g, ts, b0)
        wc = 6 / ts
        wo = g * wc
        candidates.append(AdrcSolution(g, ts, b0, wc, wo, achieved, method="exact"))

    candidates.sort(key=lambda s: abs(s.achieved[0] - kp) + abs(s.achieved[1] - ki) + abs(s.achieved[2] - kd))
    return candidates


# --------------------------------------------------------------------------
# Constrained weighted-log best fit, bounded to Betaflight's CLI ranges
# --------------------------------------------------------------------------

def _log_forward_terms(g: float) -> tuple[float, float, float]:
    denom = 3 * g * g + 6 * g + 1
    return (
        math.log((72 * g**3 + 108 * g**2) / denom),
        math.log((216 * g**3) / denom),
        math.log((6 * g**3 + 36 * g**2 + 18 * g) / denom),
    )


def _residual_and_b0(wc: float, wo: float, kp: float, ki: float, kd: float,
                      weights: tuple[float, float, float]) -> tuple[float, float]:
    """For fixed (wc, wo), b0's optimal value in log-space is a simple
    weighted mean (each of Kp/Ki/Kd is affine in log(b0) with slope -1), so
    this is closed-form - no inner optimizer needed."""
    g, ts = wo / wc, 6.0 / wc
    Ap, Ai, Ad = _log_forward_terms(g)
    terms = [
        (Ap - 2 * math.log(ts) - math.log(kp), weights[0]),
        (Ai - 3 * math.log(ts) - math.log(ki), weights[1]),
        (Ad - 1 * math.log(ts) - math.log(kd), weights[2]) if kd > 0 and weights[2] > 0 else None,
    ]
    terms = [t for t in terms if t is not None]
    total_w = sum(w for _, w in terms)
    y = sum(t * w for t, w in terms) / total_w  # log(b0)
    # The residual is a convex quadratic in y, so clamping the unconstrained
    # optimum into the CLI b0 range IS the constrained optimum for this fixed
    # (wc, wo). Without the clamp, extreme tunes made the "CLI-VALID FIT"
    # emit b0 far outside the CLI range (e.g. P=1/I=1/D=1 -> b0=379237).
    y = min(max(y, math.log(B0_MIN)), math.log(B0_MAX))
    resid = sum(w * (t - y) ** 2 for t, w in terms)
    # exp(log(B0_MAX)) can land a few ULP above B0_MAX - clamp again in the
    # linear domain so a pegged b0 still passes the CLI range check exactly.
    return resid, min(max(math.exp(y), B0_MIN), B0_MAX)


def _golden_min(f, lo: float, hi: float, iters: int = 60) -> float:
    gr = (math.sqrt(5) - 1) / 2
    a, b = lo, hi
    c = b - gr * (b - a)
    d = a + gr * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - gr * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + gr * (b - a)
            fd = f(d)
    return (a + b) / 2


def constrained_fit(kp: float, ki: float, kd: float,
                     weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
                     grid: int = 25, polish_rounds: int = 8) -> AdrcSolution:
    """Search Betaflight's actual CLI box (wc in [5,300], wo in [10,600]) for
    the point minimizing a weighted sum of squared log-errors across
    Kp/Ki/Kd. Coarse log-spaced grid, then coordinate-descent polish (each
    round: golden-section refine wc holding wo fixed, then vice versa) -
    this naturally walks to and stays on an active boundary (e.g. wo pinned
    at 600) when that's where the optimum sits, which a naive unconstrained
    search would instead run past to infinity.

    Caveat: grid + coordinate-descent is a heuristic, not a provably global
    optimizer - it has behaved well on every case tested here (the objective
    is smooth), but coordinate descent can in principle stall in a corner
    that isn't the true 2-D optimum for a pathological input."""
    _validate_positive_gains(kp, ki, kd)
    _validate_weights(weights)
    best = None
    wcs = [WC_MIN * (WC_MAX / WC_MIN) ** (i / (grid - 1)) for i in range(grid)]
    wos = [WO_MIN * (WO_MAX / WO_MIN) ** (i / (grid - 1)) for i in range(grid)]
    for wc in wcs:
        for wo in wos:
            r, b0 = _residual_and_b0(wc, wo, kp, ki, kd, weights)
            if best is None or r < best[0]:
                best = (r, wc, wo)
    _, wc, wo = best

    for _ in range(polish_rounds):
        wc = _golden_min(lambda x: _residual_and_b0(x, wo, kp, ki, kd, weights)[0], WC_MIN, WC_MAX)
        wo = _golden_min(lambda x: _residual_and_b0(wc, x, kp, ki, kd, weights)[0], WO_MIN, WO_MAX)

    _, b0 = _residual_and_b0(wc, wo, kp, ki, kd, weights)
    g, ts = wo / wc, 6.0 / wc
    achieved = forward(g, ts, b0)
    return AdrcSolution(g, ts, b0, wc, wo, achieved, method="constrained-fit")


DEFAULT_G = 4.0  # midpoint of the independently-documented "wo ~= 3-5x wc" convention


def solve_pinned_g(kp: float, ki: float, g: float) -> AdrcSolution:
    """Hold g = wo/wc fixed at a chosen ratio and solve the resulting *linear*
    equation in Tsettle that matches Kp and Ki exactly (Kd is not targeted at
    all). This is the recommended default fallback: Kp and Ki are the two
    gains classic PID uses fairly directly (unlike D, which gets reshaped by
    D_max/TPA/dterm filtering, and which we've *proven* is unreachable at
    ANY (wc, wo, b0) for real Betaflight tunes whose Q=Ki*Kd/Kp^2 falls
    outside (0.25, 0.4)) - so matching Kp/Ki exactly and anchoring the one
    remaining degree of freedom to an independently-documented community
    ratio (not a specific current default value) is the most defensible
    from-scratch derivation available, short of an unreliable from-scratch
    physical model (see module docstring)."""
    _validate_positive_gains(kp, ki)
    if g <= 1.0:
        raise ValueError(
            f"g={g:.3f} <= 1 is not a physically valid ADRC design - the observer "
            "must be faster than the controller (see module docstring). Choose --g > 1."
        )
    ts = 6 * g / ((ki / kp) * (2 * g + 3))
    if ts <= 0:
        raise ValueError(f"No positive Tsettle for g={g} - try a different --g.")
    denom = 3 * g * g + 6 * g + 1
    b0 = (72 * g**3 + 108 * g**2) / (kp * denom * ts**2)
    achieved = forward(g, ts, b0)
    wc = 6 / ts
    wo = g * wc
    return AdrcSolution(g, ts, b0, wc, wo, (achieved[0], achieved[1], achieved[2]),
                         method="exact (Kp,Ki only, g pinned)")


def resolve(kp: float, ki: float, kd: float, g: float = DEFAULT_G,
            weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
            full_fit: bool = False) -> AdrcSolution:
    """Top-level entry point.

    1. Try the exact 3-gain closed form; use it only if it also lands inside
       Betaflight's CLI ranges (an exact algebraic root is not automatically
       flyable).
    2. Otherwise, default to solve_pinned_g() - match Kp/Ki exactly at the
       community-convention g, and leave Kd unmatched (with its mismatch
       reported, not hidden). This is the recommended path: see its
       docstring for why chasing Kd is actively counterproductive. If the
       pinned-g solution itself lands outside the CLI box (extreme but
       CLI-legal classic tunes, e.g. P=255/I=1: wc rounds to 0), fall back
       to (3) - settings the CLI would reject are worse than an inexact fit.
    3. Only if full_fit=True (or as the fallback above), use the
       CLI-constrained weighted fit across all three gains instead - useful
       to see "how far off can any tune get on Kd", but not recommended as
       the primary answer, since it distorts wc/wo/b0 chasing a target
       that's provably unreachable.
    """
    for s in solve_exact(kp, ki, kd):
        if s.cli_valid:
            return s
    if full_fit:
        return constrained_fit(kp, ki, kd, weights)
    pinned = solve_pinned_g(kp, ki, g)
    if pinned.cli_valid:
        return pinned
    return constrained_fit(kp, ki, kd, weights)


def solve_pinned_wc(kp: float, ki: float, wc: float) -> AdrcSolution:
    """For a D=0 axis (classic yaw): hold wc fixed (typically matching
    another axis's solved wc, per Betaflight's own adrcResetProfile()
    convention of equal wc across roll/pitch/yaw), and solve the resulting
    *linear* equation in g that matches Kp and Ki exactly. Use this when you
    specifically want to match another axis's wc; use solve_pinned_g()
    (the default) when deriving a fresh, from-scratch tune."""
    _validate_positive_gains(kp, ki)
    if wc <= 0:
        raise ValueError(f"wc={wc} must be positive.")
    ts = 6.0 / wc
    r = (ki / kp) * ts
    denom = 6 - 2 * r
    if denom <= 0:
        raise ValueError(
            f"No positive-g solution for wc={wc}: Ki/Kp ratio is too large "
            "for this wc. Try a smaller --pin-wc."
        )
    g = 3 * r / denom
    if g <= 1.0:
        raise ValueError(
            f"Solved g={g:.3f} <= 1 for wc={wc} - not a physically valid ADRC design "
            "(the observer must be faster than the controller). Try a smaller --pin-wc."
        )
    denom_g = 3 * g * g + 6 * g + 1
    b0 = (72 * g**3 + 108 * g**2) / (kp * denom_g * ts**2)
    achieved = forward(g, ts, b0)
    wo = g * wc
    return AdrcSolution(g, ts, b0, wc, wo, (achieved[0], achieved[1], 0.0), method="exact (Kp,Ki only, wc pinned)")


# --------------------------------------------------------------------------
# CLI plumbing
# --------------------------------------------------------------------------

def print_solution(label: str, p: float, i: float, d: float, sol: AdrcSolution,
                    targets: tuple[float, float, float]) -> None:
    kp, ki, kd = targets
    print(f"\n=== {label}: CLI P={p} I={i} D={d}  ->  Kp={kp:.6f} Ki={ki:.6f} Kd={kd:.6f} ===")
    fkp, fki, fkd = sol.achieved
    if sol.method == "exact":
        tag = "EXACT match, all 3 gains"
    elif sol.method.startswith("exact"):
        tag = "Kp/Ki EXACT match, Kd not targeted"
    else:
        tag = "CLOSEST CLI-VALID FIT, all 3 gains weighted"
    print(f"  [{tag}]  g(wo/wc)={sol.g:.3f}  Tsettle={sol.Tsettle:.4f}s  method={sol.method}")
    for name, achieved, target in (("Kp", fkp, kp), ("Ki", fki, ki), ("Kd", fkd, kd)):
        if target == 0:
            continue
        err_pct = 100 * (achieved - target) / target
        print(f"    {name}: achieved={achieved:.6f}  target={target:.6f}  ({err_pct:+.1f}%)")
    if not sol.cli_valid:
        # Only the pinned-wc (D=0) path can still get here - resolve() falls
        # back to the box-constrained fit instead of returning out-of-range
        # values. Refuse to print settings the CLI would reject.
        print(f"  NO SETTINGS EMITTED: wc={sol.wc:.2f} wo={sol.wo:.2f} b0={sol.b0:.1f} is outside "
              f"Betaflight's CLI-valid ranges "
              f"(wc:[{WC_MIN:.0f},{WC_MAX:.0f}] wo:[{WO_MIN:.0f},{WO_MAX:.0f}] b0:[{B0_MIN:.0f},{B0_MAX:.0f}]) "
              "- adjust the inputs (e.g. a different --pin-wc).")
        return
    if sol.method == "constrained-fit":
        # Only a bounded search can meaningfully "hit a wall" - an exact or
        # pinned solution landing near a bound is coincidental, not evidence
        # of a search running out of room, so this note is method-specific.
        pegged = []
        if abs(sol.wc - WC_MIN) < 1e-6 or abs(sol.wc - WC_MAX) < 1e-6:
            pegged.append("wc")
        if abs(sol.wo - WO_MIN) < 1e-6 or abs(sol.wo - WO_MAX) < 1e-6:
            pegged.append("wo")
        if pegged:
            print(f"  (note: {', '.join(pegged)} pegged at its CLI bound - the fit wants to go further "
                  "but the CLI range stops it there)")
    suffix = label.lower()
    if suffix in STOCK_PID:
        print(f"    -> adrc_wc_{suffix} = {round(sol.wc)}   "
              f"adrc_wo_{suffix} = {round(sol.wo)}   "
              f"adrc_b0_{suffix} = {round(sol.b0)}")
    else:
        # No --axis given: only adrc_*_{roll,pitch,yaw} exist in the CLI, so
        # don't fabricate an "adrc_wc_axis" command that doesn't parse.
        print(f"    -> wc = {round(sol.wc)}   wo = {round(sol.wo)}   b0 = {round(sol.b0)}   "
              "(apply as adrc_{wc,wo,b0}_<roll|pitch|yaw>, or pass --axis)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--p", type=float, help="Classic CLI P gain")
    ap.add_argument("--i", type=float, help="Classic CLI I gain")
    ap.add_argument("--d", type=float, help="Classic CLI D gain")
    ap.add_argument("--pin-wc", type=float, default=None,
                     help="Fixed wc to use when D=0 (e.g. yaw) - typically another "
                          "axis's solved wc, matching Betaflight's own equal-wc convention")
    ap.add_argument("--g", type=float, default=DEFAULT_G,
                     help=f"wo/wc ratio to pin for the recommended Kp/Ki-only fallback "
                          f"(default {DEFAULT_G}, the midpoint of the community's 'wo ~= 3-5x wc' convention)")
    ap.add_argument("--full-fit", action="store_true",
                     help="Use the CLI-constrained weighted fit across all 3 gains instead of "
                          "the recommended Kp/Ki-only fallback (see module docstring for why "
                          "this is NOT the default: it distorts wc/wo/b0 chasing a Kd target "
                          "that's provably unreachable for most real classic tunes)")
    ap.add_argument("--w-p", type=float, default=1.0, help="--full-fit weight for Kp (default 1.0)")
    ap.add_argument("--w-i", type=float, default=1.0, help="--full-fit weight for Ki (default 1.0)")
    ap.add_argument("--w-d", type=float, default=1.0, help="--full-fit weight for Kd (default 1.0)")
    ap.add_argument("--stock", action="store_true",
                     help="Run the built-in Betaflight stock roll/pitch/yaw defaults instead")
    ap.add_argument("--axis", choices=sorted(STOCK_PID),
                     help="Axis the single-tune result is for - selects the real CLI suffix "
                          "(adrc_*_roll/pitch/yaw) in the output")
    args = ap.parse_args()
    weights = (args.w_p, args.w_i, args.w_d)

    try:
        if args.stock:
            roll_kp, roll_ki, roll_kd = cli_to_gains(*STOCK_PID["roll"])
            roll_sol = resolve(roll_kp, roll_ki, roll_kd, g=args.g, weights=weights, full_fit=args.full_fit)
            print_solution("Roll", *STOCK_PID["roll"], roll_sol, (roll_kp, roll_ki, roll_kd))

            pitch_kp, pitch_ki, pitch_kd = cli_to_gains(*STOCK_PID["pitch"])
            pitch_sol = resolve(pitch_kp, pitch_ki, pitch_kd, g=args.g, weights=weights, full_fit=args.full_fit)
            print_solution("Pitch", *STOCK_PID["pitch"], pitch_sol, (pitch_kp, pitch_ki, pitch_kd))

            yaw_kp, yaw_ki, _ = cli_to_gains(*STOCK_PID["yaw"])
            # NOTE: must use "is None", not "or" - an explicit --pin-wc 0 is falsy
            # and would otherwise be silently discarded in favor of roll_sol.wc.
            pin_wc = args.pin_wc if args.pin_wc is not None else roll_sol.wc
            yaw_sol = solve_pinned_wc(yaw_kp, yaw_ki, pin_wc)
            print_solution("Yaw", *STOCK_PID["yaw"], yaw_sol, (yaw_kp, yaw_ki, 0.0))
            return

        if args.p is None or args.i is None or args.d is None:
            ap.error("--p/--i/--d are required unless --stock is given")

        kp, ki, kd = cli_to_gains(args.p, args.i, args.d)
        label = args.axis.capitalize() if args.axis else "Axis"

        if args.d == 0 or kd <= 0:
            if args.pin_wc is None:
                ap.error("D=0: pass --pin-wc (e.g. the wc solved for roll/pitch)")
            if args.full_fit or args.g != DEFAULT_G or weights != (1.0, 1.0, 1.0):
                print("  (note: --full-fit/--g/--w-p/--w-i/--w-d have no effect on the "
                      "D=0 path, which always uses solve_pinned_wc())")
            sol = solve_pinned_wc(kp, ki, args.pin_wc)
            print_solution(label, args.p, args.i, args.d, sol, (kp, ki, 0.0))
        else:
            sol = resolve(kp, ki, kd, g=args.g, weights=weights, full_fit=args.full_fit)
            print_solution(label, args.p, args.i, args.d, sol, (kp, ki, kd))
    except ValueError as e:
        ap.error(str(e))


if __name__ == "__main__":
    main()

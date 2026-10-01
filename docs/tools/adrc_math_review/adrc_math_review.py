#!/usr/bin/env python3
"""Numerical review of the LADRC rate loop as implemented in src/main/flight/adrc.c (adrc-sync-1001).

Part 1  sympy: the measurement path u/y of the LADRC as an equivalent PID + 2nd-order filter
Part 2  discrete frequency-domain model of the loop exactly as coded (Euler ESO, pt2 pre-filter,
        one-loop output delay) against a plant  w' = b_acc * T,  tau T' = u - T  (motor lag):
        stability margins, per-path gyro-noise gains
Part 3  time-domain simulation of the coded loop: setpoint step with F = 0 / BF default / model F,
        disturbance step
"""
import numpy as np
import sympy as sp
from scipy.signal import cont2discrete

DT = 1 / 8000.0
PTERM_SCALE, ITERM_SCALE, DTERM_SCALE, FF_SCALE = 0.032029, 0.244381, 0.000529, 0.013754
CUT_PT2 = 1.553773974

# ----------------------------------------------------------------------------------------- part 1
def part1():
    s, wc, wo, b0 = sp.symbols('s w_c w_o b_0', positive=True)
    kp, kd = wc**2, 2 * wc
    b1, b2, b3 = 3 * wo, 3 * wo**2, wo**3
    # ESO with u = (kp r - K z)/b0 substituted (no leak): A_cl = A - B K / b0
    A_cl = sp.Matrix([[-b1, 1, 0], [-b2 - kp, -kd, 0], [-b3, 0, 0]])
    L = sp.Matrix([b1, b2, b3])
    K = sp.Matrix([[kp, kd, 1]])
    Cy = sp.simplify((K * (s * sp.eye(3) - A_cl).inv() * L)[0] / b0)   # u = -Cy * y
    num, den = sp.fraction(sp.together(Cy))
    num, den = sp.Poly(sp.expand(num), s), sp.Poly(sp.expand(den), s)
    print("u/(-y) numerator  :", num.as_expr())
    print("u/(-y) denominator:", den.as_expr())
    # den = b0 * s * (s^2 + a1 s + a0) ; ideal PID (Kd s^2 + Kp s + Ki)/s times a0/(s^2+a1 s+a0)
    dc = den.all_coeffs()  # [b0, b0 a1, b0 a0, 0]
    a1, a0 = sp.simplify(dc[1] / dc[0]), sp.simplify(dc[2] / dc[0])
    nc = num.all_coeffs()
    Kd_eq, Kp_eq, Ki_eq = [sp.simplify(c / (dc[0] * a0)) for c in nc]
    print("equivalent PID:  Kp =", sp.factor(Kp_eq), "  Ki =", sp.factor(Ki_eq), "  Kd =", sp.factor(Kd_eq))
    print("filter: s^2 + a1 s + a0,  a1 =", sp.factor(a1), "  a0 =", sp.factor(a0))
    for name, vals in [("default 60/100/2000", (60, 100, 2000)), ("Air65 99/110/5378", (99, 110, 5378)),
                       ("5in 103/140/3000", (103, 140, 3000))]:
        sub = {wc: vals[0], wo: vals[1], b0: vals[2]}
        Kp_, Ki_, Kd_ = [float(x.subs(sub)) for x in (Kp_eq, Ki_eq, Kd_eq)]
        a1_, a0_ = float(a1.subs(sub)), float(a0.subs(sub))
        wn, zeta = np.sqrt(a0_), a1_ / (2 * np.sqrt(a0_))
        print(f"  {name}: Kp={Kp_:.3f} Ki={Ki_:.2f} Kd={Kd_:.4f}  -> BF-style P={Kp_/PTERM_SCALE:.0f} "
              f"I={Ki_/ITERM_SCALE:.0f} D={Kd_/DTERM_SCALE:.0f}; filter wn={wn:.0f} rad/s ({wn/2/np.pi:.0f} Hz) zeta={zeta:.2f}")

# ----------------------------------------------------------------------------------------- part 2
def controller_dss(wc, wo, b0, sigma=0.3, gyro_lpf_hz=150.0, dt=DT):
    """Discrete state-space of the coded controller. state x = [s1, s, z1, z2, z3, up]; inputs [y, r]; output u."""
    kp, kd = wc * wc, 2 * wc
    b1, b2, b3 = 3 * wo, 3 * wo**2, wo**3
    om = 2 * np.pi * gyro_lpf_hz * CUT_PT2 * dt
    k = om / (om + 1) if gyro_lpf_hz > 0 else 1.0
    n = 6
    A = np.zeros((n, n)); B = np.zeros((n, 2))
    # pt2
    A[0, 0] = 1 - k; B[0, 0] = k                              # s1' = s1 + k (y - s1)
    A[1, :] = A[0, :] * k; A[1, 1] += 1 - k; B[1, :] = B[0, :] * k  # s' = s + k (s1' - s)
    yf = (A[1, :], B[1, :])
    # e = z1 - yf
    e_x = np.zeros(n); e_x[2] = 1; e_x -= yf[0]; e_u = -yf[1]
    # z1' = z1 + dt (z2 - b1 e)
    A[2, :] = -dt * b1 * e_x; A[2, 2] += 1; A[2, 3] += dt; B[2, :] = -dt * b1 * e_u
    # z2' = z2 + dt (z3 + b0 up - b2 e)
    A[3, :] = -dt * b2 * e_x; A[3, 3] += 1; A[3, 4] += dt; A[3, 5] += dt * b0; B[3, :] = -dt * b2 * e_u
    # z3' = (1 - dt sigma) z3 - dt b3 e
    A[4, :] = -dt * b3 * e_x; A[4, 4] += 1 - dt * sigma; B[4, :] = -dt * b3 * e_u
    # u = (kp (r - z1') - kd z2' - z3') / b0   (function of next state and r)
    Cn = np.zeros(n); Cn[2] = -kp; Cn[3] = -kd; Cn[4] = -1; Cn /= b0
    Dr = np.array([0.0, kp / b0])
    C = Cn @ A; D = Cn @ B + Dr
    A[5, :] = C; B[5, :] = D                                   # up' = u
    return A, B, C, D

def freqresp(A, B, C, D, w, dt=DT):
    z = np.exp(1j * w * dt)
    n = A.shape[0]
    H = np.empty((len(w),) + D.shape, dtype=complex)
    for i, zi in enumerate(z):
        H[i] = C @ np.linalg.solve(zi * np.eye(n) - A, B) + D
    return H

def plant_dss(b_acc, tau, dt=DT):
    # w' = b_acc T ; tau T' = u - T   ->  states [w, T]
    Ac = np.array([[0, b_acc], [0, -1 / tau]]); Bc = np.array([[0], [1 / tau]]); Cc = np.array([[1, 0]]); Dc = np.zeros((1, 1))
    Ad, Bd, Cd, Dd, _ = cont2discrete((Ac, Bc, Cc, Dc), dt, method='zoh')
    return Ad, Bd, Cd, Dd

def pt1_resp(hz, w, dt=DT):
    om = 2 * np.pi * hz * dt; k = om / (om + 1); z = np.exp(1j * w * dt)
    return k / (1 - (1 - k) / z)

def margins(w, L):
    mag, ph = np.abs(L), np.unwrap(np.angle(L))
    out = {}
    i = np.where(np.diff(np.sign(mag - 1)))[0]
    if len(i):
        j = i[0]; out['wgc'] = w[j]; out['PM'] = 180 + np.degrees(ph[j])
    i = np.where(np.diff(np.sign(ph + np.pi)))[0]
    if len(i):
        j = i[0]; out['wpc'] = w[j]; out['GM_dB'] = -20 * np.log10(mag[j])
    return out

def part2():
    w = np.logspace(0, np.log10(np.pi / DT * 0.99), 4000)
    print("\n== stability margins; plant w' = b_acc T, tau T' = u - T; b0 = b_acc/tau (matched); gyro lpf1 250 Hz + lpf2 500 Hz + ADRC pt2 150 Hz")
    print(f"{'tune':>22} {'tau ms':>6} {'PM deg':>7} {'GM dB':>6} {'f_gc Hz':>8}")
    G = pt1_resp(250, w) * pt1_resp(500, w)
    for (wc, wo) in [(60, 100), (99, 110), (103, 140), (122, 128), (140, 150)]:
        for tau in (0.010, 0.020, 0.030):
            b0 = 2000.0; b_acc = b0 * tau
            A, B, C, D = controller_dss(wc, wo, b0)
            Hy = freqresp(A, B, C, D, w)[:, 0]          # u/y (negative feedback sign included: u = -Cy y)
            Ad, Bd, Cd, Dd = plant_dss(b_acc, tau)
            P = freqresp(Ad, Bd, Cd, Dd, w)[:, 0, 0]
            L = -Hy * G * P
            m = margins(w, L)
            print(f"{str((wc,wo)):>22} {tau*1e3:6.0f} {m.get('PM',float('nan')):7.1f} {m.get('GM_dB',float('nan')):6.1f} {m.get('wgc',float('nan'))/2/np.pi:8.1f}")
    print("\n== b0 mismatch at 60/100, tau 20 ms (b0 fixed 2000, plant b_acc varied)")
    for ratio in (0.5, 0.7, 1.0, 1.5, 2.0, 3.0):
        A, B, C, D = controller_dss(60, 100, 2000.0)
        Hy = freqresp(A, B, C, D, w)[:, 0]
        Ad, Bd, Cd, Dd = plant_dss(2000.0 * 0.020 * ratio, 0.020)
        P = freqresp(Ad, Bd, Cd, Dd, w)[:, 0, 0]
        m = margins(w, -Hy * G * P)
        print(f"  b/b0 = {ratio:3.1f}: PM {m.get('PM',float('nan')):6.1f} deg, GM {m.get('GM_dB',float('nan')):5.1f} dB, f_gc {m.get('wgc',float('nan'))/2/np.pi:6.1f} Hz")

    print("\n== gyro-noise gain into pidsum, per path (white noise through gyro filters + ADRC pt2), RMS of u per unit RMS noise")
    for (wc, wo, b0, name) in [(60, 100, 2000, 'default'), (99, 110, 5378, 'Air65'), (103, 140, 3000, '5in 103/140')]:
        kp, kd = wc * wc, 2 * wc
        A, B, C, D = controller_dss(wc, wo, b0)
        # per-path: outputs z1', z2', z3' (next state) from y
        Cz = A[2:5, :]; Dz = B[2:5, :]
        Hz = freqresp(A, B, Cz, Dz, w)[:, :, 0]
        Hu = freqresp(A, B, C, D, w)[:, 0]
        Gf = pt1_resp(250, w) * pt1_resp(500, w)
        # integrate |H|^2 over frequency (uniform white noise up to Nyquist)
        def rms(H): return np.sqrt(np.trapezoid(np.abs(H * Gf)**2, w) / (np.pi / DT))
        print(f"  {name:12} P(kp z1/b0)={rms(kp*Hz[:,0]/b0):.3f}  D(kd z2/b0)={rms(kd*Hz[:,1]/b0):.3f}  I(z3/b0)={rms(Hz[:,2]/b0):.3f}  total={rms(Hu):.3f}"
              f"   | classic BF P45 D30 (D via 100 Hz pt1): P={rms(45*PTERM_SCALE*np.ones_like(w)):.3f} D={rms(30*DTERM_SCALE*(1j*w)*pt1_resp(100,w)):.3f}")
        # frequency where |u/y| peaks and the per-path value at 20 and 50 Hz
        for f in (10, 20, 50, 100):
            i = np.argmin(abs(w - 2 * np.pi * f))
            print(f"      {f:3d} Hz: |P|={abs(kp*Hz[i,0]/b0):.2f} |D|={abs(kd*Hz[i,1]/b0):.2f} |I|={abs(Hz[i,2]/b0):.2f} |u/y|={abs(Hu[i]):.2f}")

# ----------------------------------------------------------------------------------------- part 3
def simulate(wc, wo, b0, b_acc, tau, F_bf=0.0, T=0.4, step=100.0, dist=0.0, dist_t=0.2, sigma=0.3, lpf_hz=150.0, delay_loops=1, dt=DT):
    kp, kd = wc * wc, 2 * wc; b1, b2, b3 = 3 * wo, 3 * wo**2, wo**3
    om = 2 * np.pi * lpf_hz * CUT_PT2 * dt; k = om / (om + 1)
    Kf = FF_SCALE * F_bf / 100.0
    s1 = s = z1 = z2 = z3 = 0.0; wrate = Tm = 0.0; up = 0.0; r_prev = 0.0
    hist = []; ubuf = [0.0] * delay_loops
    for n in range(int(T / dt)):
        t = n * dt
        r = step if t >= 0.05 else 0.0
        d = dist if t >= dist_t else 0.0
        y = wrate
        s1 += k * (y - s1); s += k * (s1 - s)
        e = z1 - s
        z1 += dt * (z2 - b1 * e); z2 += dt * (z3 + b0 * up - b2 * e); z3 = z3 - dt * sigma * z3 - dt * b3 * e
        z3 = max(-500 * b0, min(500 * b0, z3))
        u = (kp * (r - z1) - kd * z2 - z3) / b0
        ff = Kf * (r - r_prev) / dt; r_prev = r
        usum = max(-500.0, min(500.0, u + ff))
        ubuf.append(usum); ua = ubuf.pop(0)
        up = usum
        # plant, forward Euler at 8 kHz with the applied command
        Tm += dt * (ua - Tm) / tau
        wrate += dt * (b_acc * Tm + d)
        hist.append((t, r, wrate, usum, z3))
    return np.array(hist)

def part3():
    print("\n== setpoint step 100 deg/s at 50 ms, default 60/100/2000, plant tau 20 ms matched; rise 10-90 %, overshoot")
    for F in (0.0, 120.0, 2 * 60 / 2000.0 / FF_SCALE * 100):
        h = simulate(60, 100, 2000, 2000 * 0.02, 0.02, F_bf=F)
        y = h[:, 2]; t = h[:, 0]; i10 = np.argmax(y >= 10); i90 = np.argmax(y >= 90)
        print(f"  F_bf={F:6.0f}: rise {1e3*(t[i90]-t[i10]):5.1f} ms, overshoot {max(y)-100:5.1f} deg/s, settle(2%) {1e3*(t[np.where(abs(y-100)>2)[0][-1]]-0.05):5.1f} ms")
    print("== same, Air65 99/110/5378, tau 10 ms")
    for F in (0.0, 120.0):
        h = simulate(99, 110, 5378, 5378 * 0.01, 0.01, F_bf=F)
        y = h[:, 2]; t = h[:, 0]; i10 = np.argmax(y >= 10); i90 = np.argmax(y >= 90)
        print(f"  F_bf={F:6.0f}: rise {1e3*(t[i90]-t[i10]):5.1f} ms, overshoot {max(y)-100:5.1f} deg/s")
    print("== disturbance step 20000 deg/s^2 (torque bump) at 0.2 s, no setpoint; default tune; peak and 90 % recovery")
    for (wc, wo, b0, tau, name) in [(60, 100, 2000, 0.02, 'default'), (99, 110, 5378, 0.01, 'Air65'), (60, 150, 2000, 0.02, 'wo 150')]:
        h = simulate(wc, wo, b0, b0 * tau, tau, step=0.0, dist=20000.0, T=0.5)
        y = h[:, 2]; t = h[:, 0]; pk = np.max(np.abs(y)); ipk = np.argmax(np.abs(y))
        rec = t[ipk + np.argmax(np.abs(y[ipk:]) < 0.1 * pk)] - 0.2
        print(f"  {name:8}: peak {pk:6.1f} deg/s at {1e3*(t[ipk]-0.2):4.1f} ms, back within 10 % after {1e3*rec:5.1f} ms")

if __name__ == '__main__':
    part1(); part2(); part3()

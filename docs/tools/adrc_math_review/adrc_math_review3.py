import numpy as np
from adrc_math_review import *
from scipy.integrate import solve_ivp

def sim_meso(wc, wo, b0, b_acc, tau, tau_model=None, T=0.4, step=100.0, dist=0.0, dist_t=0.2, sigma=0.3, lpf_hz=150.0, dt=DT, noise=0.0, seed=1):
    """Same loop as simulate(); if tau_model is set, the ESO includes the motor pole: z2' += -z2/tau_model and the law uses kd - 1/tau_model."""
    kp, kd = wc*wc, 2*wc; b1,b2,b3 = 3*wo, 3*wo**2, wo**3
    om = 2*np.pi*lpf_hz*CUT_PT2*dt; k = om/(om+1) if lpf_hz > 0 else 1.0
    inv_tau = 1.0/tau_model if tau_model else 0.0
    rng = np.random.default_rng(seed)
    s1=s=z1=z2=z3=0.0; wr=Tm=0.0; up=0.0; out=[]
    for n in range(int(T/dt)):
        t=n*dt; r = step if t>=0.05 else 0.0; d = dist if t>=dist_t else 0.0
        y = wr + noise*rng.standard_normal()
        s1 += k*(y-s1); s += k*(s1-s); e = z1-s
        z1 += dt*(z2-b1*e); z2 += dt*(z3 + b0*up - inv_tau*z2 - b2*e); z3 = z3-dt*sigma*z3-dt*b3*e
        u = (kp*(r-z1) - (kd-inv_tau)*z2 - z3)/b0
        us = max(-500.0,min(500.0,u)); up=us
        Tm += dt*(us-Tm)/tau; wr += dt*(b_acc*Tm + d); out.append((t,r,wr,us,z3))
    return np.array(out)

def metrics(h):
    y=h[:,2]; t=h[:,0]; i10=np.argmax(y>=10); i90=np.argmax(y>=90)
    return 1e3*(t[i90]-t[i10]), max(y)-100

print("== model-assisted ESO (motor pole in the observer): step 100 deg/s, wc 60 / wo 100 / b0 2000, plant tau 20 ms")
for label, tm in [("plain (current code)", None), ("tau_model = tau", 0.02), ("tau_model = 0.7 tau", 0.014), ("tau_model = 1.5 tau", 0.03), ("tau_model = 2 tau", 0.04)]:
    r, o = metrics(sim_meso(60,100,2000,40.0,0.02,tm)); print(f"  {label:22}: rise {r:5.1f} ms, overshoot {o:5.1f} %")
print("   same, plant tau 10 ms (b_acc 20):")
for label, tm in [("plain", None), ("tau_model = tau", 0.01), ("tau_model = 2 tau", 0.02)]:
    r, o = metrics(sim_meso(60,100,2000,20.0,0.01,tm)); print(f"  {label:22}: rise {r:5.1f} ms, overshoot {o:5.1f} %")
print("   Air65 99/110/5378, plant tau 8 ms:")
for label, tm in [("plain", None), ("tau_model = tau", 0.008)]:
    r, o = metrics(sim_meso(99,110,5378,5378*0.008,0.008,tm)); print(f"  {label:22}: rise {r:5.1f} ms, overshoot {o:5.1f} %")

print("\n== disturbance 2000 deg/s^2 with MESO (wc 60/wo 100, tau 20 ms): peak, z3 at end (should be ~ -2000 for the true disturbance only)")
for label, tm in [("plain", None), ("tau_model = tau", 0.02)]:
    h = sim_meso(60,100,2000,40.0,0.02,tm, step=0.0, dist=2000.0, T=0.6); y=h[:,2]; t=h[:,0]; i0=np.argmax(t>=0.2)
    print(f"  {label:16}: peak {np.max(np.abs(y[i0:])):5.1f} deg/s, z3(end) {h[-1,4]:8.0f}")

print("\n== continuous-time cross-check (RK45, ideal sampling-free loop) of the plain law: overshoot vs wo at tau 20 ms")
def ct(wc, wo, b0, b_acc, tau):
    kp,kd=wc*wc,2*wc; b1,b2,b3=3*wo,3*wo**2,wo**3
    def f(t,x):
        w,Tm,z1,z2,z3 = x; r = 100.0 if t>=0.05 else 0.0
        u = (kp*(r-z1)-kd*z2-z3)/b0; e = z1-w
        return [b_acc*Tm, (u-Tm)/tau, z2-b1*e, z3+b0*u-b2*e, -0.3*z3-b3*e]
    sol = solve_ivp(f,[0,0.4],[0,0,0,0,0],max_step=1e-4,rtol=1e-8,atol=1e-8)
    return max(sol.y[0])-100
for wo in (100,150,300):
    print(f"  wo {wo}: overshoot {ct(60,wo,2000,40.0,0.02):5.1f} %   (discrete sim gave {metrics(sim_meso(60,wo,2000,40.0,0.02))[1]:5.1f} %)")

print("\n== pre-ESO pt2 (adrc_gyro_lpf_hz 150): noise RMS gain and phase margin with / without, under default gyro filters and under loose ones (lpf1 off, lpf2 500)")
w = np.logspace(0, np.log10(np.pi/DT*0.99), 4000)
def rms(H): return np.sqrt(np.trapezoid(np.abs(H)**2, w)/(np.pi/DT))
for gname, G in [("gyro lpf1 250 + lpf2 500", pt1_resp(250,w)*pt1_resp(500,w)), ("lpf1 off, lpf2 500", pt1_resp(500,w))]:
    for lpf in (150.0, 0.0):
        A,B,C,D = controller_dss(60,100,2000.0, gyro_lpf_hz=lpf); Hy = freqresp(A,B,C,D,w)[:,0]
        Ad,Bd,Cd,Dd = plant_dss(40.0,0.02); P = freqresp(Ad,Bd,Cd,Dd,w)[:,0,0]; m = margins(w,-Hy*G*P)
        print(f"  {gname:26} pt2 {lpf:3.0f} Hz: noise gain {rms(Hy*G):.3f}, PM {m['PM']:.1f} deg, GM {m['GM_dB']:.1f} dB")

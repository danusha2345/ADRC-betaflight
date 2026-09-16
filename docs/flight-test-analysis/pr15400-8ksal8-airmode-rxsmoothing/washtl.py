import sys, numpy as np
f=sys.argv[1]; t0=float(sys.argv[2]); pre=float(sys.argv[3]) if len(sys.argv)>3 else 1.5; post=0.2; step=int(sys.argv[4]) if len(sys.argv)>4 else 25
hdr=[c.strip() for c in open(f).readline().strip().split(',')]
a=np.genfromtxt(f,delimiter=',',skip_header=1,usecols=range(len(hdr)),filling_values=0,invalid_raise=False)
c=lambda k:a[:,hdr.index(k)]
t=(c('time (us)')-c('time (us)')[0])/1e6
i0=np.searchsorted(t,t0-pre); i1=np.searchsorted(t,t0+post)
print("t     thr  sp_r sp_p sp_y | gy_r gy_p gy_y | I_r I_p I_y | PS_r PS_p PS_y | m0 m1 m2 m3 | vbat A st d7")
for i in range(i0,i1,step):
    print(f"{t[i]:6.2f} {c('rcCommand[3]')[i]:4.0f} {c('setpoint[0]')[i]:5.0f}{c('setpoint[1]')[i]:5.0f}{c('setpoint[2]')[i]:5.0f} |{c('gyroADC[0]')[i]:5.0f}{c('gyroADC[1]')[i]:5.0f}{c('gyroADC[2]')[i]:5.0f} |{c('axisI[0]')[i]:5.0f}{c('axisI[1]')[i]:5.0f}{c('axisI[2]')[i]:5.0f} |{c('adrcPidSum[0]')[i]:7.0f}{c('adrcPidSum[1]')[i]:7.0f}{c('adrcPidSum[2]')[i]:7.0f} |{c('motor[0]')[i]:5.0f}{c('motor[1]')[i]:5.0f}{c('motor[2]')[i]:5.0f}{c('motor[3]')[i]:5.0f} | {c('vbatLatest (V)')[i]:.2f} {c('amperageLatest (A)')[i]:3.0f} {c('adrcState')[i]:3.0f} {c('debug[7]')[i]:4.0f}")

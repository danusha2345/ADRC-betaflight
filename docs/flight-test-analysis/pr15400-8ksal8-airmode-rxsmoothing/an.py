import csv, sys, re, numpy as np
from scipy.signal import welch, find_peaks
def headers(bbl):
    d=open(bbl,'rb').read(300000); o={}
    for m in re.finditer(rb"H ([^:\n]+):([^\n]*)\n", d):
        o.setdefault(m.group(1).decode(errors='ignore'), m.group(2).decode(errors='ignore').strip())
    return o
def load(p):
    with open(p) as fh:
        rd=csv.reader(fh); names=[c.strip().split(' ')[0] for c in next(rd)]
        rows=[r for r in rd if len(r)==len(names)]
    d={}
    for n,col in zip(names,zip(*rows)):
        try: d[n]=np.array([x.strip() for x in col],dtype=float)
        except ValueError: pass
    return d
def line(x,fs):
    f,P=welch(x-x.mean(),fs=fs,nperseg=int(fs*2)); m=(f>=40)&(f<=80)
    i=np.argmax(P[m]); fpk=f[m][i]
    band=(f>=fpk-2)&(f<=fpk+2)
    rms=np.sqrt(np.trapz(P[band],f[band]))
    base=np.median(P[(f>=10)&(f<=150)])
    return fpk, rms, P[m][i]/base
def liftmask(d):
    if 'adrcState' in d: return (d['adrcState'].astype(int)&1)>0
    return d['debug[7]']>0
if __name__=='__main__':
  for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv'))
    t=d['time']*1e-6; fs=1/np.median(np.diff(t))
    lift=liftmask(d)
    if lift.sum()==0: print(bbl,'no liftoff'); continue
    i0=np.argmax(lift); sl=slice(i0,len(t))
    span=t[-1]-t[i0]
    print(f"\n### {bbl.split('/')[-1]}")
    print(f"wc/wo {h.get('adrcWC')}/{h.get('adrcWO')} b0 {h.get('adrcB0')} sigma_decay {h.get('adrc_sigma_decay')} b0_scale_max {h.get('adrc_b0_scale_max')} pamt {h.get('pid_at_min_throttle')} fs={fs:.0f} span(after gate)={span:.1f}s gate open {lift[sl].mean()*100:.1f}% total {t[-1]:.1f}s")
    vb=d['vbatLatest'][sl]; am=d.get('amperageLatest',np.zeros(len(t)))[sl]
    print(f"vbat med/min {np.median(vb):.2f}/{vb.min():.2f} V  amp med/p95/max {np.median(am):.1f}/{np.percentile(am,95):.1f}/{am.max():.1f} A")
    thr=d['rcCommand[3]'][sl]; print(f"throttle rcCommand[3] med/p90 {np.median(thr):.0f}/{np.percentile(thr,90):.0f}")
    errs=[];p90=[];ov=[]
    for ax in range(3):
        sp=d[f'setpoint[{ax}]'][sl]; g=d[f'gyroADC[{ax}]'][sl]; e=np.abs(sp-g)
        errs.append(np.median(e)); p90.append(np.percentile(e,90))
        big=np.abs(sp)>150; ovs=(np.sign(g)==np.sign(sp))&(np.abs(g)>1.2*np.abs(sp))
        ov.append(100*(ovs&big).sum()/max(big.sum(),1))
    print(f"err median R/P/Y {errs[0]:.0f}/{errs[1]:.0f}/{errs[2]:.0f}  p90 {p90[0]:.0f}/{p90[1]:.0f}/{p90[2]:.0f}  overshoot {ov[0]:.0f}/{ov[1]:.0f}/{ov[2]:.0f} %")
    mot=[d[f'motor[{k}]'][sl] for k in range(4)]; M=np.array(mot)
    rail=(M>=2047).any(axis=0).mean()*100
    lines=[line(m,fs) for m in mot]; mean=np.mean([m.mean() for m in mot])
    rmsrel=np.mean([l[1] for l in lines])/mean*100
    print(f"motor mean {mean:.0f} rail frames {rail:.1f}%  motor line f {np.median([l[0] for l in lines]):.1f} Hz  line RMS/motor {rmsrel:.2f} %  motor p99 {np.percentile(M,99):.0f}")
    ey=d['setpoint[2]'][sl]-d['gyroADC[2]'][sl]; fy,ry,py=line(ey,fs); print(f"yaw-err line {fy:.1f} Hz prom {py:.0f}")
    # z3 & b0 scale
    z3s=float(h.get('adrc_z3_log_scale',1))
    for ax,k in ((0,2),(1,5),(2,6)):
        z=d[f'debug[{k}]'][sl]*z3s
        print(f"  z3[{ax}] med {np.median(z):.0f} p95|.| {np.percentile(np.abs(z),95):.0f} max|.| {np.abs(z).max():.0f} clip {np.mean(np.abs(d[f'debug[{k}]'][sl])>=32767)*100:.2f}%")
    b0s=d['debug[7]'][sl]/100
    print(f"  b0 thr-scale med {np.median(b0s):.2f} p90 {np.percentile(b0s,90):.2f} max {b0s.max():.2f} at-cap {np.mean(b0s>=float(h.get('adrc_b0_scale_max',3))-0.01)*100:.1f}%")
    # gyro peaks / 5s windows line
    g=np.abs(np.array([d[f'gyroADC[{a}]'][sl] for a in range(3)])); print(f"  gyro |max| R/P/Y {g[0].max():.0f}/{g[1].max():.0f}/{g[2].max():.0f}")
    # windowed motor line
    n=int(5*fs); w=[]
    for s in range(0,len(mot[0])-n,n):
        w.append(np.mean([line(m[s:s+n],fs)[1] for m in mot])/mean*100)
    if w: print(f"  5s-window line RMS %: min {min(w):.1f} med {np.median(w):.1f} max {max(w):.1f}")

import sys, numpy as np
sys.path.insert(0,'/tmp/claude-1000/-home-danik-Projects-and-coding-ADRC-betaflight/4b7a05a3-6ed4-4954-bc29-5b6c73d686d9/scratchpad')
from an import load, headers, liftmask, line
print(f"{'log':34s} TL  dyn  span  thr<25%: err R/P  line%  |  25-50%: err  line%  |  >50%: err line%  | rail% vbat_min  gyro|max|")
for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv')); t=d['time']*1e-6; fs=1/np.median(np.diff(t))
    i0=np.argmax(liftmask(d)); thr=(d['rcCommand[3]']-1000)/10
    mot=[d[f'motor[{k}]'] for k in range(4)]; n=int(2*fs)
    bins={'lo':[], 'mid':[], 'hi':[]}
    for s in range(i0,len(t)-n,n):
        tp=np.median(thr[s:s+n]); key='lo' if tp<25 else ('mid' if tp<50 else 'hi')
        m=np.mean([mm[s:s+n].mean() for mm in mot]); r=np.mean([line(mm[s:s+n],fs)[1] for mm in mot])/m*100
        e=[np.median(np.abs(d[f'setpoint[{a}]'][s:s+n]-d[f'gyroADC[{a}]'][s:s+n])) for a in range(2)]
        bins[key].append((e[0],e[1],r))
    def f(b):
        if not b: return "   -/-    -  "
        a=np.array(b); return f"{np.median(a[:,0]):4.0f}/{np.median(a[:,1]):<3.0f} {np.median(a[:,2]):5.2f} (n={len(b)})"
    M=np.array(mot)[:,i0:]; rail=(M>=2047).any(axis=0).mean()*100
    g=max(np.abs(d[f'gyroADC[{a}]'][i0:]).max() for a in range(3))
    name=bbl.split('__')[-1].replace('_btfl','').replace('.bbl','')
    print(f"{name:34s} {h.get('thrust_linear','?'):>3s} {h.get('dyn_idle_min_rpm','?'):>3s} {t[-1]-t[i0]:5.0f}  {f(bins['lo'])} | {f(bins['mid'])} | {f(bins['hi'])} | {rail:4.1f} {d['vbatLatest'][i0:].min():5.2f} {g:5.0f}")

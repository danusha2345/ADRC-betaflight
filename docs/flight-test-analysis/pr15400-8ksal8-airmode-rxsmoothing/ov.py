import sys, numpy as np
sys.path.insert(0,'/tmp/claude-1000/-home-danik-Projects-and-coding-ADRC-betaflight/4b7a05a3-6ed4-4954-bc29-5b6c73d686d9/scratchpad')
from an import load, headers, liftmask
print(f"{'log':22s} {'b0 R/P':13s} vbat_med | per axis R,P: active%  |sp|p90  moves  peakratio_med  peakratio_p75  err_act/|sp|")
for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv')); t=d['time']*1e-6; fs=1/np.median(np.diff(t)); i0=np.argmax(liftmask(d))
    out=[]
    for a in range(2):
        sp=d[f'setpoint[{a}]'][i0:]; g=d[f'gyroADC[{a}]'][i0:]
        act=np.abs(sp)>150
        # moves: contiguous |sp|>200 segments >= 60 ms; peak ratio = max|gyro| in seg+150ms / max|sp| in seg (same sign)
        m=np.abs(sp)>200; idx=np.where(m)[0]; segs=[]
        if len(idx):
            s0=idx[0]; prev=idx[0]
            for i in idx[1:]:
                if i-prev>fs*0.1: segs.append((s0,prev)); s0=i
                prev=i
            segs.append((s0,prev))
        ratios=[]
        for s0,s1 in segs:
            if s1-s0<fs*0.06: continue
            sgn=np.sign(sp[s0:s1+1].mean()); spk=np.abs(sp[s0:s1+1]).max()
            e=min(len(g), s1+int(0.15*fs)); gpk=(sgn*g[s0:e]).max()
            ratios.append(gpk/spk)
        r=np.array(ratios) if ratios else np.array([np.nan])
        ea=np.median(np.abs(sp[act]-g[act]))/np.median(np.abs(sp[act])) if act.any() else np.nan
        out.append(f"{act.mean()*100:4.1f}% {np.percentile(np.abs(sp),90):4.0f} {len(ratios):3d} {np.nanmedian(r):.2f} {np.nanpercentile(r,75):.2f} {ea:.3f}")
    b0=h['adrcB0'].split(',')[:2]
    print(f"{bbl.split('__')[-1].replace('_btfl','').replace('.bbl',''):22s} {'/'.join(b0):13s} {np.median(d['vbatLatest'][i0:]):5.2f} | R: {out[0]} | P: {out[1]}")

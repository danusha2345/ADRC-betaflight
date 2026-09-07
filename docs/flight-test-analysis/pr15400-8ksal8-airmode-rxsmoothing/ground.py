import sys, numpy as np
sys.path.insert(0,'/tmp/claude-1000/-home-danik-Projects-and-coding-ADRC-betaflight/4b7a05a3-6ed4-4954-bc29-5b6c73d686d9/scratchpad')
from an import load, headers
from scipy.signal import welch
for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv')); t=d['time']*1e-6; fs=1/np.median(np.diff(t))
    has=('adrcState' in d)
    st=d['adrcState'].astype(int) if has else np.zeros(len(t),int)
    lift=(st&1)>0
    arm=(d['flightModeFlags'].astype(int)&1)>0 if 'flightModeFlags' in d else np.ones(len(t),bool)
    g=np.array([d[f'gyroADC[{a}]'] for a in range(3)]); ga=np.abs(g).max(axis=0)
    mot=np.array([d[f'motor[{k}]'] for k in range(4)]); mm=mot.mean(axis=0)
    thr=d['rcCommand[3]']
    print(f"\n### {bbl.split('/')[-1]}  gwc={h.get('adrc_ground_wc','-')} wc/wo {h.get('adrcWC')}/{h.get('adrcWO')} span {t[-1]-t[0]:.1f}s fs {fs:.0f}")
    # arm epochs: contiguous armed segments
    ai=np.where(np.diff(arm.astype(int))!=0)[0]+1; bounds=[0]+list(ai)+[len(t)]
    n=0
    for s,e in zip(bounds[:-1],bounds[1:]):
        if not arm[s]: continue
        n+=1; seg=slice(s,e)
        gnd=~lift[seg]
        gnd_s=gnd.sum()/fs; gate_t=(np.argmax(lift[seg])/fs) if lift[seg].any() else None
        # oscillation bursts on ground: |gyro|>30 while gate closed
        act=(ga[seg]>30)&gnd
        # bursts
        idx=np.where(act)[0]; bursts=[]
        if len(idx):
            b0=idx[0]; prev=idx[0]
            for i in idx[1:]:
                if i-prev>fs*0.3: bursts.append((b0,prev)); b0=i
                prev=i
            bursts.append((b0,prev))
        desc=[]
        for b0,b1 in bursts:
            if (b1-b0)<fs*0.05: continue
            x=g[:,s+b0:s+b1+1]; ax=np.argmax(np.abs(x).max(axis=1)); xx=x[ax]
            if len(xx)>=int(fs*0.25):
                f,P=welch(xx-xx.mean(),fs=fs,nperseg=min(len(xx),int(fs*0.5))); fp=f[np.argmax(P[1:])+1]
            else: fp=float('nan')
            desc.append(f"[{b0/fs:.1f}s dur {(b1-b0)/fs:.2f}s ax{ax} pk {np.abs(xx).max():.0f}°/s f{fp:.0f}Hz]")
        print(f" arm{n}: {(e-s)/fs:.1f}s, ground {gnd_s:.1f}s, gate opens at {gate_t if gate_t is None else round(gate_t,2)}s, thr max on ground {(thr[seg][gnd].max() if gnd.any() else 0):.0f}, motor mean on ground {(mm[seg][gnd].mean() if gnd.any() else 0):.0f} max {(mm[seg][gnd].max() if gnd.any() else 0):.0f}, applied max {(d['adrcAppliedCollective'][seg][gnd].max() if has and gnd.any() else 0):.0f}")
        if desc: print("   ground bursts:", " ".join(desc[:12]), "..." if len(desc)>12 else "")

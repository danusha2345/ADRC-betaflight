import sys, os, numpy as np
TOP=float(os.environ.get("TOP","2040")); LOW=float(os.environ.get("LOW","350"))
for f in sys.argv[1:]:
    hdr=[c.strip() for c in open(f).readline().strip().split(',')]
    a=np.genfromtxt(f,delimiter=',',skip_header=1,usecols=range(len(hdr)),filling_values=0,invalid_raise=False)
    c=lambda k:a[:,hdr.index(k)]
    t=(c('time (us)')-c('time (us)')[0])/1e6
    m=np.stack([c(f'motor[{i}]') for i in range(4)],1); I=np.stack([c(f'axisI[{i}]') for i in range(3)],1)
    g=np.stack([c(f'gyroADC[{i}]') for i in range(3)],1); sp=np.stack([c(f'setpoint[{i}]') for i in range(3)],1)
    err=np.abs(g-sp); lift=(c('adrcState').astype(int)&1)>0; vb=c('vbatLatest (V)'); thr=c('rcCommand[3]')
    mx=m.max(1); flat=np.zeros_like(mx,bool); flat[1:-1]=(np.abs(np.diff(mx)[:-1])<=3)&(np.abs(np.diff(mx)[1:])<=3); top=((mx>=TOP)|((mx>=1900)&flat))&lift; low=(m.min(1)<=LOW)&lift; both=top&low
    def episodes(mask,minlen):
        out=[];i=0;n=len(mask)
        while i<n:
            if mask[i]:
                j=i
                while j<n and mask[j]: j+=1
                if j-i>=minlen: out.append((i,j))
                i=j
            else: i+=1
        return out
    def rep(name,eps):
        print(f"  {name}: {len(eps)} episodes")
        for i,j in eps:
            k=min(j+300,len(t)-1); e=err[i:k]; kk=np.argmax(e[:,:2].max(1))+i
            rec=next((q for q in range(kk,min(kk+2000,len(t)-100)) if (err[q:q+100,:2].max()<100)),None); rt=(t[rec]-t[i]) if rec else -1
            print(f"    rec={rt:.2f}s t={t[i]:.2f} dur={t[j-1]-t[i]:.2f}s |I| {np.abs(I[i]).round()}->{np.abs(I[i:k]).max(0).round()} maxErrRP(dur+300ms)={e[:,:2].max():.0f}@{t[kk]:.2f} maxErrYaw={e[:,2].max():.0f} vbat={vb[i:j].mean():.2f} thr={thr[i]:.0f}")
    print(f.split('/')[-1])
    rep("both-end>=30ms",episodes(both,30))
    ep=[(i,j) for i,j in episodes(top,30) if not both[i:j].any()]
    # top-only episodes: only summarize max error
    if ep:
        mx=[err[i:min(j+300,len(t)-1),:2].max() for i,j in ep]
        print(f"  top-only>=30ms (no both-end inside): {len(ep)} episodes, maxErrRP(dur+300) max={max(mx):.0f}, >350: {sum(x>350 for x in mx)}")
    epl=[(i,j) for i,j in episodes(low,30) if not both[i:j].any()]
    if epl:
        mx=[err[i:min(j+300,len(t)-1),:2].max() for i,j in epl]
        print(f"  low-only>=30ms: {len(epl)} episodes, maxErrRP max={max(mx):.0f}, >350: {sum(x>350 for x in mx)}")

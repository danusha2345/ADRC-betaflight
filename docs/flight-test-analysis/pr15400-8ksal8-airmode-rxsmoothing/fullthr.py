import sys,numpy as np
for f in sys.argv[1:]:
    hdr=[c.strip() for c in open(f).readline().strip().split(',')]
    need=['time (us)','adrcState','rcCommand[3]','vbatLatest (V)']+[f'axisI[{i}]' for i in range(3)]+[f'motor[{i}]' for i in range(4)]+[f'gyroADC[{i}]' for i in range(3)]+[f'setpoint[{i}]' for i in range(3)]
    a=np.genfromtxt(f,delimiter=',',skip_header=1,usecols=[hdr.index(n) for n in need],filling_values=0,invalid_raise=False)
    t=(a[:,0]-a[0,0])/1e6; st=a[:,1].astype(int); inh=(st&28)>0; thr=a[:,2]; vb=a[:,3]; I=a[:,4:7]; m=a[:,7:11]; err=np.abs(a[:,11:14]-a[:,14:17])
    dt=np.median(np.diff(t)); full=thr>=1950
    print(f.split('/')[-1]); i=0; rows=[]
    while i<len(t):
        if full[i]:
            j=i
            while j<len(t) and full[j]: j+=1
            if t[j-1]-t[i]>=0.4:
                e=err[i:j]; rows.append((t[i],t[j-1]-t[i],vb[i:j].mean(),vb[i:j].min(),np.percentile(e[:,:2].max(1),50),np.percentile(e[:,:2].max(1),99),e[:,:2].max(),e[:,2].max(),inh[i:j].mean()*100,np.abs(I[i:j]).max(0),(m[i:j].max(1)>=2040).mean()*100,(m[i:j].min(1)<=350).mean()*100))
            i=j
        else: i+=1
    print("  t0     dur  vbat(mean/min)  rpErr p50/p99/max  yawMax  inhibit%  max|I|            top%  floor%")
    for r in rows: print(f"  {r[0]:6.1f} {r[1]:4.1f}  {r[2]:.2f}/{r[3]:.2f}     {r[4]:4.0f}/{r[5]:4.0f}/{r[6]:5.0f}   {r[7]:5.0f}   {r[8]:5.1f}   {r[9].round()}  {r[10]:4.0f} {r[11]:4.0f}")
    tot=sum(r[1] for r in rows); print(f"  segments={len(rows)} total={tot:.1f}s")

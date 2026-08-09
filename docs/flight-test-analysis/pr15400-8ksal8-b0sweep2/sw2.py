import csv,math,cmath,glob
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
def peak(v,fs,lo=5,hi=200):
    v=[q-sum(v)/len(v) for q in v]; N=len(v)
    w=[0.5-0.5*math.cos(2*math.pi*n/(N-1)) for n in range(N)]; cg=sum(w)/N
    best=(0,0); f=float(lo)
    while f<hi:
        a=abs(sum(v[n]*w[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N)))/N/cg
        if a>best[0]: best=(a,f)
        f+=1.0
    return best
for f in sorted(glob.glob('*.01.csv')):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                rows.append((int(row[ix['time (us)']])/1e6, float(row[ix['gyroUnfilt[2]']]),
                    float(row[ix['setpoint[2]']]), float(row[ix['rcCommand[3]']]),
                    float(row[ix['gyroUnfilt[0]']])))
            except Exception: pass
    fs=(len(rows)-1)/(rows[-1][0]-rows[0][0])
    # спокойное окно 1 с: стик по yaw ~0, газ в полёте
    best=None
    for i in range(0,len(rows)-int(fs),int(fs/4)):
        w=rows[i:i+int(fs)]
        if max(abs(x[2]) for x in w)<40 and min(x[3] for x in w)>1200:
            e=rms([x[1] for x in w])
            if best is None or e>best[0]: best=(e,w)
    if not best: print(f'{f[:10]}: спокойных окон нет'); continue
    a,fq=peak([x[1] for x in best[1]], fs)
    ar,fr=peak([x[4] for x in best[1]], fs)
    print(f'{f[:10]:11s} худшее спок. окно: СКО yaw {best[0]:5.1f} °/с | пик yaw {fq:3.0f} Гц (ампл {a:5.1f}) | пик roll {fr:3.0f} Гц (ампл {ar:5.1f})')

import csv, math, cmath
MIX=[(-1,+1,-1),(-1,-1,+1),(+1,+1,+1),(+1,-1,-1)]
MLOW=158.0; MRANGE=2047.0-158.0
def load(f):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                    gu=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)]))
            except Exception: pass
    for x in rows:
        mn=[(v-MLOW)/MRANGE for v in x['m']]
        x['ax']=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]
    return rows
def spec(v, fs, fmax=200):
    v=[q-sum(v)/len(v) for q in v]; N=len(v); out=[]
    f=2.0
    while f<min(fmax,fs/2):
        s=sum(v[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N)); out.append((f,abs(s)/N)); f+=1.0
    return out
names=['roll','pitch','yaw']
for f,lbl in [('btfl_002.01.csv','PID, 2.81 с'),('btfl_001.01.csv','PID, 0.08 с'),('btfl_003.01.csv','ADRC, 0.21 с')]:
    rows=load(f)
    if len(rows)<20: print(f'{f}: слишком короткий ({len(rows)})'); continue
    dur=rows[-1]['t']-rows[0]['t']; fs=(len(rows)-1)/dur
    print(f'##### {f} — {lbl}   fs={fs:.0f} Гц')
    for a in range(3):
        sg=spec([x['gu'][a] for x in rows], fs)
        sc=spec([x['ax'][a] for x in rows], fs)
        pg=max(sg,key=lambda q:q[1]); pc=max(sc,key=lambda q:q[1])
        # энергия гироскопа в полосе 28-40 Гц
        band=[v for fq,v in sg if 28<=fq<=40]
        e34=max(band) if band else 0
        print(f'  {names[a]:6s}: гиро пик {pg[0]:5.0f} Гц ({pg[1]:6.2f} °/с) | в полосе 28-40 Гц {e34:6.2f} °/с | команда пик {pc[0]:5.0f} Гц ({pc[1]:.3f})')
    print()

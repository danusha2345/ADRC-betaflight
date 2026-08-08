import csv, math, cmath
MIX=[(-1,+1,-1),(-1,-1,+1),(+1,+1,+1),(+1,-1,-1)]  # roll,pitch,yaw для m0..m3 (BF QUAD X)
MLOW=158.0; MRANGE=2047.0-158.0
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                g=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)]))
        except Exception: pass
t0=rows[0]['t']; dur=rows[-1]['t']-t0; fs=(len(rows)-1)/dur
for x in rows:
    mn=[(v-MLOW)/MRANGE for v in x['m']]
    x['ax']=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]
names=['roll','pitch','yaw']; lim=[0.5,0.5,0.4]
print(f'выборка {fs:.0f} Гц, окно {dur:.3f} с ({len(rows)} кадров) → разрешение по частоте {1/dur:.0f} Гц, Найквист {fs/2:.0f} Гц\n')
print('команда по осям микшера (доли; pidsum_limit = 0.500 RP / 0.400 yaw):')
for a in range(3):
    v=[x['ax'][a] for x in rows]
    atlim=sum(1 for q in v if abs(q)>=lim[a]*0.98)
    print(f'  {names[a]:6s}: {min(v):+.3f}..{max(v):+.3f}  СКО {(sum(q*q for q in v)/len(v))**0.5:.3f}  кадров на лимите {atlim} ({atlim/len(v)*100:.0f}%)')
print()
def dft_peak(v, fs, fmax):
    v=[q-sum(v)/len(v) for q in v]; N=len(v); best=[]
    f=2.0
    while f<fmax:
        s=sum(v[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N))
        best.append((abs(s)/N, f)); f+=1.0
    best.sort(reverse=True); return best[:3]
print('спектральный пик (DFT, окно короткое — оценка грубая):')
for a in range(3):
    for src,lbl in [([x['ax'][a] for x in rows],'команда'),([x['g'][a] for x in rows],'гироскоп')]:
        p=dft_peak(src, fs, fs/2)
        print(f'  {names[a]:6s} {lbl:8s}: пики {", ".join(f"{f:.0f} Гц (ампл {m:.3f})" for m,f in p)}')
print()
print(f'наблюдатель: wo = 100 рад/с = {100/(2*math.pi):.1f} Гц (yaw 80 = {80/(2*math.pi):.1f} Гц)')
print(f'контроллер:  wc = 60 рад/с = {60/(2*math.pi):.1f} Гц')

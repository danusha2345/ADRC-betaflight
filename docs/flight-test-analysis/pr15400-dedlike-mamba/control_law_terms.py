import csv, math, cmath
MIX=[(-1,+1,-1),(-1,-1,+1),(+1,+1,+1),(+1,-1,-1)]
MLOW=158.0; MRANGE=2047.0-158.0
WC=[60,60,60]; B0=[2000.0,2000.0,2000.0]
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                g=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)],
                gu=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                sp=[float(row[ix[f'setpoint[{k}]']]) for k in range(3)],
                aP=[float(row[ix[f'axisP[{k}]']]) for k in range(3)],
                aD=[float(row[ix[f'axisD[{k}]']]) for k in range(2)],
                d=[float(row[ix[f'debug[{k}]']]) for k in range(8)]))
        except Exception: pass
t0=rows[0]['t']; dur=rows[-1]['t']-t0; fs=(len(rows)-1)/dur
for x in rows:
    mn=[(v-MLOW)/MRANGE for v in x['m']]
    x['ax']=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]
names=['roll','pitch','yaw']
print('уставка (setpoint, °/с):')
for a in range(3):
    v=[x['sp'][a] for x in rows]; print(f'  {names[a]:6s}: {min(v):+.1f}..{max(v):+.1f}')
print()
print('слагаемые ADRC покадрово (roll/pitch — z1,z2 логируются; сравнение с фактической командой):')
for a,(i1,i2) in enumerate([(0,1),(3,4)]):
    P=[WC[a]**2*(x['sp'][a]-x['d'][i1])/B0[a]/1000.0 for x in rows]
    D=[-2*WC[a]*x['d'][i2]/B0[a]/1000.0 for x in rows]
    S=[P[i]+D[i] for i in range(len(rows))]
    act=[x['ax'][a] for x in rows]
    err=[abs(S[i]-act[i]) for i in range(len(rows))]
    rmsP=(sum(q*q for q in P)/len(P))**0.5; rmsD=(sum(q*q for q in D)/len(D))**0.5
    print(f'  {names[a]}:  СКО P-члена {rmsP:.4f}   СКО D-члена {rmsD:.4f}   отношение D/P = {rmsD/max(rmsP,1e-9):.1f}')
    print(f'          P+D vs факт: медиана расхождения {sorted(err)[len(err)//2]:.4f} (проверка модели)')
print()
print('сравнение с логируемыми P/D классического слоя (axisP/axisD пишутся и при ADRC):')
for a in range(2):
    p=[x['aP'][a] for x in rows]; d=[x['aD'][a] for x in rows]
    print(f'  {names[a]}: axisP {min(p):+.0f}..{max(p):+.0f}   axisD {min(d):+.0f}..{max(d):+.0f}')
print()
def peak(v):
    v=[q-sum(v)/len(v) for q in v]; N=len(v); b=[]
    f=2.0
    while f<fs/2:
        s=sum(v[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N)); b.append((abs(s)/N,f)); f+=1.0
    b.sort(reverse=True); return b[0]
print('где рождается 34 Гц — гироскоп до и после фильтров (yaw):')
for lbl,key in [('gyroUnfilt','gu'),('gyroADC (после фильтров)','g')]:
    m,f=peak([x[key][2] for x in rows]); print(f'  {lbl:26s}: пик {f:.0f} Гц, амплитуда {m:.1f} °/с')
m,f=peak([x['ax'][2] for x in rows]); print(f'  {"команда yaw":26s}: пик {f:.0f} Гц, амплитуда {m:.3f}')

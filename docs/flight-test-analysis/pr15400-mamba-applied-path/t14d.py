import csv
MLOW=158.0; MHIGH=2047.0; FR=MHIGH-MLOW; VFULL=420.0; VWARN=350.0; CELLS=6
def load(f):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                    c=max(0.0,(float(row[ix['rcCommand[3]']])-1000)/10),
                    g=max(abs(float(row[ix[f'gyroADC[{k}]']])) for k in range(3)),
                    d7=float(row[ix['debug[7]']]), vb=float(row[ix['vbatLatest (V)']]),
                    D=[float(row[ix[f'axisD[{k}]']]) for k in range(3)],
                    P=[float(row[ix[f'axisP[{k}]']]) for k in range(3)],
                    z3=max(abs(float(row[ix[f'debug[{k}]']])) for k in (2,5,6))))
            except Exception: pass
    sag=rows[0]['vb']; a=1-2.718**(-0.0005/0.5)
    for x in rows:
        sag+=a*(x['vb']-sag)
        good=1.0-max(0.0,min(1.0,(VFULL-sag/CELLS*100)/(VFULL-VWARN)))
        x['a']=(sum(x['m'])/4-MLOW)/((MHIGH-((VFULL-VWARN)/VFULL)*good*FR)-MLOW)*100
    return rows
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
print('=== сессия 02 — почему НЕ открылся (негативный контроль)')
r=load('test14.02.csv'); t0=r[0]['t']
hi=[x for x in r if x['a']>=10]
print(f'   кадров applied>=10%: {len(hi)}  из них со стиком >= пола 5%: {sum(1 for x in hi if x["c"]>=5)}')
print(f'   стик за всю сессию: {min(x["c"] for x in r):.2f}..{max(x["c"] for x in r):.2f}%  → interlock держал ветвь закрытой')
print(f'   max |z3|: {max(x["z3"] for x in r):.0f}')
print()
print('=== новое поле axisD[2]: есть ли в нём данные')
for f in ['test14.01.csv','test14.03.csv']:
    r=load(f)
    print(f'   {f}: axisD[2] диапазон {min(x["D"][2] for x in r):+.0f}..{max(x["D"][2] for x in r):+.0f}  СКО {rms([x["D"][2] for x in r]):.1f} | axisP[2] СКО {rms([x["P"][2] for x in r]):.1f}')
    nz=sum(1 for x in r if x['D'][2]!=0)
    print(f'      ненулевых кадров: {nz}/{len(r)} ({nz/len(r)*100:.0f}%)   D/P по СКО = {rms([x["D"][2] for x in r])/max(rms([x["P"][2] for x in r]),1e-9):.2f}')
print()
print('=== z3 до открытия гейта (проверка z3-фикса ещё раз)')
for f in ['test14.01.csv','test14.03.csv','test14.04.csv']:
    r=load(f); oi=next(i for i,x in enumerate(r) if x['d7']>0)
    print(f'   {f}: max |z3| до гейта = {max(x["z3"] for x in r[:oi]):.0f}   (кадров {oi})')

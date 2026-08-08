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
                    thr=float(row[ix['rcCommand[3]']]),
                    g=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)],
                    gu=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)]))
            except Exception: pass
    for x in rows:
        mn=[(v-MLOW)/MRANGE for v in x['m']]
        x['ax']=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]
    return rows
def amp(v,f,fs,hann):
    N=len(v); mu=sum(v)/N; v=[q-mu for q in v]
    if hann:
        w=[0.5-0.5*math.cos(2*math.pi*n/(N-1)) for n in range(N)]
        cg=sum(w)/N
        v=[v[n]*w[n] for n in range(N)]
    else: cg=1.0
    return abs(sum(v[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N)))/N/cg

print('=== D. чувствительность амплитуд к окну (прямоугольное vs Ханна)')
rows=load('btfl_003.01.csv'); fs=(len(rows)-1)/(rows[-1]['t']-rows[0]['t'])
for name,a,f0 in [('roll',0,23),('pitch',1,24),('yaw',2,34)]:
    for lbl,h in [('прямоуг.',False),('Ханна  ',True)]:
        ag=amp([x['g'][a] for x in rows],f0,fs,h); ac=amp([x['ax'][a] for x in rows],f0,fs,h)
        print(f'  {name:6s} {lbl}: гиро {ag:7.2f} °/с  команда {ac:.4f}  отношение {ac/ag:.5f}')
print()
print('=== E. состояние борта в btfl_001 (короткий PID-лог) — корректно ли сравнение')
for f in ['btfl_001.01.csv','btfl_002.01.csv','btfl_003.01.csv']:
    rr=load(f)
    coll=[(sum(x['m'])/4-MLOW)/MRANGE*100 for x in rr]
    spread=[(max(x['m'])-min(x['m']))/MRANGE*100 for x in rr]
    thr=[(x['thr']-1000)/10 for x in rr]
    print(f'  {f}: коллектив {min(coll):.1f}..{max(coll):.1f}%  разброс max {max(spread):.1f}pp  газ {min(thr):.1f}..{max(thr):.1f}%  кадров {len(rr)}')
print()
print('=== G. связь мгновенного гиро и команды по yaw')
print('    Результат ОПРОВЕРГАЕТ мгновенную трактовку усиления: кадры на лимите встречаются')
print('    при |гиро| от 2 до 116, а самый большой отсчёт 119 даёт всего 0.356 (не упор).')
rr=load('btfl_003.01.csv')
pairs=sorted(((abs(x['g'][2]), abs(x['ax'][2])) for x in rr), reverse=True)
print('   10 кадров с наибольшим |гиро yaw|:')
for g,c in pairs[:10]: print(f'     гиро {g:6.0f} °/с → |команда| {c:.3f}')
atlim=[x for x in rr if abs(x['ax'][2])>=0.392]
if atlim:
    gg=[abs(x['g'][2]) for x in atlim]
    print(f'   кадры на лимите (|команда|>=0.392): n={len(atlim)}, |гиро| {min(gg):.0f}..{max(gg):.0f} (медиана {sorted(gg)[len(gg)//2]:.0f})')
notlim=[abs(x['g'][2]) for x in rr if abs(x['ax'][2])<0.392]
print(f'   кадры не на лимите: |гиро| медиана {sorted(notlim)[len(notlim)//2]:.0f}, max {max(notlim):.0f}')
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
                    g=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)],
                    gu=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)]))
            except Exception: pass
    for x in rows:
        mn=[(v-MLOW)/MRANGE for v in x['m']]
        x['ax']=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]
    return rows
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
names=['roll','pitch','yaw']
print('=== устойчивые (безоконные) статистики во временной области')
for f,lbl in [('btfl_002.01.csv','PID 2.81 с'),('btfl_003.01.csv','ADRC 0.21 с')]:
    rr=load(f)
    print(f'  {lbl}:')
    for a in range(3):
        g=[x['gu'][a] for x in rr]; c=[x['ax'][a] for x in rr]
        print(f'    {names[a]:6s}: гиро СКО {rms(g):7.2f} °/с, размах {max(g)-min(g):7.1f} | команда СКО {rms(c):.4f}, размах {max(c)-min(c):.3f}')
print()
print('=== фазовый сдвиг команда↔гиро на частоте кольца')
print('    ВНИМАНИЕ: этот тест НЕ разделяет пути. Наивные ориентиры — чистый P = 180 град,')
print('    чистый D = -90 град (минус входит в сам D-член) — не применимы: LESO вносит')
print('    собственный сдвиг на этих частотах. Выведено как описание, не как доказательство.')
rr=load('btfl_003.01.csv'); fs=(len(rr)-1)/(rr[-1]['t']-rr[0]['t'])
def cf(v,f):
    N=len(v); mu=sum(v)/N
    w=[0.5-0.5*math.cos(2*math.pi*n/(N-1)) for n in range(N)]
    return sum((v[n]-mu)*w[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N))
for a,f0 in [(0,23),(1,24),(2,34)]:
    G=cf([x['gu'][a] for x in rr],f0); C=cf([x['ax'][a] for x in rr],f0)
    ph=math.degrees(cmath.phase(C/G))
    print(f'  {names[a]:6s} @ {f0} Гц: фаза команды относительно гиро {ph:+.0f}°')
import csv, math, cmath
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            rows.append(dict(t=int(row[ix['time (us)']])/1e6,
                P=[float(row[ix[f'axisP[{a}]']]) for a in range(3)],
                D=[float(row[ix[f'axisD[{a}]']]) for a in range(2)]))
        except Exception: pass
fs=(len(rows)-1)/(rows[-1]['t']-rows[0]['t'])
def a(v,f):
    N=len(v); mu=sum(v)/N
    w=[0.5-0.5*math.cos(2*math.pi*n/(N-1)) for n in range(N)]
    cg=sum(w)/N
    return abs(sum((v[n]-mu)*w[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N)))/N/cg
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
print('прямое сравнение слагаемых, логируемых бортом (axisP / axisD):')
for name,i,f0 in [('roll',0,23),('pitch',1,24)]:
    P=[x['P'][i] for x in rows]; D=[x['D'][i] for x in rows]
    print(f'  {name}:  СКО P {rms(P):6.1f}  СКО D {rms(D):6.1f}  → D/P = {rms(D)/rms(P):.1f}')
    print(f'          на {f0} Гц: |P| {a(P,f0):6.1f}   |D| {a(D,f0):6.1f}   → D/P = {a(D,f0)/a(P,f0):.1f}')
P=[x['P'][2] for x in rows]
print(f'  yaw:    СКО P {rms(P):6.1f}  (axisD по yaw блэкбокс не пишет)')
print(f'          на 34 Гц: |P| {a(P,34):6.1f}')

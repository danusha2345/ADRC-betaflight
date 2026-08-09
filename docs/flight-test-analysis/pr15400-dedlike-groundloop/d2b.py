import csv
MLOW=158.0; MRANGE=2047.0-158.0
rows=[]
with open('groundloop_btfl_all.02.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                c=float(row[ix['setpoint[3]']])/10.0,
                stick=max(0.0,(float(row[ix['rcCommand[3]']])-1000)/10),
                g=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                sp=[float(row[ix[f'setpoint[{k}]']]) for k in range(3)],
                coll=(sum(m)/4-MLOW)/MRANGE*100,
                d7=float(row[ix['debug[7]']]),
                z3=[abs(float(row[ix[f'debug[{k}]']])) for k in (2,5,6)]))
        except Exception: pass
t0=rows[0]['t']; T=lambda x:(x['t']-t0)
FLOOR=20.0  # 0.5 * adrc_liftoff_throttle(40)
def first(pred):
    x=next((y for y in rows if pred(y)), None); return T(x) if x else None
ev=[
 ('commanded пересекает idle-пол 20%', first(lambda x:x['c']>=FLOOR)),
 ('|z3| впервые >100 (лог)',           first(lambda x:max(x['z3'])>100)),
 ('|z3| упирается в 32767',            first(lambda x:max(x['z3'])>=32767)),
 ('|гиро pitch| >100 °/с',             first(lambda x:abs(x['g'][1])>100)),
 ('|гиро pitch| >500 °/с',             first(lambda x:abs(x['g'][1])>500)),
 ('первый мотор на верхнем упоре 2047', first(lambda x:max(x['m'])>=2047)),
 ('ГЕЙТ открывается',                  first(lambda x:x['d7']>0)),
 ('|гиро pitch| >1500 °/с',            first(lambda x:abs(x['g'][1])>1500)),
]
print('хронология:')
for n,t in ev: print(f'   {n:34s} {t if t is None else format(t,".3f")+" с"}')
print()
print('окна по 0.5 с:')
print('  окно      commanded  коллектив  |z3|max   гиро R/P/Y СКО      гейт')
s=0.0
while s < T(rows[-1]):
    w=[x for x in rows if s<=T(x)<s+0.5]
    if len(w)>30:
        import statistics as st
        r_=[x['g'][0] for x in w]; p_=[x['g'][1] for x in w]; y_=[x['g'][2] for x in w]
        f=lambda v:(sum((q-sum(v)/len(v))**2 for q in v)/len(v))**0.5
        print(f'  {s:4.1f}-{s+0.5:4.1f}   {max(x["c"] for x in w):6.1f}%  {max(x["coll"] for x in w):7.1f}%  {max(max(x["z3"]) for x in w):7.0f}  {f(r_):6.0f}/{f(p_):6.0f}/{f(y_):6.0f}   {"ОТКР" if any(x["d7"]>0 for x in w) else "закр"}')
    s+=0.5

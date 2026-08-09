import csv
MLOW=158.0; MRANGE=2047.0-158.0
rows=[]
with open('btfl_all.02.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                c=float(row[ix['setpoint[3]']])/10.0,
                g=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                coll=(sum(m)/4-MLOW)/MRANGE*100,
                d7=float(row[ix['debug[7]']]),
                z3=max(abs(float(row[ix[f'debug[{k}]']])) for k in (2,5,6))))
        except Exception: pass
t0=rows[0]['t']; T=lambda x:(x['t']-t0)
print('фаза ДО первого движения газа (commanded == 0):')
# непрерывный префикс ДО первого положительного commanded collective,
# а не все кадры с нулевым газом (те включают возврат к нулю уже после
# открытия гейта и дают ложные ненулевой z3 и открытый гейт)
first_gas=next((i for i,x in enumerate(rows) if x['c']>0.05), len(rows))
pre=rows[:first_gas]
print(f'  кадров: {len(pre)}, до t={max(T(x) for x in pre):.3f}с')
print(f'  коллектив max: {max(x["coll"] for x in pre):.1f} %   (стик всё это время на нуле)')
print(f'  |z3| max:      {max(x["z3"] for x in pre):.0f}')
print(f'  гейт открыт в этой фазе: {"да" if any(x["d7"]>0 for x in pre) else "НЕТ"}')
sat=[x for x in pre if max(x['m'])>=2040]
print(f'  кадров с мотором на упоре: {len(sat)}, первый в t={T(sat[0]):.3f}с' if sat else '  моторов на упоре нет')
print(f'  |гиро| max R/P/Y: {max(abs(x["g"][0]) for x in pre):.0f} / {max(abs(x["g"][1]) for x in pre):.0f} / {max(abs(x["g"][2]) for x in pre):.0f}')
print()
print('покадрово вокруг начала (шаг ~50 мс):')
print('   t       cmd    колл   |z3|   гиро R/P/Y            моторы            гейт')
for x in rows[::50]:
    if 4.4 <= T(x) <= 6.1:
        print(f'  {T(x):5.3f}  {x["c"]:5.1f}% {x["coll"]:6.1f}% {x["z3"]:6.0f}  {x["g"][0]:6.0f}/{x["g"][1]:6.0f}/{x["g"][2]:6.0f}  {[int(v) for v in x["m"]]}  {"ОТКР" if x["d7"]>0 else "закр"}')

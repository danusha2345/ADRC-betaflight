import csv, math, cmath
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            rows.append(dict(t=int(row[ix['time (us)']])/1e6,
                g=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)],
                d=[float(row[ix[f'debug[{k}]']]) for k in range(8)]))
        except Exception: pass
dur=rows[-1]['t']-rows[0]['t']; fs=(len(rows)-1)/dur
def amp(v,f):
    v=[q-sum(v)/len(v) for q in v]; N=len(v)
    return abs(sum(v[n]*cmath.exp(-2j*math.pi*f*n/fs) for n in range(N)))/N
print('проверка модели наблюдателя: при частоте много выше wo должно быть |z2|/|gyro| ≈ 3·wo²/ω\n')
for a,(ig,i1,i2,wo,wc,f0) in enumerate([('roll',0,1,100,60,23),('pitch',1,4,100,60,24)]):
    pass
for name,ig,i1,i2,wo,wc,f0 in [('roll',0,0,1,100,60,23),('pitch',1,3,4,100,60,24)]:
    w=2*math.pi*f0
    ag=amp([x['g'][ig] for x in rows],f0)
    a1=amp([x['d'][i1] for x in rows],f0)
    a2=amp([x['d'][i2] for x in rows],f0)
    pred=3*wo*wo/w
    print(f'{name} на {f0} Гц (ω={w:.0f} рад/с, wo={wo}):')
    print(f'   |гиро| {ag:8.2f} °/с   |z1| {a1:8.2f}   |z2| {a2:9.1f}')
    print(f'   z1/гиро = {a1/ag:5.2f}  (при ω>>wo наблюдатель перестаёт отслеживать → должно быть <1)')
    print(f'   z2/гиро = {a2/ag:7.1f}   предсказание 3·wo²/ω = {pred:7.1f}   расхождение {abs(a2/ag-pred)/pred*100:.0f}%')
    kd=2*wc; b0=2000.0
    gain=kd*(a2/ag)/b0/1000.0
    print(f'   → усиление D-пути гиро→команда = 2·wc·(z2/гиро)/b0/1000 = {gain:.5f} на °/с')
    print(f'     при амплитуде гиро {ag:.1f} °/с даёт команду {gain*ag:.3f} (лимит 0.500)\n')
# yaw: z1/z2 не логируются, оцениваем по формуле
w=2*math.pi*34; wo=80; wc=60
gain=2*wc*(3*wo*wo/w)/2000.0/1000.0
ag=amp([x['g'][2] for x in rows],34)
print(f'yaw на 34 Гц (wo=80): z1/z2 не логируются, по формуле усиление {gain:.5f} на °/с')
print(f'   при |гиро| {ag:.1f} °/с → предсказанная команда {gain*ag:.3f}; измеренная 0.150; лимит yaw 0.400')

# Adversarial review: test14

Дата проверки: 2026-08-09.

## Итог

**Общий вердикт: NO-GO в текущей формулировке.** Главное наблюдение при этом
не развалилось: три открытия действительно лучше всего и практически
однозначно объясняются applied-collective path. Но опубликованный способ
доказательства содержит три ошибки:

1. `getBatterySagCellVoltage()` — не PT1 с `tau ≈ 0.5 s`, а отдельный 5 Hz PT1,
   обновляемый задачей 200 Hz (`tau = 31.83 ms` при default
   `vbat_sag_lpf_period = 2`).
2. Gate сравнивает не throttle stick, а final commanded collective. В этом логе
   его можно читать как `setpoint[3]/1000`; `rcCommand[3]` — не тот сигнал.
3. Blackbox сохраняет каждый второй PID frame. Поэтому «250 ms кадр в кадр» и
   непрерывность на каждом PID loop непосредственно из CSV не доказаны.

После правильной sag-реконструкции applied в кадрах открытия равен **10.519 %,
11.924 % и 10.539 %**. Direct-command максимум до открытия равен
**6.5 %, 7.6 %, 6.0 %**, gyro максимум — **113, 128, 125 deg/s** при пороге
255. В точном коде третьей ветви нет. Поэтому branch attribution остаётся
сильным: **gate открыл applied path**, хотя таблицу и метод нужно исправить.

| заявление | evidence verdict | публикационный verdict |
|---|---|---|
| 1. Сработал applied-collective path | **ПОДТВЕРЖДЕНО как branch attribution** | **NO-GO as written**: исправить signal names, session 03, gyro labels и sampling caveat; novelty не доказана |
| 2. Session 02 — negative control interlock | **ПОДТВЕРЖДЕНО ядро** | **NO-GO as written**: точный count 31 767 не воспроизводится, interlock использует commanded 4.4 %, а не stick 4.3 %; это проверка общего idle interlock также для gyro path |
| 3. Старая нормировка неверна | **ПОДТВЕРЖДЕНО направление, ОПРОВЕРГНУТА реализация фильтра** | **NO-GO** до замены формулы/чисел |
| 4. `axisD[2]` содержит реальные данные | **ПОДТВЕРЖДЕНО** | **GO** с объяснением quantization и несопоставимости D/P metrics |
| 5. `z3` равен нулю до gate | **ПОДТВЕРЖДЕНО кодом и логом** | **GO** после различения internal `z3` и logged `z3/16` |
| 6. Старые разборы не затронуты | **ЧАСТИЧНО** | **NO-GO в общей форме**: dedlike не затронут; test13 gate verdicts устойчивы, но его фактический cell count из headers не восстанавливается, поэтому точные 1.7 % недоказаны |

## Provenance

- `test14.bbl` SHA-256:
  `32535c3acc6438ecfd4ad9a656add4d23297ea136841254f2bddad6657cc4176`.
- `blackbox_decode` SHA-256:
  `6b35322c22d5d9e3d23dd171a9ac0424e2fb38f9b8a2232425155d47cd17d23e`.
- BBL независимо заново декодирован указанным бинарником с
  `--unit-frame-time us --save-headers`.
- Получено ровно 40 553 / 80 006 / 48 730 / 45 906 data frames. Decoder не
  потерял ни одного декодируемого frame; unreadable loops: 34 / 5 / 27 / 63.
- Все относящиеся к этому review поля свежих CSV (`time`, `loopIteration`,
  PID terms, `rcCommand[3]`, `setpoint[3]`, voltage, gyro, debug, motors)
  совпали с лежащими рядом CSV во всех строках.
- Patch branch имеет HEAD
  `31a29cf333c57ad2349e3944b3bda690e4bc5752`; commit
  `3c85c4b5ad713c9974bfbdf8d78669d67037ab1a` является его непосредственным
  предком. Header показывает ожидаемые firmware date `Aug 8 2026 15:24:42`,
  ADRC tune и присутствие `axisD[2]`.

## 1. Что на самом деле делает sag compensation

### 1.1. `getBatterySagCellVoltage()`

`CLAIMS_FOR_REVIEW.md:56-60` и `t14c.py:23-26` моделируют отдельный voltage
filter как PT1 с `tau ≈ 0.5 s`, применённый на каждом Blackbox frame. Это
неверно.

Точный code path `3c85c4b5a`:

- `src/main/sensors/battery.c:144-146` задаёт default
  `vbatSagLpfPeriod = 2`;
- `src/main/sensors/battery.h:40` преобразует period в cutoff как
  `1 / (period / 10)`, то есть **5 Hz**;
- `src/main/sensors/voltage.h:26` задаёт fast voltage task **200 Hz**;
- `src/main/fc/tasks.c:529-533` действительно переводит battery voltage task
  на 200 Hz, когда sag compensation сконфигурирован;
- `src/main/sensors/voltage.c:185-189` фильтрует raw ADC отдельным
  `state->sagFilter`;
- `src/main/sensors/voltage.c:230-232` инициализирует его как PT1 на 5 Hz с
  `dT = 1/200 s`;
- `src/main/common/filter.c:45-49` даёт
  `k = omega/(1+omega) = 0.135755`, где `omega = 2*pi*5/200`;
- `src/main/sensors/battery.c:628-630` возвращает
  `voltageMeter.sagFiltered / batteryCellCount`.

Эквивалентная time constant — **`1/(2*pi*5) = 31.831 ms`**, а не 0.5 s.
Кроме того, firmware фильтрует raw ADC до centivolt conversion, тогда как BBL
записывает уже преобразованный `vbatLatest`. Поэтому `sagFiltered` нельзя
побайтно восстановить из этого BBL; возможна только близкая реконструкция.

### 1.2. Cell count не просто «угадан из vbatref»

`CLAIMS_FOR_REVIEW.md:61-62` спрашивает, даёт ли формула 6 или 7. При auto mode
формула в `src/main/sensors/battery.c:204-211` равна

`cells = floor(displayFiltered / vbatmaxcellvoltage) + 1`.

Если подставить 2513 cV и header max 430 cV, результат **6**:
`floor(2513/430)+1 = 5+1 = 6`. Для 7 нужно как минимум 2580 cV.

Но это не главный факт. `vbatref` не является detection sample: Blackbox
запоминает в нём **unfiltered** voltage при старте лога
(`src/main/blackbox/blackbox.c:1098,1531`), а auto detect читает
`displayFiltered` при battery presence.

На этом борту auto branch вообще обходится: сохранённый config явно содержит
`set force_battery_cell_count = 6` в
`.scratch/bench/diff_before_bbfix.txt:222-226`. Код выбирает forced count раньше
auto detect (`src/main/sensors/battery.c:243-248`). Поэтому правильная
формулировка: **firmware использовал шесть банок, потому что profile принудительно
задаёт 6; auto formula при 25.13 V тоже дала бы 6**.

### 1.3. Dynamic idle сконфигурирован, но фактически не активен

Headers всех четырёх sessions содержат:

- `dyn_idle_min_rpm = 30`;
- `dshot_bidir = 0`;
- `motorOutput = 158,2047`;
- `motor_idle = 550`.

В `src/main/flight/mixer_init.c:346-351` `dynIdleMinRps` получает настроенное
значение только при `useDshotTelemetry`; иначе жёстко становится `0.0f`.
Следовательно:

- ветка dynamic-idle controller в `src/main/flight/mixer.c:251-271` не
  выполняется;
- 1 % commanded-throttle floor в `mixer.c:780-784` не применяется;
- `motorRangeMinIncrease = 0`;
- `motorRangeMin` остаётся **158**, как и было принято в расчёте.

`motor_idle = 550` уже учтён firmware при формировании header endpoint 158; это
не дополнительная прибавка к 158.

### 1.4. Что именно реконструируется из motors

Внутренний applied collective — это normalized `throttle` после lower/upper
clamp (`src/main/flight/mixer.c:681-701`), который публикуется как
`mixerAdrcThrottle` (`mixer.c:882-900`). Sag compensation не меняет эту
нормализованную величину. Оно меняет только её отображение на physical motor
endpoint:

- attenuation и `motorRangeMax` — `mixer.c:275-292`;
- mapping `motorOutputMin + motorOutputRange * motorOutput` —
  `mixer.c:481-503`.

Иными словами, речь не об «исправленном applied внутри firmware», а об
исправленном **обратном преобразовании logged motors в уже существовавший
normalized applied**.

## 2. Независимый пересчёт трёх открытий

Реконструкция выполнена с 5 Hz PT1 на сетке 200 Hz, forced six cells, integer
centivolt division, `motorRangeMin = 158` и точной формулой `mixer.c:279-292`.
Неизвестная фаза 200 Hz task была просканирована от 0 до 4.5 ms с шагом 0.5 ms;
в кадрах открытия integer cell voltage и итоговый applied от фазы не менялись.

Вторая, независимая сверка не использовала battery voltage вообще: applied
lower clamp восстановлен из logged `axisP+axisI+axisD+axisF`, QUAD X
coefficients (`src/main/flight/mixer_init.c:84-89`) и
`yaw_motors_reversed = ON` (`.scratch/bench/diff_before_bbfix.txt:68`). В
последних 250 ms обе реконструкции расходятся медианно лишь на
**0.044 / 0.052 / 0.053 процентного пункта**, p95 —
**0.124 / 0.143 / 0.152 п.п.**

| session | first positive `debug[7]` | final commanded at open | max final commanded before open | gyro at open / max before open | sag cell at open | motor range at open | applied from motors | applied from PID mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 01 | **13.436812 s** | 6.3 % | **6.5 %** | 110 / **113** | 417 cV | 1587.660 | **10.519 %** | 10.5 % |
| 03 | **7.853071 s** | 7.3 % | **7.6 %** | 128 / **128** | 412 cV | 1610.148 | **11.924 %** | 12.0 % |
| 04 | **15.395979 s** | 5.5 % | **6.0 %** | 120 / **125** | 414 cV | 1601.152 | **10.539 %** | 10.4 % |

Это опровергает два точных числа/label в `CLAIMS_FOR_REVIEW.md:17-21`:

- session 03 — **11.924 %, не 12.01 %**;
- `110/128/120` — gyro **в кадре открытия**, не maxima. Maxima до gate равны
  **113/128/125**; в самих примерно 250 ms windows — 113/128/124.

Quoted общий range `1582-1618` (`CLAIMS_FOR_REVIEW.md:40-41`) также не является
range всех sessions. С правильным фильтром full-session ranges равны:

- session 01: 1578.664–1623.640;
- session 02: 1583.162–1623.640;
- session 03: 1583.162–1650.626;
- session 04: 1592.157–1637.133.

### Какой branch открыл gate

Код содержит только три способа открыть gate
(`src/main/flight/adrc.c:426-503`):

1. direct: `commandedThrottle >= 10 %`;
2. gyro: `gyroPeak > 255 deg/s` при commanded не ниже idle floor 5 %,
   удержанный 25 ms;
3. applied: applied `>= 10 %` при commanded не ниже 5 %, удержанный 250 ms.

Для direct branch нужно сравнивать не stick, а final commanded collective.
Blackbox пишет его как `setpoint[3] = mixerGetThrottle()*1000`
(`src/main/blackbox/blackbox.c:1287-1292`). `throttle_boost = 5` активен, поэтому
эта поправка принципиальна, хотя здесь она не приблизила сигнал к 10 %.

Наблюдаемые maxima final commanded до gate — 6.5/7.6/6.0 %, gyro —
113/128/125. Они далеко от direct/gyro thresholds. В то же время обе
независимые applied-реконструкции достигают 10 %, а sign flip `debug[7]`
появляется примерно через configured hold. В точном code path другого способа
нет. **Applied branch attribution подтверждён.**

### Почему «250 ms кадр в кадр» слишком сильно

`P interval = 2`: CSV сохраняет примерно 2004 frames/s при PID rate около
4 kHz. Половина PID iterations не наблюдается. По сохранённым frames crossing
brackets таковы:

| session | previous saved below 10 % | first saved at/above 10 % | gate-open frame | first-good to open | previous-bad to open |
|---|---:|---:|---:|---:|---:|
| 01 | 13.186875 s | 13.187374 s | 13.436812 s | 249.438 ms | 249.937 ms |
| 03 | 7.602991 s | 7.603491 s | 7.853071 s | 249.580 ms | 250.080 ms |
| 04 | 15.145352 s | 15.145850 s | 15.395979 s | 250.129 ms | 250.627 ms |

Эти brackets отлично согласуются с 250 ms runtime timer и sampling delay, но
не доказывают каждый промежуточный unsaved PID loop. Публикационная
формулировка должна быть: **“the saved-frame crossing brackets and the gate
transition agree with the 250 ms applied timer”**, не “continuous frame for
frame”.

Наконец, «впервые за ~29 логов с трёх бортов» нельзя проверить по одному
предоставленному corpus test14. Для novelty claim нужен перечисленный список
этих 29 sessions и одинаковый branch classifier. Без него писать только
**“the first applied-path opening identified in our reviewed hardware logs”**.

## 3. Session 02 — negative control

Ядро верно: `debug[7]` остаётся отрицательным во всех **80 006 frames**, хотя
applied надолго и сильно превышает 10 %.

Но точное число `31 767` (`CLAIMS_FOR_REVIEW.md:30`) зависит от ошибочного
0.5 s sag filter и не воспроизводится:

- motor/sag reconstruction: **31 609–31 634 frames** в зависимости от
  неизвестной 200 Hz task phase; nominal phase даёт 31 622;
- voltage-independent PID/mixer reconstruction: **32 203 frames**.

Внутренний applied не записан непосредственно, поэтому честное число —
**около 31.6–32.2 thousand saved frames**, а не псевдоточное 31 767.

Ещё одна терминологическая ошибка: interlock читает commanded collective,
не stick. Stick максимум равен 4.3 %, но `setpoint[3]` из-за throttle processing
достигает **4.4 %**. Оба всё равно ниже floor 5 %. Ни одна reconstructed frame
с applied >=10 % не имеет commanded >=5 %.

Session 02 одновременно достигает **359 deg/s**, то есть выше gyro threshold
255. Gate всё равно не открывается, потому что тот же `throttleAtIdle` блокирует
gyro branch в `adrc.c:456`. Поэтому это хороший hardware negative control
**общего idle interlock для applied и gyro paths**, не чисто applied-only test.

Слова «первая проверка на железе» снова требуют явного corpus inventory; сам
лог доказывает поведение, но не историческую уникальность.

## 4. `axisD[2]` — поле настоящее; нули ожидаемы

Patch в
`.scratch/worktrees/b7/src/main/blackbox/blackbox.c:523-539` при ADRC включает
все три D fields по общей PID-field condition. Classic PID продолжает идти по
старой проверке legacy D gain. Header содержит `axisD[2]`, то есть condition
была истинна на всю session; per-frame zeros не могут означать условное
исчезновение поля.

`pid.c:1113-1119` присваивает `adrcOutput.D` в `pidData[axis].D`, а Blackbox
записывает `lrintf(pidData[i].D)`
(`.scratch/worktrees/b7/src/main/blackbox/blackbox.c:1266-1271`). Поэтому
непрерывное значение `|D| < 0.5` становится integer zero.

Независимо воспроизведённые stats:

| session | range `axisD[2]` | std D | std P | std ratio D/P | zero frames | median/max zero run |
|---|---:|---:|---:|---:|---:|---:|
| 01 | -26…+59 | 9.779 | 35.168 | **0.2781** | **9.585 %** | 1 / 54 frames |
| 03 | -59…+41 | 10.603 | 38.772 | **0.2735** | **19.887 %** | 3 / 84 frames |

То есть заявленные aggregate range -59…+59, std 9.8–10.6,
80–90 % nonzero и D/P 0.27–0.28 верны. Короткие zero runs вокруг crossing и
длинные runs в почти неподвижных участках — ожидаемое следствие integer
quantization, не признак broken field.

### Почему 0.27 не противоречит dedlike 2.55

Сравнение в `CLAIMS_FOR_REVIEW.md:79-81` смешивает разные metrics:

- test14 0.27 — отношение standard deviations по всей медленной ручной bench
  session;
- dedlike 2.55 — reconstructed yaw ratio **на 34 Hz ring frequency**
  (`pr15400-dedlike-mamba/ANALYSIS.md:170-197`).

Для closed-gate sinusoid при `z3=b0u=0` LESO даёт приблизительно

`|D/P| = (2*wo*omega) / (wc*sqrt(omega^2 + wo^2))`.

При test14 `wc=60, wo=180` это около **0.115 на 0.55 Hz** и **0.217 на
1.04 Hz**, что согласуется с медленным bench content. При dedlike
`wc=60, wo=80, f=34 Hz` формула даёт **2.50**, практически измеренные 2.55.
`b0` в этом отношении сокращается. Разница на порядок поэтому ожидаема и даже
служит sanity check, а не признаком ошибки patch.

Не следует публиковать test14 high-frequency D/P: в 30–38 Hz там почти нет
gyro energy, и ratio определяется noise/quantization floor.

## 5. `z3` до gate

Counts из `CLAIMS_FOR_REVIEW.md:83-86` воспроизводятся точно:

- session 01: 26 907 frames до первого positive `debug[7]`;
- session 03: 15 733;
- session 04: 30 839;
- session 02: все 80 006 frames.

Во всех них `debug[2]`, `debug[5]`, `debug[6]` равны нулю.

Но telemetry формулировка должна быть аккуратной. Код логирует
`round(z3 / 16)` (`src/main/flight/adrc.c:673-689`); один logged zero сам по
себе означает только маленький internal `z3`, а не математически точный ноль.

Точный internal zero здесь доказывает совместно code path:

- arm reset задаёт `z3=0` (`adrc.c:186-200,390-400`);
- b7 inhibit активен для всего закрытого gate
  (`inhibitZ3Growth = !liftoff`, `adrc.c:599-619`);
- из начального нуля любой nonzero growth step имеет большую magnitude и
  отбрасывается, пока gate закрыт.

Поэтому вывод **internal z3 exactly zero before gate** верен, но основание —
code plus zero telemetry, не разрешение debug field само по себе.

## 6. Dedlike и test13

### Dedlike

Fresh header `btfl_003` подтверждает:

- `vbat_sag_compensation = 0`;
- `motorOutput = 158,2047`;
- `dyn_idle_min_rpm = 0`.

Следовательно, sag attenuation там отсутствует, lower endpoint не плавает и
прежняя normalization на 158…2047 верна. **Dedlike analysis этой ошибкой не
затронут.**

### test13

Fresh headers показывают `vbat_sag_compensation = 100`, `dshot_bidir = 0` и
`vbatref = 1897/1650/1378/1277`, но **не записывают ни
`batteryCellCount`, ни `force_battery_cell_count`**. Как установлено выше,
`vbatref` — unfiltered voltage на старте Blackbox, а не доказательство
detection result. Поэтому просьбу из `CLAIMS_FOR_REVIEW.md:91-93` нельзя
закрыть одними headers так категорично, как она сформулирована.

Есть два совместимых с доступными артефактами сценария:

1. Если на первой session работал auto detect и battery не отключалась между
   sessions, `floor(1897/430)+1 = 5`, cell count оставался 5 и warning threshold
   был 17.50 V. Тогда sessions 02–04 действительно ниже warning. В session 01
   при 357 cV/cell:
   - `goodness = (357-350)/70 = 0.1`;
   - attenuation = `(70/420)*0.1 = 1/60`;
   - corrected/static ratio = `1/(1-1/60) = 1.01695`;
   - заявленные **1.695 % relative** математически верны именно в этом
     operating point.
2. Если уже был активен позднее сохранённый `force_battery_cell_count = 6`,
   все четыре sessions были ниже 350 cV/cell и sag attenuation была нулевой,
   включая session 01. Config capture
   `.scratch/bench/diff_before_bbfix.txt:222-226` доказывает force=6 на этом
   борту 2026-08-08, но файл создан после test13 и одновременно содержит уже
   изменённый liftoff threshold/tune; переносить его состояние назад на test13
   без оговорки нельзя.

Если battery физически переподключалась между sessions при auto mode, cell
count мог детектироваться заново; BBL gaps этого не разрешают. Закрывающее
измерение — contemporaneous `status`/`get force_battery_cell_count` либо прямой
Blackbox field для `batteryCellCount`/`sagFiltered`.

Тем не менее прежний **gate verdict test13 устойчив при обоих основных
сценариях**. При five-cell reconstruction maximum applied session 01 меняется
только **11.395 % static → 11.632 % corrected** и остаётся далеко ниже
liftoff threshold 18 %; gate не открылся, final commanded максимум 11.4 %, gyro
максимум 144 deg/s. При six-cell scenario correction равна нулю. Sessions 02–04
также ниже warning при retained five-cell или forced-six state. Поэтому
качественные gate conclusions не меняются, но точное утверждение «session 01
имела 1.7 % ошибки» остаётся **условным, а не доказанным headers**.

## Обязательные правки перед публикацией

1. Заменить описание sag filter на 5 Hz / 200 Hz / `tau=31.83 ms`; удалить
   `tau≈0.5 s` и per-Blackbox-frame approximation.
2. Написать, что cell count был **forced to 6**; auto formula при 25.13 V тоже
   дала бы 6, но `vbatref` не является auto-detect input.
3. Явно написать, что `dyn_idle_min_rpm=30` не активен из-за
   `dshot_bidir=0`; `motorRangeMin=158`.
4. В таблице statement 1 заменить session 03 `12.01` на **11.924**; session 01
   и 04 — **10.519/10.539**.
5. Переименовать `стик` в две колонки: stick и final commanded. Branch tests
   формулировать по `setpoint[3]`.
6. Переименовать `gyro max` 110/128/120 в `gyro at gate`; настоящие pre-gate
   maxima — 113/128/125.
7. Заменить «continuous 250 ms frame-for-frame» на saved-frame crossing
   brackets, согласующиеся с runtime timer; указать `P interval=2`.
8. Session 02: убрать точное 31 767, написать примерно 31.6–32.2k saved frames;
   commanded максимум 4.4 %, gyro максимум 359. Назвать это shared idle
   interlock control для applied и gyro paths.
9. Для `axisD[2]` оставить числа, объяснить `lrintf` zeros и не сравнивать
   whole-session std ratio 0.27 напрямую с dedlike 34 Hz ratio 2.55.
10. Для `z3` различить logged `z3/16=0` и exact internal zero, доказанный
    reset+inhibit code path.
11. Заявление 6 сузить: dedlike полностью не затронут; test13 gate verdicts
    устойчивы, но cell count не записан, поэтому 1.7 % для session 01 нужно
    назвать условным five-cell расчётом, а не измеренным фактом.
12. Исторические слова «впервые» оставить только при публикации полного списка
    просмотренных sessions и единого classifier; иначе убрать.

После этих правок statements 1, 2, 4 и 5 готовы как hardware evidence.
Statement 3 нужно переписать по реальному фильтру, statement 6 — сузить.

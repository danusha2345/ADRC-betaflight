# Adversarial review: 8ksal8 b0sweep3

Дата проверки: 2026-08-09.

## Итог

**Общий вердикт: NO-GO в текущей формулировке.** Claim 1 выдерживает
проверку. Claim 5 верен по сути, но неполон. Claim 2 годится только как
описание восьми конкретных логов, не как эффект ретюна. Claim 3 действительно
показывает выполнение дефектного b8 code path, но содержит ошибку `6/8` вместо
`5/8` и не доказывает вред в полёте. Claim 4 прямо опровергнут raw flags:
Airmode включается во всех восьми логах, а текстовый decoder скрывает этот bit.

| claim | evidence verdict | публикационный verdict |
|---|---|---|
| 1. Статическая нормировка коллектива | **ПОДТВЕРЖДЕНО** | **GO** с оговоркой про integer logging |
| 2. Ретюн улучшил yaw и ухудшил roll/pitch | Whole-log числа **ПОДТВЕРЖДЕНЫ**, причинность **НЕДОКАЗУЕМА** | **NO-GO as written**; переписать как наблюдение по этим sessions |
| 3. Воспроизведена слепая зона `z3` | Дефектный code path **ПОДТВЕРЖДЁН**, причинный flight harm **НЕ ДОКАЗАН** | **NO-GO as written**; после сужения формулировки — GO |
| 4. Airmode по логам не решается | **ОПРОВЕРГНУТО** | **NO-GO** |
| 5. Атрибуция улучшения невозможна | **ПОДТВЕРЖДЕНО**, но список изменений неполон | **GO после дополнения** |

## Provenance

- Exact firmware: `c40f1e096468be030b4a1df8c6802033ef938244`, tag
  `adrc-pr15400-b8`.
- Decoder SHA-256:
  `6b35322c22d5d9e3d23dd171a9ac0424e2fb38f9b8a2232425155d47cd17d23e`.
- BBL SHA-256:

| sweep | law | SHA-256 |
|---|---|---|
| old | FIXED | `6b267618438c478441f662cd205bddcc6fc9a5120c8381f629ea5859078f2174` |
| old | LINEAR | `db62cb77c79f6a51b4dcc54f7e3cd639052d14f859b27d388730dddcda2b6063` |
| old | QUADRATIC | `37ff5da4e89b08c1d48d54b7cf74b060ef6f19e516b8f84b566a17c249af0084` |
| old | SQRT | `fe02549496fb4a2041218c0fe5dfc5515c24c2070a1bd9c91810a14668453b38` |
| new | FIXED | `c30285f15fab1c35d4200d1ac70846e32236d0eb61d2c35d97775c9e7a29424c` |
| new | LINEAR | `aa9748e6a3d68c40ae275179f4bc5c04151bea8eb6864858f032574f771f4aca` |
| new | QUADRATIC | `0c705414181fbf5dcfb989f3619dc7d84ed1be969b88e066dcb96834d6346edf` |
| new | SQRT | `42408f7bf5dcbe8126c7d6b31ad5104e9afb6392ec39f2e6448a5d4ce3106eaf` |

Все восемь BBL независимо передекодированы указанным binary с
`--unit-frame-time us --save-headers`. Свежие CSV совпали с приложенными
CSV байт-в-байт. Получено соответственно:

- old: 38 600 / 37 072 / 33 164 / 31 518 data frames;
- new: 39 741 / 39 320 / 40 283 / 36 929 data frames;
- decoder не потерял ни одного декодируемого frame; missing PID iterations во
  всех sessions — 74.51–74.52%.

## 1. Нормировка коллектива

`CLAIMS_FOR_REVIEW.md:14-21` верен.

Все восемь headers дают `vbat_sag_compensation=0`, `dyn_idle_min_rpm=0`,
`motor_output_limit=100`, `thrust_linear=0`, `motorOutput=158,2047` и
`failsafePhase=IDLE`.

`dshot_bidir=1` сам по себе dynamic idle не включает. При наличии DShot
telemetry код присваивает
`dynIdleMinRps = dyn_idle_min_rpm * 100/60`; при нулевой настройке результат
всё равно ноль (`c40f1e096:src/main/flight/mixer_init.c:344-351`). Поэтому
ветка, меняющая `motorRangeMinIncrease`, не выполняется
(`c40f1e096:src/main/flight/mixer.c:251-272`), а нижний endpoint остаётся 158.

Sag factor при нулевой настройке остаётся нулём
(`c40f1e096:src/main/flight/mixer_init.c:365-375`), поэтому
`motorRangeMax=motorOutputHigh=2047` и range равен 1889
(`c40f1e096:src/main/flight/mixer.c:275-292`). Physical mapping выполняется как
`motorOutputMin + motorOutputRange * motorOutput`
(`c40f1e096:src/main/flight/mixer.c:477-503`). У QUAD X суммы roll, pitch и yaw
coefficients по четырём моторам равны нулю
(`c40f1e096:src/main/flight/mixer_init.c:84-89`), поэтому mean motors возвращает
именно applied collective.

Итоговая формула верна:

`applied_percent = (mean(motor[0..3]) - 158) / 1889 * 100`.

Осталась только logging quantization: каждый motor пишется как integer
(`c40f1e096:src/main/blackbox/blackbox.c:1298-1301`), поэтому worst-case ошибка
mean normalization — не более **0.0265 процентного пункта**.

**Вердикт claim 1: GO.**

## 2. Что доказывают whole-flight p90

### 2.1. Числа воспроизводятся

Таблица `CLAIMS_FOR_REVIEW.md:25-32` воспроизводится точно методом самого
черновика (`k8.py:29-32`):

| law | yaw old→new | roll old→new | pitch old→new |
|---|---:|---:|---:|
| FIXED | 16→13 | 22→19 | 25→17 |
| LINEAR | 23→19 | 21→26 | 15→21 |
| QUADRATIC | 32→17 | 25→29 | 18→22 |
| SQRT | 21→16 | 19→23 | 15→19 |

Но `k8.py:33` считает не motor **на упоре**, а motor `>=2040`. Для этого
критерия опубликованный range **4.2–4.9% → 4.8–6.6%** верен. Если писать
именно «на endpoint 2047», точные ranges равны **4.1–4.9% → 4.8–6.5%**.
Нужно либо сохранить числа и назвать критерий `motor >= 2040`, либо заменить
числа на exact-endpoint counts.

### 2.2. Более агрессивное пилотирование не объясняет roll/pitch result

Whole-log p90 абсолютной уставки, deg/s:

| law | roll old→new | pitch old→new | yaw old→new |
|---|---:|---:|---:|
| FIXED | 81→72 | 68→73 | 97→99 |
| LINEAR | 98→62 | 84→67 | 74→52 |
| QUADRATIC | 86→53 | 77→57 | 62→44 |
| SQRT | 69→65 | 100→73 | 77→51 |

То есть во втором sweep setpoint p90 ниже в **7 из 8** roll/pitch сравнений,
а не выше. Доля `|setpoint| >= 300 deg/s` для pitch также ниже во всех четырёх
new logs. Гипотеза «roll/pitch p90 стал хуже просто потому, что второй sweep
пилотировался агрессивнее» этими простыми метриками не поддерживается.

Но это не спасает причинный вывод. Yaw setpoint p90 тоже ниже в трёх из четырёх
new logs; это само по себе способно сдвинуть whole-flight yaw error p90 вниз.
Даже stratification по `|setpoint|` не даёт единого эффекта: например, для
LINEAR yaw в bin `50..100 deg/s` error p90 меняется **10→15 deg/s**, хотя
whole-flight p90 меняется 23→19. Состав манёвров и внешних возмущений различен.

### 2.3. Прореживание — не главный дефект вывода

Headers дают `P interval=4`, а decoder — около 805 saved frames/s и
74.51–74.52% missing iterations. Это не позволяет утверждать значения на
каждом PID loop, но регулярных 805 Hz достаточно для whole-flight distribution
этих низкочастотных tracking errors. Дополнительное разбиение сохранённых
frames по 16 остаткам `loopIteration` меняет p90 не более чем на **3 deg/s**.
Это sanity check, не восстановление пропущенных loops.

Главный дефект `CLAIMS_FOR_REVIEW.md:36-39` — слово «перетюн улучшил». Есть
восемь разных вылетов без randomization и повторов. Данные разрешают только:

> In these four unrandomized old/new flight pairs, whole-log yaw tracking-error
> p90 was lower in all four new logs; roll/pitch p90 was higher in six of eight
> axis/law comparisons. The new flights were not more aggressive by setpoint
> p90, but the logs do not isolate a tuning effect from maneuver composition or
> session-to-session variation.

Закрывающее измерение: несколько randomized old/new повторов каждого law с
одинаковым scripted setpoint sequence либо bench/flight replay, затем
paired metric по одинаковым time/command bins.

**Вердикт claim 2: NO-GO as written; GO только как описательная статистика без
причинного “retune improved/worsened”.**

## 3. `z3`: code defect есть, доказанного flight failure нет

### 3.1. Поле и масштаб определены однозначно

В b8:

- `debug[2]` = roll `z3/16`;
- `debug[5]` = pitch `z3/16`;
- `debug[6]` = yaw `z3/16`;
- `debug[7]` = sign-tagged b0 scale, где отрицательный знак означает закрытый
  gate.

Это прямо задано в
`c40f1e096:src/main/flight/adrc.c:663-680`; constants
`ADRC_Z3_LOG_SCALE=16` и `ADRC_DEBUG_LIMIT=32767` находятся в
`c40f1e096:src/main/flight/adrc.c:168-171`. Рейлится именно telemetry `z3`, не
другое поле.

Слово `z3 > 100` в `CLAIMS_FOR_REVIEW.md:55` нужно заменить на
`max_axis |logged z3| > 100`: скрипт фактически берёт absolute value
(`k8b.py:20`), и первое пересечение в части sessions отрицательное.

### 3.2. Event table почти верна, но rail count неверен

Независимый пересчёт по свежим CSV:

| sweep | law | commanded >=20% | max-axis `|z3log|>100` | first `debug[7]>0` | floor→gate | max pre-gate `|z3log|` |
|---|---|---:|---:|---:|---:|---:|
| old | FIXED | 2.718265 | 2.719534 | 2.785299 | 67.034 ms | 32767 P |
| old | LINEAR | 2.703161 | 2.703161 | 2.779707 | 76.546 ms | 32767 R |
| old | QUADRATIC | 2.211640 | 2.212900 | 2.262239 | 50.599 ms | 23495 P |
| old | SQRT | 2.738415 | 2.739681 | 2.786477 | 48.062 ms | 20353 R |
| new | FIXED | 1.483262 | 1.483898 | 1.509201 | 25.939 ms | 32767 R |
| new | LINEAR | 1.522506 | 1.523773 | 1.556026 | 33.520 ms | 32767 P |
| new | QUADRATIC | 1.042388 | 1.043657 | 1.068321 | 25.933 ms | 32767 R |
| new | SQRT | 1.298282 | 1.298282 | 1.355232 | 56.950 ms | 28292 Y |

Следствия:

1. Displayed timestamps в `CLAIMS_FOR_REVIEW.md:57-64` корректны с точностью
   до 1 ms. Если window округлять из raw times, old QUADRATIC — **50.6 ms**, а
   new LINEAR — **33.5 ms**; целые 50/33 получены вычитанием уже округлённых
   timestamps.
2. Рост начинается через **0–1.269 ms**, то есть заявленные 0–2 ms защищаемы.
3. `CLAIMS_FOR_REVIEW.md:67` ошибается: pre-gate rail есть в **5 из 8**, не в
   6 из 8 logs. Это old FIXED/LINEAR и new FIXED/LINEAR/QUADRATIC.

Один logged 32767 сам по себе строго означает примерно
`|z3| >= 32766.5*16 = 524264`, а не ровно `>=524272`, потому что значение
округляется через `lrintf`. Но параллельный `axisI=-z3/b0` подтверждает, что
реальный internal `|z3|` всё же переходил 524272 во всех пяти rail sessions.
Консервативные lower bounds из максимального integer `|axisI|` именно на
pre-gate rail frames:

- old FIXED pitch: **606 000**;
- old LINEAR roll: **763 750**;
- new FIXED roll: **536 036**;
- new LINEAR pitch: **614 460**;
- new QUADRATIC roll: **585 085**.

### 3.3. `setpoint[3]` исправлен правильно, но это config-local equivalence

Blackbox b8 действительно пишет
`setpoint[3] = mixerGetThrottle()*1000`
(`c40f1e096:src/main/blackbox/blackbox.c:1287-1292`). Между `c40f1e096` и
`3c85c4b5a` в `blackbox.c` и `mixer.c` нет ни одной строки diff.

`mixerGetThrottle()` берёт `mixerThrottle`, записанный после throttle limit и
throttle boost, но до dyn idle, thrust-linearization compensation, RPM limiter,
automatic-mode overrides и mixer headroom
(`c40f1e096:src/main/flight/mixer.c:753-790`). Gate формально читает отдельный
`mixerGetAdrcCommandedThrottle()`, sampled после этих стадий
(`c40f1e096:src/main/flight/mixer.c:850-900`;
`c40f1e096:src/main/flight/adrc.c:431-448`).

В этих конкретных takeoff intervals эквивалентность обоснована: dyn idle и
thrust linearization равны нулю, throttle limit выключен, automatic modes не
активны, признаков вмешательства RPM limiter на spool-up нет, а снятие inhibit
совпадает с пересечением `setpoint[3]/10=20%` в пределах одного saved frame во
всех восьми logs. Поэтому прежняя подмена stick исправлена правильно. Не
следует превращать это в универсальное утверждение, что `setpoint[3]` всегда
тождествен gate-commanded на любой config.

### 3.4. Какой branch открыл gate

Во всех восьми logs gate открыл **gyro branch**, не direct-commanded и не
applied branch:

- commanded в opening frame — только **21.3–25.6%**, далеко ниже direct
  threshold 40%;
- applied в opening frame — **21.28–42.83%**; maximum interlock-qualified
  continuous saved run `>=40%` перед open равен лишь **4.429 ms**, не 250 ms;
- filtered gyro `max_axis |gyroADC|` в opening frame — **38–110 deg/s** при
  threshold 20 deg/s;
- после применения commanded floor saved spans с gyro выше 20 deg/s,
  заканчивающиеся open, имеют длину **24.665–46.798 ms**, согласуясь с
  configured 25 ms hold и возможными reset на невидимых loops.

Exact branch code — `c40f1e096:src/main/flight/adrc.c:443-503`. Из-за 74.5%
missing loops saved frames не доказывают каждый промежуточный PID iteration,
но direct и applied branches исключаются по magnitude/duration; в коде другой
ветви нет.

### 3.5. Это дефект или нормальный взлёт

Ответ: **это реальное выполнение дефектного b8 estimator path, но не доказанный
вредный flight event**.

После commanded floor b8 снимает inhibit, пока gate ещё закрыт:

`inhibitZ3Growth = !liftoff && throttleAtIdle`

(`c40f1e096:src/main/flight/adrc.c:599-609`). Одновременно gate удерживает
`b0u=0` (`adrc.c:584-597`). Поэтому любой angular acceleration от уже работающих
моторов observer вынужден приписывать disturbance `z3`, хотя известный actuator
input исключён из его модели. Даже если аппарат уже отделился от пола, это не
нормальная работа полного observer: это именно input-model blind interval.
Fix `3c85c4b5a` меняет условие на `!liftoff`
(`3c85c4b5a:src/main/flight/adrc.c:604-619`) и не допускает этот carry-in.

Но BBL не содержит altitude/range/contact field. В opening frames аппарат
явно powered and moving: mean eRPM **1644–1903**, `|acc|` **1.32–1.80 g**,
commanded **21.3–25.6%**. Это совместимо с реальным взлётом, но не определяет
момент отрыва внутри окна 26–77 ms. Commanded >20% само по себе airborne state
не измеряет.

### 3.6. Есть consequence, но causal harm не доказан

Дефект успевает изменить control command:

- maximum `|axisI|=|z3/b0|` в opening frame по каждому log — **55–123**;
- maximum в первые 100 ms после open — **77–251**;
- в семи из восьми logs post-open peak выше opening value, то есть `z3` не
  становится безвредным мгновенно;
- к концу первых 100 ms максимальный `|axisI|` по axes уже снижается до
  **11–30**.

При этом в первые 100 и 300 ms после open нет **ни одного** frame с motor=2047.
Один motor находится на lower endpoint 158 в **8.64–28.40%** первых 100 ms и
**2.88–9.50%** первых 300 ms. Tracking-error p90 по худшей оси первых 100 ms
равен **60–154 deg/s**, но setpoints в основном малы, а физический takeoff
transient сам является сильным confounder.

Следовательно, защищаемая формулировка:

> All eight AIR65 b8 logs exercise the pre-gate z3-growth blind interval: z3
> starts growing within one saved frame after commanded collective clears the
> 20% idle interlock, while b0*u is still suppressed. Five of eight logs reach
> the z3 telemetry rail before the gyro path opens the gate 25.9–76.5 ms later.
> This produces a 55–123-unit ADRC I contribution at gate opening. These logs do
> not isolate a resulting flight-quality penalty; no motor reaches the upper
> endpoint in the following 300 ms.

Нельзя писать, что эти восемь takeoffs **доказывают harmful failure** или что
наблюдаемые post-open angular errors вызваны именно precharged `z3`. Закрывающее
измерение — randomized matched b8 versus build containing `3c85c4b5a` на
одинаковой launch ramp, с altitude/range/contact marker и full-rate logging
internal commanded/applied collective и unclipped `z3`.

Фраза «ему нужен b9» также не привязана к проверяемому ref: в локальном repo
нет tag/ref `b9`, а `3c85c4b5a` находится под ref `pr15400-builds-b7`. Писать
нужно **“a build containing 3c85c4b5a or its equivalent fix”**, пока не указан
точный public b9 artifact/commit.

Историческое «третий борт» требует явного списка двух прежних hardware logs с
тем же classifier. Текущий corpus доказывает AIR65, но сам по себе не доказывает
ordinal novelty.

**Вердикт claim 3: NO-GO as written. После замены 6→5, абсолютных labels,
снятия causal-harm claim и привязки рекомендации к exact fixed commit — GO как
hardware reproduction дефектного code path.**

## 4. Airmode: claim прямо опровергнут raw decode

`CLAIMS_FOR_REVIEW.md:93-98` делает вывод по человекочитаемому
`flightModeFlags`, который для этой firmware несовместим с decoder mapping.

Firmware пишет в поле не runtime `flightModeFlags`, а первые 32 bits
`rcModeActivationMask`
(`c40f1e096:src/main/blackbox/blackbox.c:983-1015`). В этом mask `BOXARM=0`, а
`BOXAIRMODE=24` (`c40f1e096:src/main/fc/rc_modes.h:29-62`). Decoder же трактует
bit 0 как `ANGLE_MODE`, знает только bits 0..9 и молча отбрасывает bit 24
(`blackbox-tools/src/blackbox_fielddefs.c:3-15`,
`blackbox-tools/src/blackbox_fielddefs.h:98-112`,
`blackbox-tools/src/parser.c:896-935,957-960`). Поэтому обычный CSV выглядит
неизменным даже тогда, когда raw mask меняется.

Fresh decode с `--unit-flags raw` даёт:

| sweep | law | Airmode ON, relative time | raw transition |
|---|---|---:|---:|
| old | FIXED | 6.805570 s | `1 → 16777217` |
| old | LINEAR | 5.710408 s | `1 → 16777217` |
| old | QUADRATIC | 4.968318 s | `1 → 16777217` |
| old | SQRT | 6.289518 s | `1 → 16777217` |
| new | FIXED | 4.323014 s | `1 → 16777217` |
| new | LINEAR | 4.645208 s | `1 → 16777217` |
| new | QUADRATIC | 5.774063 s | `1 → 16777217` |
| new | SQRT | 3.678103 s | `1 → 16777217` |

`16777217 = 0x01000001 = BOXAIRMODE bit 24 + BOXARM bit 0`. Header feature
mask `268697608` не содержит global `FEATURE_AIRMODE` bit 22, поэтому именно
этот BOX transition меняет `isAirmodeEnabled()`; код делает это напрямую в
`c40f1e096:src/main/fc/rc_modes.c:165-175`. Это не косвенный вывод по lower
clamp: firmware зарегистрировала switch во всех восьми flights.

`airmode_activate_throttle=25` сам Airmode не включает. Он лишь latch'ит
`throttleRaised` и участвует в PID stabilization после того, как Airmode уже
enabled (`c40f1e096:src/main/fc/core.c:829-849`).

Что logs **не** решают: почему после успешно зарегистрированного перехода
пилоту субъективно кажется, что поведение осталось прежним. Для этого нужен
отмеченный пилотом bad occurrence и одинаковый low-throttle maneuver до/после
switch. Но просить новый log на основании «ни один не захватил переключение»
нельзя — все восемь его захватили.

**Вердикт claim 4: NO-GO, factual claim refuted.** Публикационная замена:

> The normal decoder output hides the Airmode bit: it labels BOXARM bit 0 as
> ANGLE_MODE and drops BOXAIRMODE bit 24. Raw flags show that the FC did register
> the Airmode switch in all eight logs, at 3.678–6.806 s after log start. The
> logs therefore refute a missed-switch hypothesis, but do not explain the
> reported subjective feel after activation.

## 5. Полный header diff

Core claim `CLAIMS_FOR_REVIEW.md:104-109` верен: attribution к одному ratio
невозможна. Но список изменений неполон.

Pairwise full-header diff каждого old/new law даёт следующие независимые ADRC
config changes:

- `adrcWC`: `87,87,190 → 80,80,96`;
- `adrcWO`: `112,112,130 → 103,103,125`;
- `adrcB0`: `6500,4000,22000 → 7007,4312,5848`;
- `adrc_hover_throttle`: `30 → 27`.

То есть пропущено, что roll и pitch `b0` тоже выросли на **7.80%**
(`6500→7007`, `4000→4312`). Yaw одновременно меняет:

- `wc 190→96`: **-49.47%**;
- `wo 130→125`: **-3.85%**;
- `b0 22000→5848`: **÷3.762** / **-73.42%**;
- общий hover reference `30→27`: **-10%**.

Headers `rollPID/pitchPID/yawPID` тоже меняются (`87,112,65 → 80,103,70`,
`87,112,40 → 80,103,43`, `190,130,220 → 96,125,58`), но при `pid_type=1`
ADRC overwrites `pidData[].P/I/D` своим output
(`c40f1e096:src/main/flight/pid.c:1111-1119`); это не отдельный действующий
classic-PID controller change.

Кроме этого pairwise headers отличаются только session/runtime values:

- `vbatref`: 430–432 old против 431–433 new — start voltage, не setting;
- `rc_smoothing_rx_smoothed`: 249/250 Hz — измеренный текущий RX rate
  (`c40f1e096:src/main/blackbox/blackbox.c:1794-1797`), не config change.

`adrc_b0_law` одинаков для соответствующей пары и закономерно различается
между четырьмя laws. Других logged config changes полный diff не показывает.

**Вердикт claim 5: GO после явного добавления roll/pitch b0 changes и
различения config от runtime header values.**

## Обязательные правки перед публикацией

1. Claim 2 переименовать из «ретюн улучшил/ухудшил» в «whole-log p90 в этих
   sessions изменился»; убрать причинное «вероятно следствие wc/wo».
2. Для motor saturation либо раскрыть критерий `>=2040`, либо заменить range
   exact endpoint на 4.1–4.9% → 4.8–6.5%.
3. В Claim 3 заменить `z3>100` на `max_axis |logged z3|>100` и `max z3` на
   `max pre-gate |logged z3|` с axis label.
4. Исправить **6/8 → 5/8**; если публикуются integer windows, не получать их
   вычитанием округлённых timestamps.
5. Разделить два вывода Claim 3: defect path воспроизведён; harmful flight
   consequence этими takeoffs не изолирован.
6. Рекомендовать exact build containing `3c85c4b5a`, не непроверяемое имя b9;
   «третий борт» снабдить списком двух прежних sessions либо убрать ordinal.
7. Claim 4 переписать полностью: raw bit 24 включает Airmode во всех восьми
   logs на 3.678–6.806 s; software missed-switch hypothesis опровергнута.
8. В Claim 5 добавить roll/pitch `b0 +7.80%`; `vbatref` и measured RX rate не
   выдавать за config changes.
9. Исправить служебный путь в `CLAIMS_FOR_REVIEW.md:12`: scripts находятся в
   `.scratch/8ksal8-b0sweep3/`, а не `/tmp/.../scratchpad/`.

До этих правок общий verdict — **NO-GO**.

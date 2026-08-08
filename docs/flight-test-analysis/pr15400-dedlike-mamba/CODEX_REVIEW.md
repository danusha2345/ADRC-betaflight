# Adversarial review: @dedlike MAMBA flight log

Вердикт: **NO-GO для опубликованного текста в текущей формулировке.** Само наблюдение — быстро растущая ADRC yaw-осцилляция при тихом PID-контроле — реальное. Но временная шкала saturation ошибочна, RHP-pole не доказан, roll начинается до верхнего rail, а фраза “gate not involved” причинно неверна.

Декодирование повторено `blackbox_decode` commit `f832acf9cd`, firmware проверена строго по `6317fe2aada13113f4c337e2c6fcade9f66fa5c3`.

## Главная фактическая ошибка: saturation начинается не на 120 ms

`ANALYSIS.md:60-65` смешивает три разных ограничения:

- yaw `pidSum` впервые достигает `±400` на **87.017 ms**;
- верхний motor rail `2047` впервые достигается на **127.025 ms**;
- нижний motor rail `158` активен вообще во всех **205/205** кадрах, хотя до 127 ms он ещё не режет axis authority — mixer сохраняет диапазон сдвигом collective.

Правильные доли:

| Окно | Yaw command у `±0.4` | Верхний motor `2047` |
|---|---:|---:|
| 0–30 ms | 0% | 0% |
| 30–60 ms | 0% | 0% |
| 60–90 ms | **10%** | 0% |
| 90–120 ms | **53%** | 0% |
| 120–150 ms | 13% | 53% |
| 150–180 ms | 13% | 60% |
| 180–210 ms | 0% | 78% |

Поэтому `ANALYSIS.md:85` содержит прямую ошибку: `53/60/78%` взяты из столбца upper-motor rail и ошибочно названы временным распределением 13% yaw `pidsum_limit`.

То же видно из противоречия внутри документа: таблица сообщает roll `0%` у pidsum limit, а ниже заявлено 6%. Причина — `spectra.py:21-24` считает уже применённую mixer-axis команду после общей нормализации, а не входной `pidData.Sum`. Настоящие 12 roll-кадров с `|P+D|≥490` считает другой скрипт.

## Вердикт по восьми тезисам

### 1. Gate never opened — ПОДТВЕРЖДЕНО. “Gate not involved” — ОПРОВЕРГНУТО как причинная формулировка.

`debug[7]` отрицателен во всех 205 кадрах, диапазон `−100…−120`; он не близок к clipping. Debug z3 равен нулю.

Но нулевой debug сам по себе означает лишь примерно `|z3|<8`, потому что `6317fe2aa:src/main/flight/adrc.c:591-607` делит z3 на 16 и округляет. Внутренний точный ноль подтверждается уже кодом: arm reset ставит z3 в 0 (`adrc.c:174-189`), а закрытый gate при idle отклоняет любое увеличение `|z3|` (`adrc.c:530-537`).

При этом закрытый gate — активная часть loop: `adrc.c:515` принудительно делает `b0u=0`, хотя моторы реально воздействуют на craft. Более того, applied collective пересекает liftoff threshold 40% ровно на **87.017 ms**, но b6 использует commanded collective и намеренно оставляет gate закрытым. Контрфактуально это другое поведение observer. Доказано только: **ADRC-026 gate-open/z3-windup здесь отсутствует**. Не доказано: **gate dynamics не участвуют вообще**.

### 2. Рост реальный — ПОДТВЕРЖДЕНО. “RHP pole”, “не limit cycle”, “divergent instability” — НЕДОКАЗУЕМО.

Независимый fit по несатурированным первым 80 ms:

- `f = 37.0 Hz`;
- exponential time constant `65.6 ms`;
- `R²=0.988`;
- constant-amplitude sinusoid хуже по SSE в **9.5 раза**.

Значит, это не артефакт именно 30-ms окон. Но до первого yaw clamp остаётся только около **трёх циклов**, не семь. После 87 ms система уже нелинейна. Для дискретного нелинейного, меняющего operating point loop нельзя из finite transient вывести pole в RHP; даже для линейной дискретной модели речь шла бы о pole вне unit circle.

Limit cycle также не исключён: растущая startup-огибающая может быть переходом к saturation-limited cycle. После saturation yaw peak не начинает монотонно падать: положительные peaks идут `121 dps @112 ms`, `113 @140 ms`, затем **128 @170 ms**. Фраза “78→39 precisely because saturation costs authority” неверна.

### 3. Yaw первый — ПОДТВЕРЖДЕНО. “Roll only after motors rail” — ОПРОВЕРГНУТО.

Roll достигает:

- `|gyro|≥5 dps` на **86.017 ms**;
- `≥10 dps` на **103.020 ms**;
- `≥15 dps` на **107.021 ms**;
- верхний rail появляется лишь на **127.025 ms**.

Даже опубликованная таблица показывает roll RMS `2.7→7.7 dps` в окне 90–120 ms при 0% upper rail. Roll начинается примерно одновременно с yaw `pidsum` clipping, но до motor rail.

Следовательно, причина отзыва ADRC-024 link неверна. Сам отказ считать это четвёртым ADRC-024 sighting остаётся разумным, но по другой причине: активный roll участок длится около 0.11 s, то есть содержит лишь 2–3 цикла. “23 Hz” здесь слишком неточно для идентификации механизма.

### 4. Collective поднят mixer lower clamp — ПОДТВЕРЖДЕНО очень жёстко.

Во всех **205/205** кадрах минимальный motor равен `158`, а вычисленно:

`collective = -min(axis motor mix)`

с residual не больше `1.1e-16`. Это именно `mixer.c:697-700`.

Альтернативы не объясняют рост:

- `dyn_idle_min_rpm=0`;
- `thrust_linear=0`;
- `throttle_limit_type=OFF`;
- throttle stick постоянно 1000;
- angle throttle correction имеет default 0;
- `motor_idle=550` только задаёт нижний endpoint `158`, уже вычтенный при нормализации;
- throttle boost при неизменном нулевом throttle не создаёт положительного шага.

Airmode действительно участвует: feature bit `1<<22` установлен и сохраняет полную axis authority на нулевом throttle. Но он не является альтернативой clamp — это условие, при котором clamp поднимает collective сильнее.

### 5. D-equivalent численно доминирует — ПОДТВЕРЖДЕНО как composition, не как причинность.

`6317fe2aa:src/main/flight/pid.c:1110-1115` действительно записывает ADRC P/I/D в `pidData`.

Time-aware DFT даёт D/P:

- roll: **2.53**;
- pitch: **2.57**.

На yaw term можно восстановить напрямую до clipping, хотя отдельного поля нет. Проверка формулы на roll совпадает с записанным `axisD[0]` с median error **0.31 PID units**. Для yaw до 87.017 ms:

- P standard deviation `43.85`;
- inferred D standard deviation `111.65`;
- D/P `2.55`;
- на 34 Hz D/P `2.52`.

Поэтому D-dominance на failing axis поддержана лучше, чем написано. Но dominance не доказывает, что D-путь является причиной отрицательного damping: он может быть сильным ответом на уже растущую gyro motion. Для причинности нужен A/B по `wc_yaw` или `b0_yaw`.

### 6. QUAD X decomposition — ПОДТВЕРЖДЕНО. Cross-validation через median 0.0009 — вводит в заблуждение.

Коэффициенты совпадают с `6317fe2aa:src/main/flight/mixer_init.c:84-89`, header сообщает `mixer_type:LEGACY`.

До 120 ms reconstruction действительно очень точен: max error `0.00148` roll и `0.00118` pitch. Но по полной записи constant-`b0` reconstruction имеет:

- roll p95 **0.271**, max **0.420**;
- pitch p95 **0.068**, max **0.129**.

Median скрывает saturated tail. Кроме того, `debug[7]` в конце достигает `−120`: effective b0 вырос до примерно `2400`, тогда как `control_law_terms.py:4` везде использует 2000. Формулировку надо ограничить: reconstruction подтверждает модель **в несатурированном участке с b0 scale=1**, а не всю запись.

### 7. PID quiet — ПОДТВЕРЖДЕНО как наблюдение, не как “loop, not airframe”.

Опубликованные whole-log `1.89/1.68 dps` верны. Ещё сильнее:

- первые 211 ms PID: roll/yaw `0.74/0.88 dps`;
- худшее 211-ms окно во всём PID log: `5.01/3.38`;
- PID 30-ms окно с почти тем же collective `7.697%`: `1.18/1.71`;
- ADRC: `34.2/57.9`.

Это убедительно опровергает “обычный arm transient любого controller” в данной сессии. Но PID ни разу не достигает applied collective ADRC `30–67%`. Поэтому “external vibration ruled out” и заголовок “loop, not airframe” слишком сильны: доказано controller-specific closed-loop состояние, а не независимость от plant, contact condition или RPM-dependent excitation. Один arm на режим также не отделяет воспроизводимый ADRC defect от редкого ADRC-specific arm transient.

### 8. Поле `axisD[2]` отсутствует — ПОДТВЕРЖДЕНО. “Term invisible” — ОПРОВЕРГНУТО частично.

`6317fe2aa:src/main/blackbox/blackbox.c:206-208,523-526` включает axisD только если legacy profile D ненулевой. Здесь legacy yaw D=0, хотя ADRC генерирует ненулевой D. Это реальный Blackbox instrumentation bug.

Но до yaw clamp D восстанавливается из mixer-axis command и P с D/P≈2.55. После clipping точное значение действительно теряется. Корректно: **“axisD[2] не записан непосредственно и после saturation не восстанавливается точно”**, а не “dominant term invisible”.

## Ещё три небезопасные публичные формулировки

- `ANALYSIS.md:180-181`: “reproducible” — ложное слово при одном ADRC arm. Сейчас это только “observed once”.
- `ANALYSIS.md:106-113`: props-on исключает propless artifact, но не означает “full aerodynamic damping”; craft стоит на земле, RPM и contact constraints меняются.
- `ANALYSIS.md:185-190`: `b0=4000 “should not diverge at all”` не следует из модели. Он уменьшит P/D authority вдвое, но не гарантирует stability. Тестировать логичнее только `adrc_b0_yaw`, короткими повторными arms с автоматическим stop threshold.

## Что могло сделать проблему yaw-specific

Самая важная пропущенная связка:

- classic yaw D в header равен **0**;
- ADRC независимо создаёт yaw `kd=2*wc=120` (`adrc.c:302-306`);
- inferred yaw D уже до saturation примерно **2.5× P**;
- yaw D при этом не логируется из-за проверки legacy D=0.

Дополнительные гипотезы:

- yaw `wo=80 rad/s = 12.7 Hz`, тогда как observed prelimit tone около 37 Hz — почти в 3 раза выше observer bandwidth, что может ухудшать phase margin;
- один `b0=2000` используется для всех осей, хотя сам код на `adrc.c:220-225` предупреждает, что b0 airframe-dependent;
- закрытый gate обнуляет `b0u`, но ground-constrained craft может всё равно физически двигаться по yaw сильнее, чем по roll/pitch.

`pidsum_limit_yaw=400` не объясняет зарождение: он впервые действует лишь на 87 ms. Он объясняет ранний переход в nonlinear regime.

Самый информативный следующий capture: несколько рандомизированных коротких PID/ADRC arms с pre-arm visibility, жёстко одинаковой позой и отдельным A/B только `adrc_b0_yaw`; diagnostic firmware должна писать `axisD[2]`, commanded/applied collective и фактический `b0u`. Для pole claim нужно хотя бы 15–20 несатурированных циклов при фиксированном operating point — нынешняя запись даёт только около трёх.

# Adversarial review: свежий ground event @dedlike от 09.08

Ref: `ORCHTASK-1050568-2135810720`

## Итоговый вердикт

**NO-GO для `CLAIMS_FOR_REVIEW.md` в текущей формулировке.** Это **не следует
считать вторым ADRC-028** и нельзя публиковать как доказанный дефект ADRC.

Самое сильное защищаемое название события:

> **Command-triggered ground-contact roll oscillation under ANGLE + AIRMODE,
> with mixer-induced collective lift.**

По-русски: **командно-возбуждённая ground-contact roll-осцилляция в
`ANGLE_MODE + AIRMODE` с подъёмом коллектива lower clamp микшера**.

Почему:

- подъём applied collective при нулевом commanded collective — штатная работа
  `AIRMODE`/legacy mixer: микшер сохраняет осевую власть и поднимает collective,
  чтобы отрицательная часть axis mix не ушла ниже motor floor;
- эпизод не возник самопроизвольно на нулевых R/P/Y setpoint: перед ним есть
  не один pitch input `−195`, а последовательность `−197` и затем
  **противоположный `+275 deg/s`**;
- первый upper rail вызван не растущим pitch P, а главным образом roll
  D-equivalent: в первом rail-frame raw roll `P+I+D+F = +544`, из них
  `axisD[0] = +439`, при pitch sum всего `+6`;
- после возврата R/P/Y setpoint почти к нулю roll-осцилляция и rail occupancy
  продолжаются около 0.3 s. Поэтому доказано, что onset был command-triggered,
  но не доказано, что последующий режим не мог быть self-sustaining;
- matched PID A/B с тем же `−197 -> +275 deg/s` reversal отсутствует. Старые
  PID-логи показывают, что классический PID с AIRMODE тоже поднимает collective
  при нулевом throttle, но не отвечают, дошёл бы он до rail на этом input.

То есть **дефект ADRC по этим данным не установлен**. Установлен опасный
props-on ground режим вне нормальной свободной динамики аппарата, где AIRMODE
штатно даёт controller output полную mixer authority. Остаточный ADRC-specific
вопрос — почему после input reversal возник насыщенный roll-tail — требует
restrained matched PID/ADRC A/B или HIL, а не ещё одного свободного props-on arm.

## GO / NO-GO по пяти заявлениям

| # | Вердикт | Что выдерживает проверку | Что нужно исправить |
|---|---|---|---|
| 1 | **GO с оговоркой** | `adrcB0:2000,2000,4000` реально применён; событие до газа не yaw-dominant. | `raising b0 halves authority` верно только для мгновенных P/D/I terms при фиксированном ESO state. `b0` также входит в `b0*u` и z3 limit, поэтому это не глобальное «ровно вдвое». |
| 2 | **NO-GO** | До первого положительного commanded collective гейт закрыт и истинный z3 остаётся ровно 0; onset и первый rail не являются ADRC-026/z3-windup. | Это не ADRC-028. Кроме того, `3c85c4b5a` не изменил бы первый rail, но **изменил бы** участок `5.631–5.656 s`: на старом коде z3 там доходит до log rail до открытия gate. Нельзя писать, что fix не изменил бы событие целиком и что blind spot «ни при чём». |
| 3 | **NO-GO как написано; core observation GO** | Событие command-triggered, оси до газа — roll/pitch, не yaw; lower clamp действительно поднимает collective. | Пропущен противоположный input до `+275 deg/s`; первый rail — roll D, не pitch P. Полносессионные пики `pitch −1998`, `roll +1141`, `axisP[1] +1662` появляются после газа/gate и не доказывают pre-gas cause. |
| 4 | **GO с оговоркой** | Log 1: `15.168 s`, `setpoint[3]=0` всю сессию, gate не открыт, z3=0, applied collective max `14.981%`, motor max `706`, yaw gyro `−112…+230 deg/s`. | Это только **weak negative control**: R/P/Y команды не нулевые (`|setpoint| max 166/109/326 deg/s`), а критического reversal `−197 -> +275` нет. |
| 5 | **GO** | В log 2 `axisD[2] = −82…+107`, population SD `7.058`; `axisP[2]` SD `4.746`; ratio `1.487`. Поле действительно содержит ADRC D-equivalent. | В тексте явно сказать, что это whole-session composition statistic, не causal attribution. |

Общий publication verdict: **NO-GO**, пока заявления 2 и 3 не заменены
исправленной интерпретацией выше.

## Provenance и воспроизводимость

Проверенный corpus:

- fresh raw BBL SHA-256:
  `1c9d6dee211d01d5f9b95941533747dc1486975a8d87402a2e758fabc93a9866`;
- supplied CSV SHA-256:
  `0fb9493770361e89d9979a81046de38b9e707aac9aa82e261dca67f92691f169`
  и `23a4de7b81afe388b24fb81425b03116a438ec4f65c1a5fe828805543be5e136`;
- decoder binary SHA-256:
  `6b35322c22d5d9e3d23dd171a9ac0424e2fb38f9b8a2232425155d47cd17d23e`,
  source HEAD `f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`;
- firmware commit:
  `6317fe2aada13113f4c337e2c6fcade9f66fa5c3`.

Обе сессии заново декодированы в `.scratch/dedlike2/redecoded_codex/`.
Обе CSV и оба `.event` **побайтно совпали** с supplied files (`cmp = 0`).
Старые 06.08 BBL также заново декодированы в
`.scratch/dedlike2/redecoded_0608/`; существовавшие supplied CSV совпали с
повторным decoder output.

Header comparison подтверждает:

- 06.08 ADRC log -> 09.08 log 1: изменён только
  `adrcB0 2000,2000,2000 -> 2000,2000,4000` плюс volatile `vbatref`;
- 09.08 log 1 -> log 2: `yawPID D 0 -> 1`, `d_max yaw 0 -> 1` плюс volatile
  `vbatref`;
- firmware везде `6317fe2aa`;
- `vbat_sag_compensation=0`, `dyn_idle_min_rpm=0`, `thrust_linear=0`,
  `motor_output_limit=100`, `motorOutput=158,2047`;
- `features=272958600` содержит `FEATURE_AIRMODE` bit `1<<22`;
- содержательные строки обеих свежих сессий идут в `ANGLE_MODE`, не ACRO.

Отдельная provenance-несостыковка: тестер сообщает физические моторы
`2400 kv`, но Blackbox header содержит configured `motor_kv=1960`. Это не
меняет хронологию, но hardware statement нельзя выдавать за header-confirmed.

## Методические проверки

### Commanded collective

Использовано `setpoint[3]/10`, не stick. Exact source пишет
`mixerGetThrottle()*1000` в `setpoint[3]`
(`6317fe2aa:src/main/blackbox/blackbox.c:1287-1292`), а `mixerThrottle`
фиксируется до AIRMODE headroom
(`6317fe2aa:src/main/flight/mixer.c:769-778`). В этих логах нет automatic
throttle mode/dynamic idle/thrust linearization, поэтому поле соответствует
commanded collective, которое нужно сравнивать с applied collective.

### Applied collective normalization

Формула

```text
applied_collective_pct = (mean(motor[0..3]) - 158) / (2047 - 158) * 100
```

здесь допустима. `vbat_sag_compensation=0` оставляет `motorRangeMax` равным
static high endpoint (`mixer.c:275-293`, `mixer_init.c:365-376`), dynamic idle
и thrust linearization выключены.

Независимая reconstruction из всех logged `P+I+D+F`, QUAD X coefficients,
axis limits и legacy mixer lower clamp на непрерывном pre-gas prefix log 2
совпала с motor-derived collective: p99 absolute error `0.177 pp`, max
`0.276 pp`. Оставшаяся невязка объяснима округлением logged terms/motors и
1 kHz sampling. Это прямо подтверждает mixer mechanism, а не только корреляцию.

Source path: axis sums ограничиваются и делятся на `1000`
(`mixer.c:731-750`), motor mix строится в `mixer.c:798-814`, а при AIRMODE
`throttle = constrainf(throttle, -normalizedMotorMixMin, ...)`
(`mixer.c:681-701`). При roll/pitch limit `500` чистая ось даёт `±0.5` mixer
range, поэтому около 50% applied collective при 0% commanded collective —
ожидаемый результат этого алгоритма, а не отдельная throttle command.

### z3=0

Одного нуля в `debug` недостаточно: firmware логирует
`lrintf(z3/16)` (`adrc.c:591-607`), поэтому он сам по себе лишь ограничивает
истинное значение примерно `|z3|<8`.

Здесь gap закрывается кодом:

- rising arm вызывает `adrcResetAll()` (`adrc.c:374-385`), а axis reset ставит
  `z3=0` (`adrc.c:174-188`);
- пока gate закрыт и commanded collective ниже 20%,
  `inhibitZ3Growth` отвергает любое увеличение `|z3|`
  (`adrc.c:427-449, 523-537`).

Поэтому на непрерывном pre-gas prefix истинный z3 действительно остаётся
ровно 0. Но после commanded `>=20%` старый код снимает inhibit до открытия
gate — именно этот blind spot меняет `3c85c4b5a`.

### `P interval 4`

`looptime=125 us`, `pid_process_denom=2` дают nominal PID period `250 us`;
Blackbox `P interval=4` сохраняет примерно один main frame на четыре PID
iterations, то есть около 1 kHz. `blackboxPInterval` задаётся как
`1 << sample_rate` (`blackbox.c:2305-2312`).

Все времена ниже — времена **первых сохранённых samples**, uncertainty порядка
одного log step (~1 ms). Они не являются наблюдением каждой PID iteration.
Более того, `loopIteration` в P-frames использует unencoded `PREDICT(INC)`
(`blackbox.c:196`), поэтому внутри 32 ms блока decoder показывает increments
по 1, а на I-frame перескакивает, например, `31 -> 128`. Нельзя использовать
эту CSV-колонку как доказательство покадрового покрытия всех 4 kHz iterations.

## Исправленная хронология log 2

Время относительно первой сохранённой data row (`11089698 us`):

| First saved sample | t, s | Что реально видно |
|---|---:|---|
| Более ранний pitch pulse | `1.835848–1.987835` | `setpoint pitch` до `+154`, applied collective до `18.396%`, motor max `853`, rail нет |
| Основной отрицательный pitch pulse | `4.677603–4.883585` | `setpoint pitch` до `−197`, `rcCommand pitch` до `−259`, applied collective до `24.709%`, motor max `1114` |
| Первый upper motor rail | **`5.024572`** | motor `[179,158,2047,2027]`; `setpoint pitch=+6`; roll raw sum `+544` (`P=105,D=439,F=0`), pitch sum `+6` |
| Противоположный pitch pulse | `5.035571–5.278548` | `setpoint pitch` до **`+275`**, `rcCommand pitch` до `+311`; applied collective max `51.668%` |
| Первый positive commanded collective | **`5.588517`** | `setpoint[3]=0.1%`; не `5.60 s` |
| Commanded collective `>=20%` | **`5.630513`** | `20.6%`; logged pitch z3 сразу `−675` |
| Logged z3 rail | **`5.647512`** | roll z3 field `−32767` при gate ещё закрытом |
| Gate first positive | **`5.655511`** | `debug[7]=+173`; z3 уже большой до открытия |
| `|gyroUnfilt pitch|>1500` | **`5.692507`** | `−1651 deg/s`, commanded `40.0%`, уже после газа и gate |
| Pitch gyro field rail/minimum | **`5.696507`** | единственный sample `−1998 deg/s`; это sensor-range sample, не точный физический peak |

От начала основного отрицательного pitch pulse до первого positive commanded
collective прошло `0.910914 s`. В 911 сохранённых pre-gas rows от
`4.677603` до `5.587520`:

- 402 rows имеют motor `>=2040`, но только 400 — ровно `2047`;
- это **23 отдельных rail runs**, а не один непрерывный 402-frame участок;
- max applied collective `51.668%` на `5.110564 s`;
- gate закрыт и z3 code-derived exact zero;
- pre-gas `|gyroUnfilt| max R/P/Y = 185/339/60 deg/s`;
- pre-gas `|axisP| max R/P/Y = 285/245/12`;
- pre-gas `|axisD| max R/P/Y = 786/492/13`.

Следовательно, pre-gas режим действительно не yaw и не z3-driven, но его
dominant saturated term — roll D-equivalent, а не pitch P.

После `5.28 s`, когда R/P/Y setpoint вернулись почти к нулю, roll gyro и
`axisD[0]` сохраняют насыщенную осцилляцию. Hann peak в окнах
`5.28–5.588 s` / `5.30–5.588 s` лежит в `19.5–20.9 Hz` (короткое окно,
resolution около `3.3–3.5 Hz`). Это не доказывает unstable pole/limit cycle,
но не позволяет написать, что вся 50%-фаза была непосредственным ответом на
остающийся `195 deg/s` input.

## Что произошло после газа

Полносессионные экстремумы из заявления 3 нельзя использовать как evidence
pre-gas cause:

- `pitch −1998`, `roll +1141`, `yaw +531 deg/s` возникают после commanded
  throttle, z3 growth и gate opening;
- quaternion-derived pitch меняется примерно с `+16 deg` перед gate до
  `−24 deg` на `5.750 s` и `−46.5 deg` на `5.800 s`;
- на `5.692–5.700 s` accelerometer и gyro показывают сильный physical
  impulse/rotation; `gyroUnfilt pitch=−1998` встречается один раз и выглядит
  как 2000 dps sensor rail.

Поэтому сомнение 4 верно: поздний peak — downstream physical motion
(отрыв/переворот/удар в ground-contact системе) во время реакции газом. Он не
разделяет вклад ADRC, AIRMODE, pilot throttle и механики контакта.

## Сравнение с classic PID 06.08

Все строки ниже — `ANGLE_MODE`, `AIRMODE` feature включён, commanded collective
`0%`. Сегменты определены как непрерывные `|setpoint pitch|>=10 deg/s`:

| Controller/log | Pitch segment, s | max `|setpoint pitch|` | max applied collective | max motor | rail |
|---|---:|---:|---:|---:|---|
| PID `btfl_002` 06.08 | `0.706–0.869` | `66` | `10.045%` | `530` | no |
| PID `btfl_002` 06.08 | `1.867–1.995` | `118` | `17.456%` | `815` | no |
| ADRC fresh log 2 | `1.836–1.988` | `154` | `18.396%` | `853` | no |
| ADRC fresh log 2 | `4.678–4.884` | `197` | `24.709%` | `1114` | no |
| ADRC fresh log 2 | `5.036–5.279` | `275` | `51.668%` | `2047` | yes |

Это отвечает только на половину вопроса:

- **да**, classic PID с AIRMODE на том же craft тоже поднимал collective при
  нулевом commanded throttle — до `17.5%` на имеющемся `118 deg/s` pulse;
- moderate ADRC pulse `154 deg/s` дал близкий масштаб `18.4%` и не rail;
- **нет**, старые PID-данные не содержат matching `−197 -> +275 deg/s`
  reversal, поэтому из них нельзя оценить PID outcome на свежем input и нельзя
  вычислить ADRC/PID ratio для события.

Просить повторить props-on тест ради этой точки нельзя. Discriminator — только
restraint/test stand с automatic cutoff, либо HIL/recorded gyro replay через
обе controller paths. Props-off может проверить configuration/log fields, но
не ground-contact plant dynamics.

## Одно ли это явление с 06.08

**Нет, считать одним явлением или вторым ADRC-028 — NO-GO.**

06.08 / ADRC-028 по текущему tracker:

- saved R/P/Y setpoints практически `1/0/0`;
- fast-growing yaw oscillation `34–37 Hz` с первых 211 ms записи;
- yaw command limit на `87.017 ms`, upper motor rail на `127.025 ms`;
- gate закрыт, z3 exact zero, commanded collective zero;
- статус tracker: `OPEN, observed once`, не reproduction
  (`ADRC_REMEDIATION_TRACKER.md:965-1037`).

09.08:

- несколько явных pitch commands, включая reversal `−197 -> +275 deg/s`;
- первый rail примерно через 4.7 s записи, не с первых frames;
- rail onset dominated roll D-equivalent;
- zero-setpoint tail преимущественно roll и около 20–21 Hz;
- затем pilot throttle открывает blind-spot window, z3 растёт до log rail,
  gate открывается и начинается реальное крупное движение аппарата.

Общее: один craft/firmware, ground contact, AIRMODE, lower-clamp collective
lift, closed gate и z3=0 в pre-throttle portion. Возможная общая ADRC
ground-loop susceptibility остаётся гипотезой. Разные trigger, dominant axis,
frequency family и timing не позволяют засчитать fresh event как второе
наблюдение ADRC-028.

## Ошибки и ограничения supplied scripts

1. `d2c.py:19` делает
   `pre=[x for x in rows if x['c']<0.05]`. Это не prefix до первого газа, а
   выборка **всех** zero-command rows, включая строки после возврата газа к
   нулю и уже открытого gate. Поэтому напечатанные им `до t=6.247`, `z3=14233`,
   `gate=да` и pre-phase gyro maxima методически неверны. Нужен срез
   `rows[:first_index(c>0)]`.
2. `d2b.py:29` называет threshold `>=2040` «мотор 2047». В этом событии first
   timestamp совпал, но counts различаются: 402 rows `>=2040`, 400 rows
   `==2047`.
3. `d2.py:17` static motor normalization здесь корректна только потому, что
   header действительно даёт `vbat_sag_compensation=0`, dynamic idle/thrust
   linearization off и fixed endpoints. Это проверено, а не принято на веру.
4. Ноль logged z3 в scripts сам по себе недостаточен; exact-zero вывод выше
   сделан только через arm reset + growth-inhibit path exact firmware.
5. Ни один script не учитывает `P interval=4` как thinning и не должен
   превращать saved-frame chronology в per-PID-iteration chronology.

## Безопасная формулировка тестеру

> Thank you for capturing the log — it is useful and changes the diagnosis.
> Please don't repeat an unrestrained props-on ground arm. The first motor rail
> occurred before a manual throttle response could help, so any follow-up must
> use a purpose-built restraint/test stand with an automatic cutoff; otherwise
> the data already captured is enough.

Она благодарит за уже полученные данные, прямо запрещает повтор без подходящей
оснастки и не звучит как выговор.

## Source anchors exact firmware

- ADRC arm reset / gate / z3 inhibit / logging:
  `6317fe2aa:src/main/flight/adrc.c:174-188, 340-385, 410-479, 482-607`;
- ADRC terms written into `pidData`:
  `6317fe2aa:src/main/flight/pid.c:1095-1115`;
- AIRMODE enabled state and feature bit:
  `6317fe2aa:src/main/fc/rc_modes.c:75-77, 140-176`,
  `6317fe2aa:src/main/config/feature.h:58-69`;
- legacy mixer lower clamp / axis scaling / commanded vs applied collective:
  `6317fe2aa:src/main/flight/mixer.c:681-701, 704-710, 731-778, 798-901`;
- QUAD X coefficients:
  `6317fe2aa:src/main/flight/mixer_init.c:84-89`;
- Blackbox `axisD` condition, state load, setpoint and thinning:
  `6317fe2aa:src/main/blackbox/blackbox.c:196-208, 520-526, 1248-1295, 1973-2015, 2301-2312`;
- PID/Blackbox scheduling:
  `6317fe2aa:src/main/fc/core.c:1217-1287, 1419-1422`.

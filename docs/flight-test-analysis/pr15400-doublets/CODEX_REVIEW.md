# Ревью Codex: анализ полётов 15–16.07.2026

Дата проверки: 2026-07-16  
Проверенный commit: `1980fd7d65a67d771cea42c97578541a6d7c8eaf`  
Scope: read-only перепроверка `.bbl`, декода, скриптов, численных результатов и формулировок в `ANALYSIS.md`/трекере.

## Итог

Основной результат ADRC-021 выдерживает независимую проверку: в этих полётах
зашитый `clamp((collective/hover)^2, 1, 3)` описывает зависимость хуже более
мягких законов, а наблюдаемый рост authority существенно меньше квадратичного.
Это хорошее основание для controlled A/B кандидатов `sqrt` и `linear`, но пока
не доказательство конкретного production-закона.

Текст в текущем виде не стоит отправлять Bob'у без исправлений. В нём есть две
прямые фактические ошибки про punch/z3, чрезмерно сильный вывод ADRC-024 и
несколько мест, где наблюдение представлено как установленная причина.

## Что проверено и подтверждено

- Commit `1980fd7d65` присутствует в `fork/master`.
- Все десять `.bbl` Bob'а совпадают по SHA-256 с архивом
  `blackbox/bvandevliet/2026-07-15-walhalla/`.
- Оба `.bbl` jmsweng совпадают с исходным GitHub attachment
  `2026-07-15.zip`; SHA-256 архива:
  `35c2770b9efffa3952c3e8def580c73d00abae31b2877dbd847fa620e3edb3ff`.
- Повторный decode `42-100-2000.bbl` инструментом blackbox-tools commit
  `f832acf9cd9dbe5ad8220de1a5f4eb4021523d72` дал CSV и event, идентичные
  локальным побайтно.
- Заголовки jmsweng подтверждают `08ad602ce`, то есть точный b4 release;
  заголовки Bob подтверждают board/date, а соответствие build commit
  `35adbf14e6` основано на сообщении автора и его `diff all`.
- Все основные опубликованные выводы скриптов воспроизвелись:
  - Bob: 159 перекрывающихся окон; `sqrt=0.425`, `linear=0.453`,
    `fixed=0.512`, code-quadratic `0.541`;
  - jmsweng: 71 перекрывающееся окно; `sqrt=0.294`, `fixed=0.331`,
    code-quadratic `0.345`, `linear=0.360`;
  - ADRC-025: 18 p1-событий, median 60, max 135 deg/s;
  - Cascade-ESO: линия около 35 Hz, 20–26 deg/s в первых окнах после
    взлёта; продолжительность лога 5.709 s.

## Дополнительные robustness checks

### Неперекрывающиеся окна

При `HOP_FRAC=1.0` основной ranking сохраняется:

| Craft | n | sqrt | linear | fixed | code quadratic |
|---|---:|---:|---:|---:|---:|
| Bob | 82 | 0.441 | 0.453 | 0.540 | 0.544 |
| jmsweng | 37 | 0.308 | 0.402 | 0.317 | 0.387 |

У Bob `sqrt` остаётся первым во всех leave-one-log-out прогонах. Однако разрыв
`code - fixed` в отдельных leave-one-log-out выборках уменьшается до `+0.004`,
поэтому фразу «quadratic хуже отсутствия schedule» лучше подавать как результат
этого corpus, а не как универсально доказанный факт.

На двух отдельных логах jmsweng победители различаются: на
`42-100-2000` лучший `fixed`, на converted-stock — `linear`; `sqrt` становится
лучшим после pooling. Следовательно, «sqrt fits best on both crafts» формально
верно для pooled scoring, но ещё не выбирает production exponent.

### Частотный confound

`b0_hat` сильно зависит от полосы, что уже честно отмечено в анализе. Проверка
`log(b0_hat) ~ log(collective/hover) + log(excitation_frequency) + log fixed
effects` на окнах Bob дала показатель газа около `0.74`, а не `2`. То есть
учёт спектра манёвров не возвращает quadratic и поддерживает главный вывод
ADRC-021. Но OLS выполняется внутри замкнутого контура, использует те же `u` и
gyro, отбирает только положительный slope с `R² >= 0.5`, поэтому это
описательная system-identification оценка, а не несмещённая causal estimate.

## Обязательные исправления

### 1. Неверно: debug rail пришёлся на самый большой punch

Сейчас написано: «the biggest punch rails z3-pitch».

Фактические события p1:

- единственный debug-rail `524k`: throttle `78.7%`, rebound `127 deg/s`;
- максимальный throttle: `88.8%`, rebound `132 deg/s`, z3 `238k`;
- максимальный rebound: throttle `75.0%`, rebound `135 deg/s`, z3 `260k`.

Нужно заменить на что-то вроде:

> One of the larger punch events (78.7%, 127 deg/s rebound) reaches the
> ±524k Blackbox debug clipping limit; neither the highest-throttle event nor
> the maximum-rebound event clips the z3 debug channel.

### 2. Неверно: все 11 z3-rail эпизодов связаны с flip/loop или zero throttle

`2.74%` и `11 episodes` воспроизводятся, но утверждение `every one coincides`
неверно. Эпизод `62.25–62.38 s` проходит при среднем throttle `56%`, максимум
pitch gyro на самом эпизоде `61 deg/s`; в контексте ±0.5 s максимум pitch gyro
`84 deg/s`, setpoint pitch `39 deg/s`, minimum throttle `34%`. Это не flip/loop
и не zero-throttle drop.

Корректно: десять из одиннадцати эпизодов связаны с aggressive flip/loop или
zero-throttle segment; один эпизод остаётся необъяснённым.

### 3. Debug rail не равен внутреннему clamp ESO

`debug[5] * 16 = ±524272` — предел int16 Blackbox-телеметрии после
`ADRC_Z3_LOG_SCALE`, а не доказательство, что внутренний `z3` дошёл до
`pidSumLimit * b0_eff`.

Внутренний clamp в `adrc.c`:

```c
const float maxZ3 = finitePidSumLimit * b0;
adrcRuntime->z3[axis] = constrainf(adrcRuntime->z3[axis], -maxZ3, maxZ3);
```

Он может быть значительно выше debug clip. По логу известно только
`|z3| >= 524272`; утверждать, что I-equivalent занял весь `pidSum`, нельзя.
Нужно написать, что реальная величина после clipping телеметрии неизвестна и
может находиться от debug threshold до внутреннего authority clamp.

### 4. ADRC-024: `wo150 collapses the ring` не следует из incidence

Фактическая таблица:

- base: `2–9%` ring windows на лог;
- `wo150`: `1/19 = 5%`;
- `wc85`: `9/81 = 11%`;
- converted: `2–4%`.

Пять процентов находится прямо внутри базового диапазона. Для `wo150`
подтверждено только отсутствие сильной амплитуды в коротком полёте: единственное
окно едва выше threshold, `5.4 deg/s`. Формулировка должна быть:

> The wc85 flight is suggestive of increased ring incidence and amplitude.
> The short wo150 flight contains no strong ring (one threshold-level window),
> but is too short to establish a reduction in incidence. This pattern is
> consistent with a phase-margin hypothesis, not yet a causal discriminator.

Подсчёт независимых эпизодов вместо перекрывающихся окон также даёт:

- каждый base-log: по 2 эпизода;
- `wc85`: 6 эпизодов;
- `wo150`: 1 эпизод;
- каждый converted-log: по 1 эпизоду.

Это поддерживает `wc85 is suggestive`, но полёты не были randomized или
maneuver-controlled.

### 5. Converted b0 не подтверждён одинаково хорошо на обоих крафтах

На Bob hover-band числа converter действительно близки к оценке. На jmsweng
pooled best-fit hover b0 около `1909–1914`, поэтому `2252–2328` выше примерно
на `18–22%`, а не «within ~15%». Сам полёт доказывает, что converted tune
летает, но не изолирует правильность его b0 от `wc/wo`.

Рекомендуемая формулировка ADRC-022:

> b0=2000 is well supported as a conservative hover starting point across
> both crafts. The converter values are close on Bob's craft and remain a
> plausible flight-tested starting point on jmsweng's craft, but appear
> somewhat high in the latter craft's direct estimate.

### 6. Mechanical/motor-band attribution оставить гипотезой

В `gyroUnfilt` действительно присутствует сильная линия в log-frame
`150–200 Hz`, а устойчивого hover-band ADRC-024 на jmsweng нет. Но без
синхронизации Blackbox с аудио/видео и с учётом aliasing нельзя утверждать, что
именно эта линия является слышимой осцилляцией или что её источник механический.

Корректно: `a strong high-frequency gyroUnfilt line is observed and is a
plausible mechanical/motor-band candidate; its relationship to the audible
oscillation is unproven`.

### 7. Заявление о полной воспроизводимости сейчас слишком сильное

Существующие скрипты воспроизводят основные b0/ring/punch/jmsweng таблицы, но:

- для `z3-on-u slope` нет сохранённого скрипта;
- cascade `35 Hz / 20–26 deg/s / 5.7 s` не выводится существующим скриптом;
- sensitivity sweeps LP/window/R² не автоматизированы;
- `.csv/.event` не закоммичены, `blackbox_decode` version/commit и точная
  команда batch-decode не зафиксированы в `ANALYSIS.md`.

Либо добавить скрипты/команды для этих результатов, либо заменить «every
number is generated by a saved script» на более узкое утверждение.

## Что можно оставить как итог после правок

1. Два крафта независимо показывают существенно более пологий рост authority,
   чем зашитый quadratic schedule.
2. `sqrt` и `linear` — обоснованные кандидаты для следующего controlled A/B;
   cap около `1.7–2` и below-hover behavior требуют отдельного теста.
3. `b0=2000` хорошо поддержан как консервативная hover-отправная точка.
4. `wc85` дал более частый и сильный ADRC-024-подобный ринг; phase margin —
   рабочая гипотеза, не установленная причина.
5. ADRC-025 воспроизводится на обоих тюнах, но причинная связь с b0 schedule и
   z3 saturation ещё не доказана.
6. Самый информативный следующий тест: на одном неизменном крафте randomized
   A/B quadratic → sqrt → linear с одинаковыми doublet/ring/punch манёврами,
   после чего повторно оценить ADRC-024 и ADRC-025.


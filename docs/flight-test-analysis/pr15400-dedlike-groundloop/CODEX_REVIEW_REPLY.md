# Повторное adversarial-review `DRAFT_reply.md`

Дата проверки: 2026-08-09.

Проверенный текст: `DRAFT_reply.md`, 62 строки, SHA-256
`055f67ecc433f5a693903edf38b0a541a3e4551c64b19d4b232314d840c95119`.
Проверены обе свежие CSV, повторно декодированные данные, старый ADRC log от
06.08, `diffall.txt` и exact firmware `6317fe2aa`.

## Итог

**NO-GO в текущем виде.** Почти все обязательные исправления из прошлого
review перенесены правильно, но появились два существенных новых дефекта:

1. `ANGLE_MODE` в `DRAFT_reply.md:9,15` — ложная интерпретация собственного
   default-decoder output. Raw S-frame содержит только `0` и `1`; это
   `BOXARM` bit 0, а `BOXANGLE` bit 1 не установлен. Сессии были в ACRO.
2. `DRAFT_reply.md:19` говорит, что слова тестера про «few ms» совпадают с
   timing «exactly», а затем само же приводит интервал около 900 ms. По логу
   main negative pitch pulse начался за **0.910914 s** до первого положительного
   commanded collective; первый rail появился за **0.563945 s** до него. Это
   подтверждает только порядок событий, не «few ms» и не точное совпадение.

После исправления этих двух мест и уточнения timebase в сравнительной таблице
текст можно публиковать.

## Обязательные правки

### 1. Исправить ACRO/ANGLE

Проблемные места: `DRAFT_reply.md:9,15`.

Exact firmware записывает в S-frame не runtime `flightModeFlags`, а младшие
32 bits `rcModeActivationMask`:

- `6317fe2aa:src/main/blackbox/blackbox.c:403-410,1005-1015`;
- `BOXARM = 0`, `BOXANGLE = 1`, `BOXAIRMODE = 24`:
  `6317fe2aa:src/main/fc/rc_modes.h:29-62`.

Независимый decode `btfl_all.bbl --unit-flags raw` дал в log 2 только:

```text
flightModeFlags raw: 0 (9 rows), 1 (6221 rows)
```

Bit 1 ни разу не установлен. Default decoder ошибочно называет bit 0
`ANGLE_MODE` (`blackbox-tools/src/blackbox_fielddefs.h:98-112`,
`src/blackbox_fielddefs.c:3-15`, `src/parser.c:896-960`). Это как раз дефект,
описанный в ISSUE 2 соседнего черновика.

Следовательно:

- в названии события заменить `ANGLE + AIRMODE` на **`ACRO + AIRMODE`**;
- удалить фразу о levelling controller;
- заменить её, например, на:

  > Raw mode-mask decoding shows ACRO, not ANGLE: only `BOXARM` bit 0 is set.
  > The default decoder labels that bit `ANGLE_MODE`; that label is wrong for
  > this firmware. The −197/+275 deg/s values are therefore rate-controller
  > setpoints associated with the RC input/rate mapping, not levelling output.

`AIRMODE` при этом подтверждён независимо: header `features=272958600` содержит
`FEATURE_AIRMODE = 1 << 22`, а `isAirmodeEnabled()` включает его по feature или
`BOXAIRMODE` (`6317fe2aa:src/main/fc/rc_modes.c:75-77,140-176`).

### 2. Переписать timing paragraph

`DRAFT_reply.md:19` содержит сразу две ошибки.

- Applied collective уже уходил от низкого уровня во время более раннего
  pitch pulse: впервые превышал 2% на **1.829850 s** и 5% на **1.839847 s**.
  Поэтому `the collective leaves idle at about 4.70 s` нельзя выдавать за
  первое такое событие в записи.
- `a few ms` не совпадает с измеренным интервалом:
  - main negative pitch pulse starts: **4.677603 s**;
  - first upper rail: **5.024572 s**;
  - first positive commanded collective: **5.588517 s**;
  - pulse-to-throttle: **0.910914 s**;
  - rail-to-throttle: **0.563945 s**.

Защищаемая замена:

> The log confirms the ordering in your account — the event began before the
> throttle response — but not the “few ms” interval. The main negative pitch
> pulse starts at 4.677603 s, the first motor rail is at 5.024572 s, and the
> first positive commanded collective is at 5.588517 s: about 911 ms and
> 564 ms earlier, respectively.

Все времена здесь отсчитаны от **first saved data frame**, не от physical arm
и не от начала записи header. Это надо указать в абзаце и в таблице
`DRAFT_reply.md:42`: `127 ms after the first saved data frame` и
`5.025 s after the first saved data frame`.

### 3. Снять двусмысленность `in 2/2`

`DRAFT_reply.md:5` можно прочесть как «поле присутствует в двух логах из двух».
Это неверно: в log 1 `yawPID D=0` и `axisD[2]` отсутствует; в **log 2/2**
`yawPID D=1` и поле присутствует. Написать `the field is present in log 2/2`.

## Проверка всех перенесённых чисел

| Claim в draft | Независимая проверка | Вердикт |
|---|---|---|
| Pitch reversal `−197 -> +275 deg/s` | `−197` на 4.786593 s; `+275` на 5.132562 s | **верно** |
| First rail raw roll `+544`, `axisD[0]=+439`, pitch `+6` | frame 5.024572 s, motors `[179,158,2047,2027]`; roll `105+0+439+0=544`; pitch `8+0−7+5=6` | **верно** |
| Mixer reconstruction p99 `0.177 pp` | 5589 saved pre-throttle rows; nearest-rank p99 `0.176601 pp`, max `0.276178 pp` | **верно** |
| Tail `about 0.3 s`, `20–21 Hz` | 5.280548–5.587520 = `0.306972 s`; Hann peaks `19.4805` and `20.8333 Hz` for the stated windows | **верно с обычной оговоркой о коротком окне** |
| `adrcB0=2000,2000,4000` | header обоих fresh logs | **верно** |
| z3 blind window `5.631–5.656 s` | commanded >=20% at 5.630513; roll logged z3 rail at 5.647512; gate positive at 5.655511 | **верно после округления** |
| Log 1 setpoints `166/109/326 deg/s` | whole-session max absolute R/P/Y exactly `166/109/326` | **верно** |
| `motor_kv 1960` vs stated `2400 kv` | both fresh headers say `motor_kv=1960`; tester description says 2400 kv | **верно** |
| ADRC-028 setpoints `≈1/0/0`, first rail `127 ms` | old log: exactly `1/0/0`; rail at `0.127025 s` after first saved row | **верно при исправленном timebase** |
| ADRC-028 `34–37 Hz` | full-record Hann peak `34.146 Hz`; prior sinusoidal fit gives 37.0 Hz | **верно как диапазон методов, не как точная частота** |

## Остальные обязательные смысловые правки из прошлого review

1. **Название события:** применено по существу, кроме ошибочного `ANGLE`.
   `command-triggered ground-contact roll oscillation ... with mixer-induced
   collective lift` — сильнейшая защищаемая формулировка.
2. **Нормальность mixer lift:** применено правильно. Legacy lower clamp
   `constrainf(throttle, -normalizedMotorMixMin, ...)` находится в
   `6317fe2aa:src/main/flight/mixer.c:681-701`; axis sums ограничиваются в
   `:731-750`, QUAD X coefficients — `mixer_init.c:84-89`. При limit 500
   чистая насыщенная roll/pitch axis действительно требует около 50%
   collective headroom.
3. **Self-sustaining tail:** вопрос оставлен открытым корректно. Продолжение
   rail occupancy после возврата setpoint почти к нулю не доказывает ни limit
   cycle, ни отсутствие self-sustaining feedback.
4. **Matched PID A/B:** отсутствие сформулировано правильно. Старые PID pulses
   максимум 118 deg/s и не содержат reversal `−197 -> +275`; из них нельзя
   вывести ADRC/PID outcome ratio.
5. **Оговорка про b0:** применена правильно. При фиксированном ESO state
   P/D/I действительно масштабируются через `1/b0`, но `b0` также входит в
   observer feedback `b0*u` и z3 bound; глобального «ровно вдвое» нет.
6. **Разграничение с ADRC-028:** логика правильная: trigger, dominant axis,
   frequency family и timing различаются. Исправить только timebase и ANGLE.
7. **z3:** применено точно. До first positive commanded collective arm reset +
   closed-gate idle inhibit удерживают истинный z3 ровно в нуле
   (`adrc.c:174-188,374-385,427-449,523-537`). Fix `3c85c4b5a` не изменил бы
   onset/first rail, но подавил бы рост в 5.631–5.656 s до открытия gate.
8. **Log 1 как weak control:** применено правильно.
9. **Hardware provenance:** несостыковка 1960/2400 изложена без лишнего вывода.
10. **Безопасность повтора:** `DRAFT_reply.md:3,60` не поощряет ещё один
    свободный props-on arm, требует restraint/test stand и automatic cutoff и
    прямо говорит, что уже полученных данных достаточно. Это GO.

## Неблокирующее улучшение

`full-rate logging` в `DRAFT_reply.md:60` лучше заменить на `the highest log
rate the target can sustain without dropped iterations, with the same fields
and settings in both arms`. Без такой оговорки попытка 1:1 logging может сама
изменить loop load; для discriminator важнее matched, устойчиво записанный
rate, чем максимальный nominal rate.

## Publication verdict

**NO-GO сейчас. GO после трёх обязательных текстовых правок:**

1. `ANGLE` -> `ACRO` и удалить levelling-controller attribution;
2. заменить `matches exactly/few ms/collective leaves idle` точной хронологией;
3. уточнить timebase в таблице и `log 2/2` в instrumentation paragraph.

Сам draft не редактировался и не публиковался.

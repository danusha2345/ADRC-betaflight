# ADRC: ревизия и план исправлений

Этот файл — основной рабочий tracker для ревизии и исправления ADRC в
Betaflight. Все последующие изменения ADRC должны быть привязаны к одному из
пунктов ниже либо сначала добавлены сюда отдельным пунктом.

## Базовая точка

- Дата ревизии: 2026-07-11.
- Актуальный `upstream/master`: `6ecfb45f938e`.
- Основная локальная ветка: `codex/adrc-main-final-local`.
- Экспериментальная D-term ветка для стенда: `codex/adrc-dterm-final-local`.
- Проверенный head исходной ревизии: `a138a5dd19fe`.
- Локальный code head основной линии: `1b19666f6c5e`.
- Локальный code head D-term линии до этого обновления tracker:
  `ac4481674eaf`.
- Точно прошитый D-term firmware head: `c1f5b2e80888` (code head
  `ac4481674eaf` + pre-flash tracker commits).
- Post-bench evidence записан commit `a31f203d9b`.
- Config submodule обеих финальных линий: `57abd54d632d`.
- Официальный PR: [betaflight/betaflight#15400](https://github.com/betaflight/betaflight/pull/15400).
- Состояние PR при повторной проверке 2026-07-11: `OPEN`, `DRAFT`,
  `REVIEW_REQUIRED`, head по-прежнему `a138a5dd19fe`; локальные исправления в
  PR не отправлены.
- ОБНОВЛЕНИЕ (вечер 2026-07-11, по отмашке пользователя): remediation-серия
  ОТПРАВЛЕНА в PR force-push'ем — head `a138a5dd19` → `9d04e46d57` (rebase на
  `6ecfb45f93` + 15 remediation commits + `git rm` этого tracker из дерева
  PR) → `04813845dc` (fix ADRC-017). Бэкапы: fork `adrc-remediation-main`,
  `adrc-remediation-dterm`, `adrc-pr-push`. Отчётный комментарий:
  betaflight#15400 issuecomment-4947193088.
- Итог ревизии: **REQUEST CHANGES**.

Последний commit `a138a5dd19fe` меняет только комментарии. Функционально
текущему head соответствует `0079d685a2`, на котором основан release
`adrc-pr15400-b2`.

## Как вести этот файл

Статусы:

- `TODO` — работа не начата.
- `IN PROGRESS` — пункт взят в работу.
- `IMPLEMENTED` — код и доступные локальные проверки готовы, но остался
  внешний acceptance criterion: полёт, CI/matrix, release либо измерение на
  реальном контроллере.
- `BLOCKED` — продолжение требует отдельного решения или внешнего evidence.
- `DONE` — acceptance criteria выполнены и указан commit реализации.
- `DEFERRED` — осознанно отложено с записанной причиной.

Правила обновления:

1. Перед изменением кода поставить пункту статус `IN PROGRESS`.
2. Для каждого исправления сначала получить воспроизводящий тест или другой
   проверяемый критерий.
3. Исправление кода и его тесты фиксировать отдельным содержательным commit.
4. После commit обновить здесь статус, фактические проверки и поле
   `Implementation commit(s)`. Обновление tracker идёт следующим commit,
   поскольку commit не может надёжно содержать собственный SHA.
5. `DONE` ставить только после прохождения всех acceptance criteria пункта.
6. Если commit был rebased или squashed, до push заменить устаревший SHA.
7. Не смешивать в одном implementation commit независимые пункты без
   технической необходимости. Если смешивание неизбежно, один SHA указывается
   во всех затронутых пунктах.
8. После каждого изменения ADRC выполнять минимум:

   `make EXTRA_FLAGS=-Werror test_adrc_unittest test_pid_unittest`

9. Перед commit проверять `git diff --check`, `git status` и GitNexus
   `detect_changes`. Для изменяемых code symbols заранее выполнять GitNexus
   impact analysis.
10. Изменения не считать flight-validated, пока не указан точный firmware SHA,
    target, конфигурация и ссылка на лог.

## Карта веток и артефактов

| Линия | SHA | Роль | Использование |
|---|---:|---|---|
| `repo/master` | `4028af2aab` | Legacy inline ADRC и старые flight logs | Только evidence/reference |
| `adrc-toggle-fixes` | `d45d6b0c9c` | Ранний модульный вариант | История fixes |
| `adrc-review-fixes-2` | `71bd38ff95` | Промежуточные CLI/safety fixes | История fixes |
| `adrc-gate-fix` | `a797ada388` | Историческая доребейзная линия исправлений | Только reference |
| `codex/adrc-main-final-local` | `1b19666f6c` | Финальная основная линия, rebased на `6ecfb45f93` | Не push; локальная reviewed база |
| `codex/adrc-dterm-final-local` | `ac4481674e` | Финальная основная линия + opt-in D-term LPF, PG15 и EEPROM tests | Не push; выбранная линия стендовой прошивки |
| `codex/adrc-dterm-remediation` | `20b2685db0` | Доребейзная D-term remediation | Только reference |
| `adrc-dterm-lpf` | `665bbb1dc5` | Исходный небезопасный экспериментальный D-term LPF | Только reference, не прошивать |
| `pr15400-builds` | `69053ba918` | Release workflow поверх `0079d685` | Источник release b2 |

Remotes в этом workspace:

- `origin` — `Boyyt357/ADRC-betaflight`, исходный PoC.
- `fork` — `danusha2345/ADRC-betaflight`, рабочий fork.
- `bvandevliet` — fork автора официального PR.
- `upstream` — `betaflight/betaflight`.

Важно: `repo/master` настроен отслеживать `origin/master`, хотя совпадает с
`fork/master`. Поэтому отображаемое `ahead 49` не означает 49 новых commits
относительно рабочего fork.

## Подтверждённое состояние до исправлений

### Unit tests и сборки

На чистых временных worktree с `EXTRA_FLAGS=-Werror`:

| Ветка | ADRC tests | PID tests | Результат |
|---|---:|---:|---|
| `adrc-toggle-fixes` | 20/20 | 17/17 | PASS |
| `adrc-review-fixes-2` | 28/28 | 17/17 | PASS |
| `adrc-gate-fix` | 29/29 | 17/17 | PASS |
| `adrc-dterm-lpf` | 33/33 | 17/17 | PASS |
| `pr15400-builds` | 29/29 | 17/17 | PASS |

Ветка `adrc-dterm-lpf` также собирает target `STM32F405`. Успешная сборка не
устраняет проблему persisted layout из ADRC-006.

### GitHub CI

- Повторная проверка выполнена 2026-07-11 14:18 UTC.
- Текущий удалённый head PR `a138a5dd19fe221c34be1ac6bd40551fc9b44344`,
  recorded base `4e411ac3ce4fdb5952a21326e5185c29ef7f25fd`; текущий
  `upstream/master` уже `6ecfb45f938e4996fbb568b21eafa7057446a906`.
- GitHub сообщает `mergeable=true`, `mergeable_state=blocked`,
  `rebaseable=false`; запрошенный reviewer — `Quick-Flash`.
- В PR 13 conversation comments, 0 formal reviews и 0 inline review comments.
- Head PR имеет 53/53 зелёных checks.
- [Основной run 29113914811](https://github.com/betaflight/betaflight/actions/runs/29113914811)
  завершил 51/51 jobs, включая полный `test-all` и firmware matrix.
- `CodeRabbit / Review = success` не является независимым review: review был
  пропущен из-за draft-состояния.
- Формальных reviews и inline review threads нет.
- Ветки `adrc-dterm-lpf` и `adrc-toggle-fixes` не имеют собственных GitHub
  Actions runs.
- Release workflow не завершает shard ненулевым exit при единичной ошибке
  board build. Для b2 полнота отдельно подтверждена набором 623/623 assets.
- Локальные heads `1b19666f6c`/`ac4481674e` в GitHub CI не проверялись и ни в
  один remote не отправлялись; зелёные checks PR нельзя приписывать им.

### Flight evidence

- [Issue #1](https://github.com/danusha2345/ADRC-betaflight/issues/1)
  содержит основную историю полётов legacy inline ADRC. Эти логи нельзя
  напрямую считать валидацией текущего `adrc.c`.
- [Issue #2](https://github.com/danusha2345/ADRC-betaflight/issues/2)
  в основном содержит release/PR coordination и не добавляет независимых
  тестеров текущего head.
- PR-архитектура летала на pre-fix build `c1db438203`. Логи выявили false
  mid-air re-arm, Airmode limit cycle, слишком большое `b0` scaling и
  gate-open transient.
- Исправления `4ec9b282de`, `4b51833842` и `0079d685a2` после этих логов
  покрыты unit tests, но точный post-fix head ещё не перелётан.
- D-term LPF в полётном build был выставлен в `0`. Эффект включённого LPF
  flight-validated не был.
- Dedicated legacy fix-#8 A/B невалиден: обе стороны логов содержали один и
  тот же firmware revision с reverted gate fix.

### Артефакты

Локальный `ADRC_PR15400_DTERMLPF_MAMBAF722_I2C.hex`:

- SHA-256:
  `0c93140a5d0e21e14a19720974b27470178b232f71efb4bfab2bc5531e32365c`;
- embedded revision: `c1db43820`;
- persisted schema: PG13;
- старые defaults: re-arm `500 ms`, `b0 scale max=9`.

Этот hex устарел и не должен использоваться для проверки текущих fixes.

[Release b2](https://github.com/danusha2345/ADRC-betaflight/releases/tag/adrc-pr15400-b2)
основан на функциональном `0079d685a2` и предпочтительнее legacy/D-term
артефакта для контролируемых тестов. Он всё ещё содержит нерешённый
gate-open transition из ADRC-001.

## Локальное состояние после исправлений

Финальная основная линия `codex/adrc-main-final-local`:

- `c3311a0ba9` — feedback фактически доступной mixer authority и
  post-override throttle;
- `1bdfffcef1` — bumpless gate-open/re-open и невакуумные gate tests;
- `fc2b9cca4c` — disarmed-only semantics перехода CLASSIC↔ADRC;
- `1321ef4c1b` — независимые от classic D crash detection и подавление
  `I/z3` на полном recovery loop;
- `62fe21523a` — стабильный TD, loop-rate cap ESO, физические state limits и
  finite recovery, включая `-ffast-math`;
- `2e891d6f18` — feedback фактического yaw limit;
- `ab98b77127`, `72e47757e8`, `799ff89e60` — real-`mixTable()`, dynamic/EZ
  Landing и gate feedback epoch regression tests;
- `555f575a70` — обязательная повторная запись EEPROM после rejected/missing
  PG, включая default-only config;
- `ee9a153767` — bumpless yaw-spin recovery без скрытого `z3`;
- `7ade8d8089` — полный ADRC reset на каждом Crash Flip loop;
- `1b19666f6c` — публикация thrust-linearized collective в домене реально
  приложенной тяги.

Финальная D-term линия `codex/adrc-dterm-final-local` добавляет:

- `6791636cad` — opt-in `adrc_dterm_lpf_hz`, debug и blackbox metadata;
- `6da893a48b` — PG14 rejection, PG15 layout и перенос нового поля в конец
  `adrcProfile_t`;
- `121f09b176` — runtime cutoff transitions, corruption recovery и multi-axis
  debug tests;
- `ac4481674e` — реальный PG14→PG15 EEPROM reset/rewrite/reload и PG15
  multi-profile round-trip.

Rebase 38 ADRC-коммитов на `upstream/master` прошёл без конфликтов;
`range-diff` сохранил эквивалентность исходной серии. Ни одна финальная ветка
не отправлена в remote. Полётной валидации этих SHA нет.

Финальная локальная матрица после clean build/test:

| Линия | Mixer | ADRC | PID | PID+Gate E2E aggregate | `-ffast-math` | `test-all` | F405 | F411 | Mamba F722 |
|---|---:|---:|---:|---:|---|---|---|---|---|
| main `1b19666f6c` | 11/11 | 39/39 | 28/28 | 30/30 | PASS | PASS | PASS | PASS | PASS |
| D-term `ac4481674e` | 11/11 | 46/46 | 30/30 | 32/32 | PASS | PASS | PASS | PASS | PASS |

Оба `test-all` запускались после полной очистки с `EXTRA_FLAGS=-Werror`.
Целевые EEPROM/Mixer/ADRC/PID/Gate suites дополнительно прошли с
`EXTRA_FLAGS='-Werror -ffast-math'`: main EEPROM 2/2, D-term EEPROM 4/4.

Размеры clean D-term build `ac4481674e`:

| Target | Flash | RAM | Дополнительно |
|---|---:|---:|---:|
| `STM32F405` | FLASH1 625540/1015808 (61.58%) | RAM 101808/131072 (77.67%) | CCM 13636/65536 |
| `STM32F411` | FLASH1 473650/491520 (96.36%) | RAM 102932/131072 (78.53%) | flash headroom 17870 B |
| `MAMBAF722_I2C` | AXIM_FLASH1 387864/491520 (78.91%) | DTCM 30408/65536; SRAM1 56020/180224 | ITCM 16008/16384 (97.71%) |

Независимый source-order review после rebase нашёл три дополнительных
production blocker: yaw-spin hidden state, Crash Flip state learning и
thrust-linearization domain. Все три исправлены перечисленными выше commits;
повторный review default path, D-term delta и compile guards новых blocker не
нашёл.

## Сводный план

| ID | Приоритет | Кратко | Ветка | Статус | Implementation commit(s) |
|---|---|---|---|---|---|
| ADRC-001 | P0 | Bumpless liftoff gate open | final main | IMPLEMENTED | `1bdfffcef1`, `799ff89e60` |
| ADRC-002 | P0 | Crash detector без зависимости от classic D | final main | DONE | `1321ef4c1b` |
| ADRC-003 | P0 | ADRC I/z3 во время crash recovery | final main | DONE | `1321ef4c1b` |
| ADRC-004 | P0 | Устойчивая TD discretization | final main | DONE | `62fe21523a` |
| ADRC-005 | P0 | Loop-rate safe ESO | final main | DONE | `62fe21523a` |
| ADRC-006 | P0 | Persisted schema и EEPROM recovery для D-term LPF | final D-term | IMPLEMENTED | `6791636cad`, `6da893a48b`, `121f09b176`, `555f575a70`, `ac4481674e` |
| ADRC-007 | P1 | Фактически приложенный mixer feedback | final main | IMPLEMENTED | `c3311a0ba9`, `2e891d6f18`, `ab98b77127`, `72e47757e8` |
| ADRC-008 | P1 | Post-override throttle для ADRC | final main | DONE | `c3311a0ba9`, `ab98b77127`, `1b19666f6c` |
| ADRC-009 | P1 | State limits и finite-value defenses | final main | DONE | `62fe21523a` |
| ADRC-010 | P1 | Семантика CLASSIC↔ADRC handover | final main | DONE | `fc2b9cca4c` |
| ADRC-011 | P1 | Исправить vacuous gate tests | final main | DONE | `1bdfffcef1` |
| ADRC-012 | P1 | End-to-end tests и F411 cycle budget | final main/D-term | IMPLEMENTED | `ab98b77127`, `72e47757e8`, `799ff89e60`; F411 timing внешний |
| ADRC-013 | P1 | Rebase, CI, release b3 и точный re-flight | final main/D-term | IMPLEMENTED | rebase/local matrix готовы; official CI/release/flight внешние |
| ADRC-014 | P0 | Bumpless yaw-spin recovery | final main | DONE | `ee9a153767` |
| ADRC-015 | P0 | ADRC reset на всём Crash Flip | final main | DONE | `7ade8d8089` |
| ADRC-016 | P0 | Thrust-linearized collective feedback | final main | DONE | `1b19666f6c` |
| ADRC-017 | P0 | ADRC state/gate reset на переходе арма | PR line + final D-term | DONE | `04813845dc` (PR), `f4c809a12d` (D-term) |

## Детальные пункты

### ADRC-001 — Bumpless liftoff gate open

- Приоритет: **P0**.
- Статус: `IMPLEMENTED` — локально закрыто, flight criterion остаётся.
- Implementation commit(s): `1bdfffcef1`, `799ff89e60`.
- Затронутые места:
  - `src/main/flight/adrc.c`: gate transition, `lastOutput` и ESO update;
  - `src/test/unit/adrc_unittest.cc`;
  - при необходимости `src/test/unit/pid_unittest.cc`.

Finding:

При `liftoff=false → true` код в том же loop подключает
`b0 * lastOutput` к состоянию ESO без отдельного transition/priming/blend.
На pre-fix `btfl_001-AIR` первый gate open сопровождался примерно 1,3 с
осцилляции, motor saturation до 89% и gyro около ±145 deg/s. Уменьшение
`b0 scale max` снижает возможную амплитуду, но не устраняет сам разрыв.

Acceptance criteria:

- [x] Выбран и кратко документирован invariant перехода `closed → open`.
- [x] Добавлен regression test, который воспроизводит старый discontinuity на
      baseline `a138a5dd19` и проходит после исправления.
- [x] На первом открытом loop нет скачка только из-за подключения `b0u`.
- [x] `z1/z2/z3`, gyro filter и `lastOutput` переходят в согласованное
      состояние либо `b0u` вводится ограниченным blend.
- [x] Повторное открытие при opt-in re-arm покрыто тем же правилом.
- [x] ADRC/PID unit tests проходят с `-Werror`.
- [ ] После firmware build выполнен контролируемый Airmode takeoff test на
      точном SHA; ссылка на лог записана ниже.

Flight evidence после исправления: первый полёт `c1f5b2e808` 2026-07-11
(`blackbox/mamba/flash_2026-07-11_c1f5b2e808.bfl`, log 8): AIRMODE feature
включён, gate открылся по gyro-условию на отрыве (t = 11.11 s, pitch
20–26 deg/s около 50 ms), переход bumpless — axisP/axisD и моторы непрерывны,
без транзиента (у pre-fix `btfl_001-AIR` в этой же точке была ~1.3 s
осцилляция). Airmode takeoff criterion выполнен на точном SHA.

Принятое правило: при `closed → open` сохраняются `z1/z2/z3`, TD и gyro
filter, но `lastOutput` предыдущей grounded-эпохи обнуляется. Первый открытый
loop поэтому не подключает к ESO команду, которую зажатая землёй модель не
могла реализовать; mixer публикует уже новую airborne-команду для следующего
loop. Mutation/revert старого поведения ломает новые gate tests.

### ADRC-002 — Crash detector без зависимости от classic D

- Приоритет: **P0**.
- Статус: `DONE`.
- Implementation commit(s): `1321ef4c1b`.
- Затронутые места:
  - `src/main/flight/pid.c`;
  - `src/test/unit/pid_unittest.cc`.

Finding:

`detectAndSetCrashRecovery()` вызывается только внутри `if (Kd > 0)`.
В режиме ADRC classic D затем перезаписывается, но при `d_roll=0` или
`d_pitch=0` вместе с ним исчезает crash detection, включая путь
`GPS_RESCUE_MODE`.

Acceptance criteria:

- [x] При `pid_type=ADRC` crash detection не зависит от значения classic
      `Kd`.
- [x] Тест ADRC + `D=0` подтверждает вход в crash recovery.
- [x] Покрыт GPS Rescue crash-detection path.
- [x] Поведение classic PID не изменилось.
- [x] ADRC/PID unit tests проходят с `-Werror`.

### ADRC-003 — ADRC I/z3 во время crash recovery

- Приоритет: **P0**.
- Статус: `DONE`.
- Implementation commit(s): `1321ef4c1b`.
- Затронутые места:
  - `src/main/flight/pid.c`;
  - `src/main/flight/adrc.c` и `adrc.h` при необходимости;
  - `src/test/unit/pid_unittest.cc`.

Finding:

Crash recovery обнуляет `pidData.I`, но позднее в том же loop
`applyAdrcControl()` безусловно возвращает `I=-z3/b0`. При насыщенном `z3`
это может вернуть до полного `pidSumLimit`, который recovery пыталась убрать.

Acceptance criteria:

- [x] Определена политика ADRC state на входе, во время и при выходе из crash
      recovery.
- [x] Пока recovery требует нулевой I, ADRC не восстанавливает его позднее в
      том же loop.
- [x] Нет скачка I при выходе из recovery.
- [x] Unit test начинает с ненулевого/насыщенного `z3` и проверяет полный
      порядок вызовов одного PID loop.
- [x] Покрыты normal crash recovery и GPS Rescue.

Принятая политика: recovery-state latch действует на весь PID loop, `z3` и
выведенный из него `I` удерживаются в нуле, включая оси, вычисленные до поздно
обнаружившей crash оси. Первый чистый post-recovery loop тоже начинается без
старого disturbance trim.

### ADRC-004 — Устойчивая TD discretization и reset semantics

- Приоритет: **P0** при включённом `adrc_td_hz`.
- Статус: `DONE`.
- Implementation commit(s): `62fe21523a`.
- Затронутые места:
  - `src/main/flight/adrc.c`;
  - `src/main/cli/settings.c`;
  - `src/test/unit/adrc_unittest.cc`;
  - reset callers в `pid.c`/`mixer.c`.

Finding:

TD использует forward Euler:

`vRef += dT * 2πf * (setpoint - vRef)`.

Разрешённая комбинация PID loop `1.6 kHz` и `td=1000 Hz` имеет pole около
`-2.927` и доходит до `Inf` примерно за 48 ms. Кроме того,
`adrcResetState()` ставит `vRef=0`; повторный reset при 3D reversal не даёт
reference tracker развиваться и способен создавать saturated opposite output.

Acceptance criteria:

- [x] TD использует устойчивую для любого положительного `dT` discretization
      либо cutoff жёстко ограничен относительно loop rate.
- [x] Sweep всех разрешённых loop-rate/cutoff комбинаций остаётся finite.
- [x] Reset seed’ит `vRef` из физически согласованного текущего значения.
- [x] Повторные resets 3D reversal не создают opposite saturated command.
- [x] Добавлена защита/recovery от non-finite state.
- [x] `adrc_td_hz=0` остаётся точным bypass.

Решение: raw Euler заменён на монотонный PT1 gain
`omega*dT/(1 + omega*dT)`, а reset seed’ит `vRef` текущим gyro rate.

### ADRC-005 — Loop-rate safe ESO

- Приоритет: **P0** для разрешённых экстремальных конфигураций.
- Статус: `DONE`.
- Implementation commit(s): `62fe21523a`.
- Затронутые места:
  - `src/main/flight/adrc.c`;
  - `src/main/cli/settings.c`;
  - `src/test/unit/adrc_unittest.cc`.

Finding:

ESO использует forward Euler, `wo` разрешён до `600`. Для BMI270
`3.2 kHz` и `pid_process_denom=16` PID loop равен `200 Hz`. При `wo=600`
observer имеет spectral radius больше `2` и чередуется между state clamps.

Acceptance criteria:

- [x] Для каждого runtime `dT` существует проверяемая граница устойчивости.
- [x] Невозможна настройка `wo`, которая отправляет observer в rail-to-rail
      limit cycle в пределах поддерживаемых loop rates.
- [x] Unit sweep покрывает минимум 200 Hz, 1.6 kHz, 4 kHz и 8 kHz.
- [x] Проверены gated и airborne observer paths.
- [x] Default tune не изменён без отдельного обоснования.

Решение: effective observer bandwidth ограничен инвариантом
`wo*dT <= 0.5`; profile/default при этом не переписывается.

### ADRC-006 — Persisted schema для D-term LPF

- Приоритет: **P0**, блокирует использование `adrc-dterm-lpf`.
- Статус: `IMPLEMENTED` — schema локально безопасна, flight/release отсутствуют.
- Implementation commit(s): `6791636cad`, `6da893a48b`, `121f09b176`,
  `555f575a70`, `ac4481674e`.
- Ветка: `codex/adrc-dterm-final-local`.
- Затронутые места:
  - `src/main/flight/pid.h`;
  - `src/main/pg/pg_ids.h`/регистрация PID profile;
  - PG load/migration tests;
  - CLI и ADRC unit tests.

Finding:

`uint16_t dtermFilterHz` добавлен в середину persisted `adrcProfile_t`, но
`PG_PID_PROFILE` остаётся version 14. Размер `pidProfile_t` меняется
`266 → 268`, а массива профилей `1064 → 1072`. Loader при совпавшей version
raw-copy’ит старую запись, тихо смещая поля и границы профилей.

Динамическая проверка старой PG14 записи на новой структуре получила, среди
прочего, `dterm=5160`, `b0ThrottleScaleMax=100` и
`motorOutputLimit=0` при `LOAD_OK=1`.

Acceptance criteria:

- [x] Старые PG14 данные не могут быть тихо интерпретированы как новый layout.
- [x] Есть автоматический test старого serialized PG14 blob.
- [x] Явно выбрана стратегия: reset, migration или отдельный ADRC PG.
- [x] Учтено, что PG version занимает 4 бита, а version 15 — последнее
      доступное значение.
- [x] `pgStore`/reset/`pgLoad` round-trip сохраняет новый cutoff и соседние
      поля без смещения последующих профилей.
- [x] CLI save/reboot/load проверен на реальном Mamba EEPROM/config storage
      path; после минимум трёх reboot `diff all` совпадает 187/187 команд.
- [x] Новый отдельно маркированный hex собран только после прохождения теста:
      firmware `c1f5b2e808`, target `MAMBAF722_I2C`.
- [x] Старый `c1db43820` hex не распространяется как актуальный.

Предпочтительное направление: отдельный ADRC parameter group вместо
дальнейшего расходования version основного PID profile.

Локально выбрана безопасная краткосрочная стратегия PG15 reset: новое поле
перенесено в конец `adrcProfile_t`, registry version поднята `14 → 15`.
`pgLoad()` отклоняет blob PG14 размером 1064 bytes до копирования и сбрасывает
PID profiles в defaults; PG15 размером 1072 bytes проходит round-trip.

Критически важно: в штатном boot path один version mismatch делает весь
`readEEPROM()` неуспешным, после чего Betaflight выполняет полный config
reset/rewrite, а не только reset PID profiles. Поэтому до прошивки этой
экспериментальной ветки обязательно сохранить `diff all`. Отдельный ADRC PG
остаётся предпочтительной архитектурой перед включением функции в основной PR.

Независимый повторный review не нашёл code-correctness blocker. Остаточный
risk: даже при cutoff `0` две PT1-ступени остаются в hot path, а при включении
фильтр добавляет фазу в D/control path. На F411 D-term ветка добавляет 1228
bytes text и 48 bytes BSS к main и занимает 96.36% FLASH1.
Функция остаётся `off by default` до DWT 8 kHz и A/B blackbox/flight sweep.

### ADRC-007 — Фактически приложенный mixer feedback

- Приоритет: **P1**.
- Статус: `IMPLEMENTED` — основные uniform-scale paths и mixer E2E готовы;
  exact mixed-axis reconstruction осознанно не добавлена в realtime path,
  flight criterion остаётся.
- Implementation commit(s): `c3311a0ba9`, `2e891d6f18`, `ab98b77127`,
  `72e47757e8`.
- Затронутые места:
  - `src/main/flight/pid.c`;
  - `src/main/flight/mixer.c`;
  - ADRC/PID/mixer tests.

Finding:

`lastOutput` сохраняется после per-axis clamp, но до mixer normalization.
При `motorMixRange>1`, linear/legacy normalization и low-throttle attenuation
реальный actuator input меньше сохранённого. ESO принимает эту разницу за
disturbance и накапливает её в `z3`.

Acceptance criteria:

- [x] Для legacy/linear/EZ Landing observer получает приложенный uniform
      normalization/attenuation scale, включая effective yaw-spin limit.
- [x] Для `MIXER_DYNAMIC` real mixer test доказывает точный uniform scale;
      mixed-axis redistribution задокументирована как lumped disturbance.
- [x] Real-`mixTable()` tests покрывают legacy mixer, linear mixer и
      no-Airmode attenuation.
- [ ] Saturation test не вызывает ложный устойчивый drift `z3`.
- [x] Не добавлена циклическая зависимость PID↔mixer или лишняя задержка без
      документированного анализа.

Mixer публикует нормализованный command после constraint/normalization; ESO
использует его на следующем PID loop, что совпадает с прежней one-loop
семантикой `lastOutput`. При yaw-spin передаётся временный
`PIDSUM_LIMIT_MAX`, а не обычный `pidSumLimitYaw`. Для `MIXER_DYNAMIC`
сохранён documented approximation: uniform normalization учитывается, а
преднамеренная per-motor redistribution остаётся частью lumped plant
disturbance. Точная обратная реконструкция axis torque в hot path пока не
обоснована по cycle budget.

### ADRC-008 — Post-override throttle для ADRC

- Приоритет: **P1**.
- Статус: `DONE`.
- Implementation commit(s): `c3311a0ba9`, `ab98b77127`, `1b19666f6c`.
- Затронутые места:
  - `src/main/flight/adrc.c`;
  - `src/main/flight/mixer.c`;
  - tests автоматических режимов.

Finding:

`adrcUpdatePerLoopState()` читает `mixerGetThrottle()` до
`ALT_HOLD`/`GPS_RESCUE` throttle overrides. Gate и `b0` scheduling поэтому
моделируют pilot/pre-override throttle, а не реально приложенную тягу.

Acceptance criteria:

- [x] ADRC использует определённое post-override throttle значение.
- [x] Normal/manual mode сохраняет прежнюю семантику.
- [x] ALT_HOLD и GPS_RESCUE покрыты real-`mixTable()` tests.
- [x] Порядок вычислений явно задокументирован рядом с API.

`mixerThrottle` оставлен без изменения для blackbox/TPA. Отдельный
`mixerAdrcThrottle` публикуется после yaw-spin/launch/ALT_HOLD/GPS_RESCUE
override и mixer constraints; crash-flip/motor-stop публикуют нулевую
authority.

### ADRC-009 — State limits и finite-value defenses

- Приоритет: **P1**.
- Статус: `DONE`.
- Implementation commit(s): `62fe21523a`.
- Затронутые места:
  - `src/main/flight/adrc.c`;
  - profile validation/init;
  - `src/test/unit/adrc_unittest.cc`.

Findings:

- `ADRC_Z1_LIMIT=2000` почти равен максимальному setpoint и ниже
  поддерживаемого gyro range ±4000 dps.
- Corrupt/internal `b0ThrottleScaleMax=0` может дать `b0=0` и `0/0 → NaN`,
  несмотря на CLI minimum.
- Комментарий о одинаковых units `z1/z2/z3` неверен: это соответственно
  deg/s, deg/s² и deg/s³ для выбранной модели.

Acceptance criteria:

- [x] State bounds согласованы с реальным gyro FSR и command range.
- [x] Invalid persisted/internal parameters санитизируются до деления.
- [x] P/I/D и observer state восстанавливаются в finite domain; mixer clamp
      ограничивает итоговый `Sum`.
- [x] Тесты покрывают high-FSR gyro, zero/invalid `b0` и corrupt scale max.
- [x] Units в комментариях исправлены без изменения runtime semantics.

`z1` bound поднят до 8000 deg/s, profile coefficients имеют верхние и нижние
runtime bounds, а finite check читает IEEE-754 exponent напрямую и поэтому не
оптимизируется прочь при `-ffast-math`.

### ADRC-010 — Семантика CLASSIC↔ADRC handover

- Приоритет: **P1**, latent для stock runtime.
- Статус: `DONE`.
- Implementation commit(s): `fc2b9cca4c`.
- Затронутые места:
  - `src/main/flight/pid_init.c`;
  - `src/main/flight/adrc.c`;
  - `src/test/unit/pid_unittest.cc`;
  - публичная документация/PR wording.

Finding:

Старый PT2 zero-state kick уже исправлен: обе ступени filter seed’ятся и
`z1` согласован с gyro. Однако CLASSIC→ADRC transition обнуляет `z3`,
`lastOutput` и `vRef` и не переводит gate в airborne state. При спокойном
hover ниже liftoff threshold gate может оставаться закрытым неограниченно.

В stock Betaflight stick/MSP profile switch заблокирован при `ARMED`, поэтому
это не обычный полётный путь. Текущий тест и wording тем не менее создают
ожидание mid-air bumpless handover.

Acceptance criteria:

- [x] Принято явное решение: поддерживать runtime handover или удалить такое
      обещание из tests/docs.
- [x] Ветка «если handover поддерживается» неприменима: in-flight handover не
      поддерживается; disarmed switch test проверяет reset state и первый
      подготовленный control epoch вместо ложного mid-air обещания.
- [x] Если handover не поддерживается, API не создаёт ложной гарантии.
- [x] CLASSIC path после ADRC не получает скрытый ADRC I без принятой политики.

Принятое решение: stock Betaflight разрешает смену PID profile/controller law
только disarmed. На такой смене `pidResetIterm()` и ADRC gate/state reset
начинают новый arm epoch; same-type in-flight adjustment-range update сохраняет
observer state.

### ADRC-011 — Исправить vacuous gate tests

- Приоритет: **P1**, выполнять вместе с первым gate-related fix.
- Статус: `DONE`.
- Implementation commit(s): `1bdfffcef1`.
- Затронуто: `src/test/unit/adrc_unittest.cc`.

Finding:

`GateDoesNotChatterWithInvertedThresholds` явно ставит
`liftoffIdleHoldMs=0`, а `GateReArmStillnessIsCappedIndependently` наследует
default `0`. Это полностью выключает re-arm path, который тесты должны
проверять.

Acceptance criteria:

- [x] Оба теста используют ненулевой hold и реально входят в re-arm branch.
- [x] Mutation/revert проверка показывает, что регрессия cross-clamp или
      stillness cap ломает соответствующий тест.
- [x] Отдельно сохранён test, подтверждающий, что hold `0` отключает re-arm.

### ADRC-012 — End-to-end tests и F411 cycle budget

- Приоритет: **P1**.
- Статус: `IMPLEMENTED` — все доступные host/build/E2E проверки выполнены;
  точный 8 kHz cycle deadline требует реального F411.
- Implementation/test commit(s): `ab98b77127`, `72e47757e8`, `799ff89e60`,
  `121f09b176`, `ac4481674e`.

Обязательное покрытие:

- [x] Полный `pidController` ADRC path, а не только isolated `adrc.c`.
- [x] Первый gate open и opt-in re-arm через реальную цепочку
      `pidController → pidUpdateAdrcAppliedOutput → ESO` следующего loop.
- [x] Crash recovery и GPS Rescue.
- [x] Real-`mixTable()` normalization/saturation feedback для legacy/linear,
      no-Airmode, yaw-spin, motor-stop и crashflip.
- [x] Real-`mixTable()` ALT_HOLD/GPS_RESCUE throttle.
- [x] `MIXER_EZLANDING` и uniform normalization в `MIXER_DYNAMIC`; mixed-axis
      redistribution явно оставлена в lumped disturbance.
- [x] TD/ESO sweep по loop rates и граничным настройкам.
- [x] High-FSR gyro и non-finite recovery.
- [x] PG rejection/reset и round-trip для нового D-term layout.
- [ ] Cycle benchmark на F411 при 8 kHz с ADRC enabled/disabled.
- [x] Зафиксированы RAM/flash delta для generic F405/F411.
- [ ] Зафиксирован измеренный запас до 125 µs deadline и stack high-water mark.

Размеры clean final main head `1b19666f6c` относительно `a138a5dd19`:

| Target | Метрика | Baseline | Final | Delta | Остаток |
|---|---:|---:|---:|---:|---:|
| F405 | FLASH1 | 621420 | 624700 | +3280 B | 391108 B |
| F405 | RAM | 101756 | 101792 | +36 B | 29280 B |
| F405 | CCM | 13596 | 13600 | +4 B | 51936 B |
| F411 | FLASH1 | 469798 | 472422 | +2624 B | 19098 B |
| F411 | RAM | 102860 | 102884 | +24 B | 28188 B |

Обе generic firmware сборки проходят ARM GCC 13.3.1 с `-Werror`. Статический
assembly audit показал рост ADRC hot path (`pidController` на F405 примерно
+470 static instructions; F411 LTO `taskMainPidLoop` примерно +539), но это
не executed cycles. На F411 при 8 kHz бюджет равен 125 µs, поэтому verdict по
deadline: **NOT PROVEN, MEDIUM risk**. Нужен DWT `CYCCNT`/scheduler timing на
реальном F411 с exact target/config, ADRC и classic, worst-case logging/features.
Host x86 benchmark для такого verdict непереносим и намеренно не выдаётся за
hardware evidence.

### ADRC-013 — Rebase, CI, release b3 и точный re-flight

- Приоритет: **P1**, финальный integration gate.
- Статус: `IMPLEMENTED` локально; official CI, release и полёт остаются
  внешними acceptance criteria.
- Локальные integration heads: main `1b19666f6c`, D-term `ac4481674e`.

Acceptance criteria:

- [x] Обе финальные ветки rebased на `upstream/master` `6ecfb45f93`.
- [x] `src/config` обновлён до `57abd54d632d`.
- [x] `git diff --check` чист на локальных heads.
- [x] Полный `make EXTRA_FLAGS=-Werror test-all` проходит локально.
- [x] Clean generic F405/F411 и exact `MAMBAF722_I2C` builds проходят с
      `-Werror` на обеих финальных линиях.
- [x] Exact D-term firmware `c1f5b2e808` прошит на Mamba, config восстановлен,
      минимум три reboot и 8 kHz hot-loop bench прошли без зависаний/late.
- [ ] Официальная firmware matrix проходит.
- [ ] Release workflow либо падает при любом board failure, либо полнота
      artifacts проверяется отдельным обязательным job.
- [ ] Создан release b3 для точного reviewed SHA.
- [ ] Проверены Airmode first takeoff, zero-throttle catch, throttle punches,
      sustained saturation, crash recovery/GPS Rescue и несколько loop rates.
- [ ] Для каждого лога записаны SHA, target, diff конфигурации и verdict.
- [ ] Только после этого PR снимается с draft.

Rebase выполнен реально, без конфликтов. `range-diff` подтвердил эквивалентность
38-коммитной ADRC-серии, затем поверх неё добавлены локальные E2E/EEPROM/state
fixes. Официальный PR всё ещё указывает на старый `a138a5dd19`; локальные
проверки не заменяют upstream CI.

### ADRC-014 — Bumpless yaw-spin recovery

- Приоритет: **P0**.
- Статус: `DONE`.
- Implementation commit(s): `ee9a153767`.

Finding: во время yaw-spin recovery наружный I term был равен нулю, но
внутренний `z3` продолжал жить. После снятия recovery первый обычный loop мог
вернуть скрытое disturbance скачком вплоть до `pidSumLimit`.

Acceptance criteria:

- [x] `z3` обнулён до и после ESO update на всём recovery epoch.
- [x] Первый loop после выхода не возвращает stale I/disturbance.
- [x] `lastOutput` остаётся реально приложенной командой для rate observer.
- [x] Mutation старого поведения воспроизводит kick; regression проходит в
      обычной и `-ffast-math` матрице.

### ADRC-015 — ADRC reset на всём Crash Flip

- Приоритет: **P0** для `crashflip_auto_rearm=ON`.
- Статус: `DONE`.
- Implementation commit(s): `7ade8d8089`.

Finding: ESO мог обучиться скрытой turtle-команде и открыть liftoff gate. При
автоматическом re-arm выход из Crash Flip возможен без disarm и старый state
мог попасть в первый обычный loop.

Acceptance criteria:

- [x] При ADRC state/gate/terms/Sum сбрасываются на каждом Crash Flip loop.
- [x] Auto-rearm начинает обычный control epoch с чистого state.
- [x] Classic PID path не изменён.
- [x] Сохранённая Mamba имеет `crashflip_auto_rearm=OFF`, но общий latent path
      всё равно закрыт.

### ADRC-016 — Thrust-linearized collective feedback

- Приоритет: **P0** для `thrust_linear > 0`.
- Статус: `DONE`.
- Implementation commit(s): `1b19666f6c`.

Finding: при сохранённом `thrust_linear=20` mixer публиковал inverse-
compensated throttle `0.352`, хотя реальный collective составлял примерно
`0.40032`. Из-за этого 40% liftoff gate фактически сдвигался примерно к 45%,
а `b0` scheduling недооценивал приложенную тягу.

Acceptance criteria:

- [x] ADRC получает guarded forward-linearized constrained collective.
- [x] `motorStopped` по-прежнему публикует нулевые throttle и authority.
- [x] Real mixer test с target-equivalent thrust formula проходит 11/11.
- [x] Mutation старого feedback-domain поведения ломает 10 из 11 tests.

Для TL с ненулевым axis mix средний физический collective остаётся нелинейным;
публикуется base collective, а residual рассматривается как lumped disturbance.
На текущей Mamba используется `MIXER_LEGACY`, не `MIXER_DYNAMIC`.

### ADRC-017 — ADRC state/gate reset на переходе арма

- Приоритет: **P0**.
- Статус: `DONE`.
- Implementation commit(s): `04813845dc` (PR line), `f4c809a12d` (D-term
  cherry-pick). Rising-edge reset в `updateAdrcSharedState()` по
  `ARMING_FLAG(ARMED)` (новое поле `pidRuntime.adrcWasArmed`), независим от
  `pid_at_min_throttle`.
- Затронутые места:
  - `src/main/fc/core.c` (`tryArm()`/disarm path) либо arm-transition hook в
    `src/main/flight/pid.c`;
  - `src/test/unit/pid_unittest.cc` / gate E2E suite.

Finding:

При штатном дефолте `pid_at_min_throttle = ON` поле
`pidRuntime.pidStabilisationEnabled` остаётся true и в disarm, поэтому ветка
`!pidStabilisationEnabled` в `pidController()` — единственный вызов
`adrcResetAllState()` и единственное место закрытия liftoff gate — мёртвый
код. `tryArm()` не сбрасывает ни classic I, ни ADRC. Gate и ESO state живут
сквозь disarm неограниченно. Инвариант в комментарии
`adrcZeroThrottleItermReset()` («живой ESO не может намотаться на земле —
gate держит b0*u в нуле») ломается, как только gate открыт на земле: контур
публикует выход, моторы его не прикладывают, разница уходит в z3.

Evidence:

- USB-стенд 2026-07-11 (`msp_capture.py`, RX выключен): gate latched open
  85 s в disarm (строки d7 = +100 при throttle < 35 % исключают per-loop
  пересчёт), z3 на клипе ±524k.
- Полёт `c1f5b2e808` (логи 8–9, интервал между армами 1.6 s): log 8 — на
  посадке с открытым gate z3-roll намотался до ≥524k rail; disarm его НЕ
  очистил; log 9 — gate открыт с первого сэмпла, z3-roll ≈ 128k (I ≈ 32)
  въехал в новый арм. Здесь исход benign (z3 распался за ~2 s до подъёма
  газа, взлёт 7 deg/s uncommanded), worst case — мгновенный ре-арм + punch
  с I до ~131 (26 % pidSumLimit); защита от наземной намотки отсутствует для
  каждого арма после первого за power cycle.

Acceptance criteria:

- [x] На переходе disarm→arm сбрасываются per-axis ESO state и liftoff gate
      (новый arm epoch), независимо от `pid_at_min_throttle`.
- [x] Regression test (`testAdrcArmTransitionStartsFreshEpoch`): открытый
      gate + z3 = 1e5 перед повторным армом → после арма gate закрыт, z3 = 0;
      проверено stash-прогоном, что тест падает на pre-fix head.
- [x] Semantics «gate открыт от первого liftoff до disarm» выполняется
      буквально (не «до конца power cycle»).
- [x] Mid-flight пути (`pidResetIterm`, launch control, 3D reversal) не
      затронуты — reset только на rising edge армed-флага.
- [x] Suites с `-Werror`: PR line — PID 29, ADRC 39, gate E2E aggregate 31,
      mixer 11; D-term line — PID aggregate 31, ADRC 46. F405 firmware build
      проходит.
- [ ] Полётная проверка ре-арма на исправленном билде (второй арм в сессии
      должен начинаться с закрытым gate и z3 = 0 в первом сэмпле лога).

## Mamba F722: backup, прошивка и стендовая проверка

Контроллер: `MAMBAF722_I2C`, STM32F722, стабильный USB path
`/dev/serial/by-id/usb-Betaflight_Betaflight_-_MAMBAF722_I2C_203E39564638-if00`.
Исходная прошивка:
2026.6.0-alpha `c1db43820`, config revision `9e1bee9`. LiPo не подключён;
моторные и полётные проверки запрещены в этом этапе.

Сохранённые файлы до прошивки находятся в
`.scratch/bench/mambaf722_i2c_2026-07-11/`:

| Файл | Строк | SHA-256 |
|---|---:|---|
| `diff_all_c1db43820.txt` | 242 | `c48b033c463dc3ae6e46b7d71b5031920b4785d609896c6585d274775744b52e` |
| `dump_all_c1db43820.txt` | 1474 | `ddff3ec79f8355249be3e9ba5fd5ac011ca522c32b740b267050a1a3e37db6a9` |
| `baseline_c1db43820.txt` | 165 | `4233b7ac5c8f9dd616e3325170c6aeedad0979c1db89b605f8402213ac2c2705` |
| `restore_cli.txt` | 231 | `8a0d012014bf51bad50857cacbf4a7e9120e0bef058bd381f8ac2ed6d997988d` |

Restore audit: все 143 `set` names и все 16 CLI command types существуют в
точной новой Mamba сборке. Target config между revisions не менялся. В restore
сохранены user-specific feature/serial/beacon/aux/vtxtable/settings, но
намеренно не возвращаются старые небезопасные defaults `hold=500` и
`b0 scale max=9`; остаются новые `0` и `3`. D-term cutoff остаётся `0`.

Контрольная конфигурация для сверки после restore: profile 0, `pid_type=ADRC`,
8 kHz gyro/PID (`pid_process_denom=1`), DSHOT600, bidirectional DSHOT off,
`MIXER_LEGACY`,
`thrust_linear=20`, `crashflip_auto_rearm=OFF`, `pid_at_min_throttle=ON`.
ADRC: `wc=40`, `wo=120`, `b0=4000` на всех осях, gyro LPF 150 Hz,
hover 35%, sigma 3, TD 0, liftoff throttle 40%, gyro 20 dps, hold 25 ms,
idle throttle 5%, gated decay 200 ms, D-term LPF 0.
После reset намеренно должны остаться новые безопасные
`adrc_liftoff_idle_hold_ms=0` и `adrc_b0_scale_max=3`, а не старые 500/9;
`debug_mode=ADRC_DTERM` возвращается restore script.

Старый 8 kHz scheduler baseline: CPU 43%, cycle time 124 µs, GYRO avg/max
2/5 µs, FILTER 9/17 µs, PID 41/59 µs, late 0. Питание только USB:
0S, около 0.44 V, LiPo отсутствует.

PG14→PG15 не является PID-only migration: rejected PG делает весь
`readEEPROM()` неуспешным, Betaflight выполняет полный reset и rewrite.
Поэтому восстановление `restore_cli.txt` после первого boot обязательно.

Стендовый чек-лист:

- [x] Сохранены и хэшированы `diff all`, полный `dump all`, baseline и
      очищенный restore script.
- [x] Restore script проверен против exact ELF и не возвращает старые unsafe
      defaults.
- [x] Clean exact `MAMBAF722_I2C` build проходит с `-Werror`.
- [x] `git diff --check` чист, tracker commits локальны; GitNexus обновлён до
      tracker head и показывает актуальный индекс.
- [x] Собран и хэширован exact firmware после commit pre-flash tracker.
- [x] Выполнена DFU-прошивка выбранной D-term ветки.
- [x] Восстановлен CLI config без `###ERROR`/batch errors.
- [x] Сверены target, firmware/config SHA, ADRC tune, serial/features/aux/VTX,
      mixer/thrust/crashflip settings и `diff all`.
- [x] Выполнены минимум три последовательных reboot/reconnect без зависания.
- [x] Несколько снимков `tasks` показывают hot-loop late 0 и PID max ниже
      125 µs; измеримый рост PID/FILTER load сопоставлен с baseline ниже.
- [x] Полётная проверка выполнена пользователем 2026-07-11: два арма, indoor
      hover (логи 8–9 в `blackbox/mamba/flash_2026-07-11_c1f5b2e808.bfl`,
      flash после скачивания стёрт). Насыщения моторов 0.0 % в обоих логах,
      z1-трекинг corr 0.997 при лаге 2.5 ms (roll), b0 scale корректно 1.0
      (газ ниже hover 35 %), bumpless gate open подтверждён (ADRC-001).
      Оба лога дописаны полностью; на flash оставалось ~1 MB (~13 s) — на
      грани. Полёт также воспроизвёл ADRC-017 (см. секцию выше): gate и
      z3 ≈ 128k пережили disarm и въехали во второй арм.

Фактический стендовый результат:

- Прошит firmware `c1f5b2e8088821d4768381de086ae57d34af059d`, config
  `57abd54d632d8ec93dbbe14193de0a521c45185c`, target `MAMBAF722_I2C`.
- DFU записал оба element (480 и 387864 bytes) полностью и завершился с
  exit code 0; VCP вернулся штатно.
- HEX SHA-256:
  `a2dbe3c883471374b875877e161680eea9b8810cc685c4bb27a9af4d18fa3a79`.
- DFU SHA-256:
  `ef07f4df7c566e5838d29abef7548a562f34b8e06d16e8429a41aeb795f5f15f`.
- ELF SHA-256:
  `0e0abcdca86b6f5aca9dab9bf552c3c723dff6b30ab98828d92d41a317b2c261`.
- Restore output: 441 строк, SHA-256
  `44986a21c7f69e5d7e2f535430b824360bea1a8c5198ca6a3b567b16aa81b1e6`;
  `###ERROR`, unknown/invalid command и batch errors отсутствуют.
- После persistence/reboot текущий `diff all` машинно сравнен с
  `restore_cli.txt`: expected 187 commands, observed 187, missing 0, extra 0.
- Reboot logs SHA-256: `bfbc5fd579d8be5f338b9b57279ec83ca9c6a38a828b56fa2db7a0c8c38c8b39`,
  `fc0edc73d40747f01d525acdb1d48177fa7f6a947ea6eda2648344f9bccec7c4`,
  `5abcd3406f56caf43ea8d36dc70b307e00b26e471474426d2637431e8f939664`;
  финальный контрольный лог
  `0fee9b03357838f2bccc3e12e9c7eeb15368c4105061b99f7a2c63b033c573e9`.

Стабильные 8 kHz snapshots после restore:

| Snapshot | CPU | GYRO avg/max | FILTER avg/max | PID avg/max | GYRO/FILTER/PID late |
|---|---:|---:|---:|---:|---:|
| baseline `c1db43820` | 43% | 2/5 µs | 9/17 µs | 41/59 µs | 0/0/0 |
| reboot 1 `c1f5b2e80` | 49% | 2/5 µs | 9/20 µs | 52/74 µs | 0/0/0 |
| reboot 2 `c1f5b2e80` | 49% | 2/6 µs | 9/15 µs | 49/68 µs | 0/0/0 |
| reboot 3 `c1f5b2e80` | 49% | 2/6 µs | 8/15 µs | 48/69 µs | 0/0/0 |
| final, uptime 69 s | 49% | 2/6 µs | 9/15 µs | 48/74 µs | 0/0/0 |

Вывод: зависаний/reconnect failures и пропусков hot loop не обнаружено.
Финальный D-term build с cutoff 0 показывает PID avg выше старой прошивки
примерно на 7–11 µs и CPU выше примерно на 6 процентных пунктов. Это не
изолированный A/B только для cutoff: между firmware есть и остальные ADRC/
upstream изменения. Наблюдавшийся PID max 74 µs остаётся ниже 124–125 µs
cycle deadline на F722. Это стенд без LiPo, движения и полёта; flight verdict
из этих измерений не выводится.

## Порядок выполнения

Рекомендуемая последовательность:

1. ADRC-001 и ADRC-011 — gate transition и реальные regression tests.
2. ADRC-002 и ADRC-003 — crash recovery.
3. ADRC-004 и ADRC-005 — TD/ESO stability.
4. ADRC-009 — finite/state defenses.
5. ADRC-007 и ADRC-008 — фактический actuator/throttle feedback.
6. ADRC-010 — зафиксировать поддерживаемую handover semantics.
7. ADRC-014, ADRC-015 и ADRC-016 — recovery/Crash Flip/thrust-domain state.
8. ADRC-012 — end-to-end coverage и cycle budget.
9. ADRC-006 — перенос fixes в D-term branch и безопасная PG schema/EEPROM.
10. ADRC-013 — rebase, полный CI, b3 и flight validation.

ADRC-006 ведётся отдельно от основного PR, пока D-term LPF не принят в scope
PR #15400.

## Журнал завершённых работ

Добавлять строку после каждого implementation commit.

| Дата | ID | Статус | Implementation commit | Проверки | Примечание |
|---|---|---|---|---|---|
| 2026-07-11 | ADRC-007,008 | IMPLEMENTED/DONE | `c3311a0ba9` | ADRC/PID, F405 | Applied mixer scale и post-override throttle |
| 2026-07-11 | ADRC-001,011 | IMPLEMENTED/DONE | `1bdfffcef1` | ADRC/PID, mutation | Новый actuator-feedback epoch на gate open/re-open |
| 2026-07-11 | ADRC-010 | DONE | `fc2b9cca4c` | PID handover tests | Disarmed-only transition semantics |
| 2026-07-11 | ADRC-002,003 | DONE | `1321ef4c1b` | ADRC 39/39, PID | D=0, GPS Rescue, late-axis crash, bumpless exit |
| 2026-07-11 | ADRC-004,005,009 | DONE | `62fe21523a` | normal/`-ffast-math`, F405/F411 | TD/ESO/finite/state hardening |
| 2026-07-11 | ADRC-007 | IMPLEMENTED | `2e891d6f18`, `72e47757e8` | real mixer normal/`-ffast-math` | Effective yaw limit, dynamic и EZ Landing feedback |
| 2026-07-11 | ADRC-007,008,012 | IMPLEMENTED | `ab98b77127`, `799ff89e60` | mixer 11/11, gate main 30/30 | Real mixer и полный feedback epoch E2E |
| 2026-07-11 | ADRC-006 | IMPLEMENTED | `6791636cad`, `6da893a48b`, `121f09b176` | ADRC 46/46, PID 30/30 | D-term opt-in, PG15 и runtime transitions |
| 2026-07-11 | ADRC-006 | IMPLEMENTED | `555f575a70`, `ac4481674e` | EEPROM 4/4, `test-all` | Rejected PG принудительно переписывается и чисто reload'ится |
| 2026-07-11 | ADRC-014 | DONE | `ee9a153767` | mutation, PID/ADRC/gate | Скрытый yaw-spin `z3` не возвращается после recovery |
| 2026-07-11 | ADRC-015 | DONE | `7ade8d8089` | PID, mutation | Чистый auto-rearm epoch после Crash Flip |
| 2026-07-11 | ADRC-016 | DONE | `1b19666f6c` | mixer 11/11, mutation 10 failures | Feedback в домене реально приложенной thrust-linearized тяги |
| 2026-07-11 | ADRC-001,013 | flight evidence | — | Логи 8–9 `c1f5b2e808` | Airmode-взлёт bumpless, z1 corr 0.997/2.5 ms, saturation 0 %, оба лога целы |
| 2026-07-11 | ADRC-017 | TODO (finding) | — | USB-стенд + логи 8–9 | Gate/ESO переживают disarm (`pid_at_min_throttle=ON` делает reset-ветку мёртвой); z3 ≈ 128k въехал во 2-й арм |
| 2026-07-11 | ADRC-017 | DONE | `04813845dc`/`f4c809a12d` | PID 29, gate E2E 31, ADRC 39/46, F405 | Rising-edge reset на арме; characterization-тест падает на pre-fix head |
| 2026-07-11 | ADRC-013 | IMPLEMENTED | main `1b19666f6c`, D-term `ac4481674e` | clean `test-all`, fastmath, F405/F411/Mamba | Rebase/local integration готовы, push отсутствует |
| 2026-07-11 | ADRC-006,012,013 | IMPLEMENTED | firmware `c1f5b2e808`; evidence `a31f203d9b` | DFU, exact restore 187/187, 3+ reboot, 8 kHz tasks | Mamba bench без LiPo/моторов; flight остаётся внешним |

## Принятые решения и остаточные блокеры

1. Gate open: сохранить observer/filters, обнулить только grounded-эпоху
   `lastOutput`; новый applied output приходит от mixer на следующий loop.
2. Crash recovery: на весь recovery loop и первый clean handoff подавлять
   disturbance trim через `z3=0`/`I=0`, не останавливая rate observer.
3. ESO: ограничивать effective `wo*dT <= 0.5`; TD использовать стабильный PT1.
4. D-term LPF: для локальной экспериментальной ветки использовать PG15 reset;
   перед основной интеграцией предпочесть отдельный ADRC PG.
5. Observer feedback: delayed applied command предыдущего mixer loop; для
   uniform mixer modes передавать normalization scale. `MIXER_DYNAMIC`
   per-motor redistribution пока остаётся lumped disturbance.
6. CLASSIC↔ADRC: только disarmed transition; mid-air гарантия удалена.
7. Exact `MIXER_DYNAMIC` mixed-axis redistribution и nonlinear TL residual не
   реконструируются обратно в axis torque: они осознанно остаются lumped
   disturbance; для текущей Mamba активен legacy mixer.
8. До `DONE` по ADRC-001/006/007/012/013 нужны: F411 DWT timing/stack
   high-water, upstream CI/release и полётные логи точного firmware SHA.
9. Integrated yaw, tricopter и fixed-wing authority не валидированы; на
   текущей Mamba integrated yaw выключен.
10. Вне ADRC scope найдено, что CLI display config size в `config_eeprom.c`
    двигает pointer на `sizeof(storedCrc)`, а не `sizeof(*storedCrc)`. Это не
    затрагивает load/write/CRC и оставлено `DEFERRED` как отдельная задача.

# ADRC b10: интеграция с Betaflight master 2026-08-28

## Исходная линия

b10 — не простой rebase PR #15400. В отдельной ветке
`codex/adrc-upstream-20260828` объединены:

- ветка b9 + ADRC-029 на `b82a9e16bd`;
- актуальный на момент интеграции `betaflight/master` `e8580ad977` — 118
  upstream-коммитов после общей базы `6ecfb45f93`;
- точная Blackbox-наблюдаемость ADRC, адаптированная из `aa93b5e680` к
  трёхветочному liftoff gate b9.

Граф опубликован как merge `fe7355e635`, перенос observability —
`98bbff99ab`, release tag `adrc-pr15400-b10` указывает на `343572dcba`.
Ветка автора PR `adrc-toggle` не переписывалась: это fork-side интеграция для
проверки новой базы, а не молчаливое решение за автора о способе посадки 118
upstream-коммитов в PR.

## Что пришлось решить при слиянии

1. **PID profile PG.** Upstream использует версию 12 без `adrcProfile_t`, b9
   использует обёрнутую версию 0 с другой структурой. b10 использует новую для
   обеих линий версию 13. PID-профили при первом запуске намеренно
   сбрасываются: побайтовое сохранение любой из несовместимых структур было бы
   опаснее потери настроек.
2. **Debug enum.** Upstream добавил `DEBUG_PITOT` в тот же ordinal, где b9 уже
   имел `DEBUG_ADRC`. В b10 сохранён ordinal b9 для `DEBUG_ADRC`, а
   `DEBUG_PITOT` добавлен после него, чтобы сохранённый конфиг тестера не
   переключился молча с ADRC на PITOT.
3. **Integrated Yaw.** Upstream удалил Integrated Yaw. Мёртвая условная ветка
   ADRC crash-recovery удалена; обычный ADRC sum и bumpless-вычитание I-канала
   сохранены.
4. **Serial configuration.** Upstream завершил переход от записываемого
   `serial ...` bitmask к per-feature `*_uart`/`*_baud`. Старый `serial ...`
   теперь только синтезированное read-only представление. Поэтому старый
   `diff all` нельзя вставлять целиком без проверки RX/MSP/Blackbox/VTX/GPS.
   Релизный Configurator 2026.6.1 предшествует firmware API 1.49; поддержка
   находится в configurator master (`betaflight/betaflight-configurator#5420`,
   `betaflight/betaflight-configurator#5451`,
   `betaflight/betaflight-configurator#5452`). В нём Ports
   намеренно read-only, а назначения находятся на вкладках функций; запасной
   полный путь — CLI `set <feature>_uart = <PORT>`.
5. **Targets/config repo.** Generic targets переименованы
   `STM32F7X2 -> STM32F722` и `STM32G47X -> STM32G474`, а board configs теперь
   лежат в `configs/<manufacturer>/<board>`. Старый release workflow не видел
   ни одной board config; b10 перечисляет 629 листовых `config.h` и делит их
   между 40 shards.
6. **Autopilot/mixer.** В upstream существенно переписаны Position Hold, GPS
   Rescue и flight-plan/autopilot. ADRC по-прежнему берёт commanded collective
   после automatic-mode override и до mixer headroom, applied collective —
   после mixer adjustment. Существующие ALT_HOLD/GPS_RESCUE/mixer
   characterization tests и новые upstream autopilot suites проходят.

## Новая наблюдаемость

При `pid_type = ADRC` и `debug_mode = ADRC` Blackbox пишет значения именно того
PID-цикла, который они описывают:

- `adrcPidSum[0..2]` — прямой финальный `pidData[].Sum`, не реконструкция из
  округлённых P/I/D/F;
- `adrcCommandedCollective` и `adrcAppliedCollective`;
- `adrcState`: liftoff, throttle-idle, фактически подавленные оси роста `z3` и
  причина открытия gate (`commanded`, `gyro`, `applied`);
- `adrcGateResetCount` — счётчик вызовов reset gate;
- `adrc_z3_log_scale` из ADRC-029. Для старых логов без заголовка остаётся
  legacy divisor 16.

## Проверка до публикации

- `make EXTRA_FLAGS=-Werror checks` — PASS.
- Полный `make EXTRA_FLAGS=-Werror test-all` — PASS, 74 test suites.
- После полного `make clean` собраны generic `STM32F411`, `STM32F446`,
  `STM32F722`, `STM32G474`, а также `MAMBAF722_I2C` и `BETAFPVG473_V2`.
- Все ADRC-сборки содержат новые Blackbox fields; F446 ожидаемо не содержит
  ADRC.

Запасы памяти уже требуют контроля:

| target | критичный регион | использовано | остаток |
|---|---|---:|---:|
| generic STM32F411 | FLASH1 | 97.09% | около 14 KiB |
| generic STM32F446 (без ADRC) | FLASH1 | 99.62% | около 1.8 KiB |
| generic STM32F722 | AXIM_FLASH1 / ITCM | 97.75% / 96.48% | ITCM 576 B |
| MAMBAF722_I2C | ITCM | 96.88% | 512 B |

Любой overflow конкретной платы в release matrix — реальная несовместимость,
а не предупреждение, которое можно игнорировать.

## Результат release matrix

[GitHub Actions run 33166958162](https://github.com/danusha2345/ADRC-betaflight/actions/runs/33166958162)
завершился `success`. Повторная выборка raw logs всех 40 shards дала ровно
`615 OK`, `0 FAIL`, `14 SKIP` (SITL/RP2350 и targets с отдельными platform
SDK/output). Релиз содержит 630 уникальных assets: 615 board-specific и 15
generic; старых имён `STM32F7X2`/`STM32G47X` в нём нет.

Четыре опубликованных hex скачаны обратно, преобразованы из Intel HEX в binary
и проверены по встроенной revision-строке. Все содержат tag revision
`343572dcb`; три ADRC-target содержат новые observability fields, F446 — нет,
как и должно быть.

| asset | SHA-256 | ADRC observability |
|---|---|---|
| generic STM32F411 | `484e12c04ab9e980416497811124249e4f51fac22f61e3dbe1a4cc89a97ea7eb` | да |
| generic STM32F446 | `812cc480b0f73121ea2cfa33688f2ec020bfc0325c57a696cf66e50f15dc382a` | нет |
| MAMBAF722_I2C | `1fa8a40d7e7989244400be7996e55d811e95857bea60aa4cd154fc649f706cc7` | да |
| BETAFPVG473_V2 | `6497b483dbc6d19302258640d219001c1950080e37bdd8bce5a70968f6307ccb` | да |

## Явно не входит в b10

- выбор production/default между LINEAR и SQRT для b0 law;
- автоматическое понижение настроек при самовозбуждении — защита отложена;
- изменения частоты ELRS;
- утверждение универсального безопасного `wo` или production tune;
- новый обязательный flight matrix: дальнейшие проверки выбирают сами
  тестеры;
- аппаратный F411 8 kHz DWT benchmark.

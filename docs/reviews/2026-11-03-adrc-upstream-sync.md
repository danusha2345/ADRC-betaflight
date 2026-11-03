# Синхронизация ADRC с Betaflight master — 3 ноября 2026

## Результат

Локальная ветка/bookmark `adrc-sync-20261103`, merge-коммит
`a7c9d13995dc4fc5297d1aa5f840b9b33dbe2748`.
Родители: PR #15400 `912827d69ec26120fdfdaac47b33c022c3073bc3` и upstream master
`c5102518911f6ac4820e4656221a9deccf77e967`. Внесены все 55 новых upstream-коммитов.
Рабочее дерево: `/home/danik/storage/adrc-sync-1009`, повторно использовано существующее
место синхронизаций. Подключён JJ; существующие `tools` и содержимое `src/config`
не включены в merge как посторонние локальные изменения. Другой docs-worktree не затронут.
Ветка опубликована на GitHub, GitLab и Forgejo; открыт [PR Бобу #6](https://github.com/bvandevliet/betaflight/pull/6).

## Что пришлось адаптировать

1. `pid.c`: upstream #15920 устраняет повторное умножение сохранённого результата
   anti-gravity фильтра на gain, когда Crash Flip не подаёт новых данных. Сохранил
   локальную переменную upstream `antiGravityThrottleD` и проверку CLASSIC/ADRC:
   классика получает исправленный P boost, ADRC по-прежнему его пропускает.
2. `mixer.c`: объединил комментарий/ранний выход upstream с обнулением двух
   ADRC collective, обратной связи по приложенному выходу и saturation state при
   Crash Flip. Эта ветка не должна передавать turtle-команды в ESO.
3. `adrc_mixer_unittest.cc`: после upstream #15837 `rcData` уже в диапазоне −1…1.
   Исправил helper (throttle 0…1 → raw channel −1…1) и убрал повторную запись
   PWM_RANGE_MIN в motor-stop тесте. До правки именно этот тест воспроизводимо падал.
4. `pid_unittest.cc`: добавил сравнение ADRC P при одинаковом входе с anti-gravity
   OFF/ON. При намеренном удалении bypass тест падает; после восстановления проходит.

Текстовых конфликтов было два, в pid.c и mixer.c. Несовместимость тестового ввода
rcData не вызвала текстового конфликта: её выявила проверка интерфейса и тест.

## Просмотренные изменения upstream

| Область | Коммиты / PR | Значение для этой интеграции |
|---|---|---|
| Anti-gravity / Crash Flip | `1757120fd3`, #15920 | Два конфликта выше; upstream regression сохранён |
| Нормализация входа RX | `1011b6a9ae`, #15837 | rcData −1…1; rcCommand throttle остаётся 0…1. ADRC читает нормализованные collective, дополнительного изменения математики не нужно |
| Порядок инициализации | `05ff7eab1b`, #15885 | initRcProcessing после pidInit, чтобы читать обновлённые feedforward-настройки; принято из upstream |
| EEPROM diagnostics / alignment | `043fa0115f` #15867, `32bf6ce25f` #15870 | Причины resetEEPROM и byte-wise CRC приняты; ADRC hash-dirty fix при отвергнутой записи сохранён. Отдельный size guard #15908 здесь не добавлялся |
| MAVLink | `25f0c45814`, #15903 | Вместо встроенных generated headers — pinned submodule; основной источник огромного удаления строк. Подмодуль загружен при тестах |
| Serial/OSD migration | `e7b5e6f295` #15924, `3cf644ab2b` #15898 | Исправлены legacy serial mask и выбор OSD-порта для старой MSP+VTX_MSP линии. Это изменения новой базы, не установленное объяснение старого видеосрыва |
| RX framing / UART | `c510251891` #15947, `4c45a7ffb4` #15956, `bd42aa4c26` #15927 | Границы CRSF/SUMD и согласованное чтение UART ring indexes; приняты без ADRC-специфичных изменений |
| Gyro / IMU | `9818d81894` #15895, `aa2336ea7b` #15843, `a6603693a3` #15911 | Компиляция init slew limiter, ориентация BMI423, LSM6DSO; поведение датчиков требует учитывать при дальнейших аппаратных сравнениях |
| SPI/DMA/DShot/storage | #15859, #15858, #15917, #15914, #15915, #15748, #15934 | Восстановление SPI DMA, гонка остановки DShot, ограничения flash/SDIO и AT32 flash; приняты из upstream, покрыты общими тестами/сборками в пределах выбранных MCU |
| Wing/navigation | #15842, #15933, #15732, #15735, #15938 | Wing yaw/TPA, MSP speed curves, MAVLink mission и удаление неиспользуемого gps_rescue_yaw_p. Приняты в merge; полёт на самолёте не проводился |
| Остальное | CMS, LED, ADC/PICO/MCU fixes, config submodule bumps | Полный список из 55 коммитов сохранён рядом с логами; отдельного изменения ADRC не потребовалось |

## Проверки и совместимость

- `make -C src/test test`: **100/100 тестовых программ PASS** (новая база содержит
  дополнительные upstream-наборы; число программ не равно числу отдельных кейсов).
- Профильный прогон ADRC/PID/mixer/gate/Blackbox/EEPROM — PASS.
- Motor-stop regression: до адаптации rcData FAIL, после PASS.
- Новый anti-gravity ADRC-тест: mutation FAIL (P 180 → 180.306 вместо неизменности),
  восстановленный код PASS. Upstream testAntiGravityNotCompoundedWhenFilterNotFed сохранён.
- Чистая компиляция и линковка **STM32G474, STM32F405, STM32F411** успешны.
- adrc.c и adrc.h побайтово совпадают с `912827d69e`; объявление pidProfile_t не изменилось;
  PG_PID_PROFILE остаётся 1. Новые настройки/дефолты ADRC не вводились.
- Совместимость всего EEPROM на железе не проверялась: отсутствие изменения ADRC-layout
  не является обещанием сохранения любой конфигурации при смене набора build options.
- Сохранён dirty-hash fix в loadEEPROM; profile-version/EEPROM тесты проходят.
- Относительно нового master остаётся 26 ADRC-файлов; лишнего изменения src/config нет.
- `diff --check 912827d6..a7c9d139` чистый. Полный ADRC diff относительно master
  сохраняет существующее предупреждение: пустая строка в конце adrc_unittest.cc
  (то же предупреждение есть в исходной ветке PR); постороннее форматирование не менялось.
- Нет незавершённых конфликтов. Source tree после merge чистый по JJ;
  прежняя локальная symlink `tools` оставлена untracked.

При первой сборке с вынесенным BIN_DIR линковка G474 прошла, а objcopy не смог создать
HEX из-за отсутствующего каталога назначения. Каталог создан, упаковка прошла.
После фиксации merge SHA build/version.o пересобран для всех трёх целей, чтобы
проверочные артефакты не носили старую ревизию 912827d69. Это generic build checks,
не board-specific релиз для прошивки тестеру.

## Повторная независимая проверка

По отдельному запросу пользователя merge проверен повторно:

- `git merge-tree --write-tree 912827d6 c5102518` независимо восстановил автоматическое
  слияние. Сохранённый merge отличается ровно в четырёх ожидаемых путях: pid.c,
  mixer.c, adrc_mixer_unittest.cc и pid_unittest.cc. Все остальные blob/tree entries
  совпадают; src/config и MAVLink имеют точные gitlink из master.
- Повторный запуск `make -C src/test test`: снова **100/100 программ PASS**.
- Рабочие исходники совпадают с сохранённым merge a7c9d139; обе родительские головы
  являются его предками. Удалённые головы на момент перепроверки не сдвинулись.
- ELF SHA256 совпали с manifest; повторный objcopy с тем же `--set-start 0x8000000`,
  что в Makefile, дал побайтово одинаковые HEX. В каждой из трёх ELF присутствуют
  ADRC init и ground-wc функции (имена с LTO constprop), т.е. ADRC не исключён из сборки.
- Не найдено новых дефектов интеграции. Существующий EOF-whitespace warning
  в adrc_unittest.cc по-прежнему исторический и не относится к merge-правкам.

Артефакты независимого сравнения находятся в adrc-sync-20261103-review;
повторный test log — adrc-sync-20261103-recheck-tests.log.

## Границы и следующие шаги

Полёты jmsweng от 1 ноября относятся к `912827d69e`, а не к этому merge.
На новой интеграции железо не прошивалось. F411 hardware timing остаётся открытым;
успешная сборка не закрывает бюджет 8 kHz. Новую математику ADRC-036 не переносили.
Ветка `adrc-sync-20261103` отправлена на три remote, открыт PR в
`bvandevliet:adrc-toggle`. Далее — проверка CI и ревью новой головы; после слияния
Бобом #15400 должен получить новую базу.

Логи: `/home/danik/storage/adrc-sync-20261103-*.log`.
Объекты и сборки: `/home/danik/storage/adrc-sync-20261103-obj/`,
`/home/danik/storage/adrc-sync-20261103-builds/`.
Полный список upstream: `/home/danik/storage/adrc-sync-20261103-review/upstream-commits.txt`.

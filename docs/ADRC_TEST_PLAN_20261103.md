# План проверок ADRC: сверка на 3 ноября 2026

Базовая версия: PR betaflight/betaflight#15400, head `912827d69ec26120fdfdaac47b33c022c3073bc3`.
Проверены описание PR, 328 комментариев, 12 reviews, 12 inline-комментариев, обсуждения
issues/PR #1–5 нашего форка и PR #1–5 форка Боба, текущие check-runs и сырой лог CI.
Исторические полётные результаты сверялись с исправленными записями трекера и сообщениями;
повторно весь исторический корпус BBL в этой работе не декодировался.
Два новых лога Air65 разобраны и перепроверены отдельно двумя декодерами.

## Подтверждённые проверки

| Проверка | Результат и граница доказательства | Источник |
|---|---|---|
| CI на текущем PR head | Успех 29.10.2026: 95 тестовых программ, 41 build job. Фактический checkout `0f4cfbd8048de300d4d897296c86f23ea16a0ea3` — merge head `912827d69e` с base `b37531190d`. Не проверка сегодняшнего master | [CI](https://github.com/betaflight/betaflight/actions/runs/39300163902) |
| PID/ADRC host tests | PID 35 с USE_ADRC; ADRC 64; mixer 20; gate-e2e 37 (35 общих PID + 2 собственных); Blackbox 14 и encoding 6; EEPROM 2. Все PASS | [Лог test job](https://github.com/betaflight/betaflight/actions/runs/39300163902/job/123648972524) |
| Сохранение профиля, bench CLASSIC/ADRC | Исторически отмечены автором PR на SpeedyBee F7 Mini V2. Не заявляем повторение на нынешнем head | Описание [PR](https://github.com/betaflight/betaflight/pull/15400) |
| Полёт текущего head | Два BBL с `912827d69`, ADRC=1, BETAFPVG473_V2/G474, 24.417 и 43.260 с. Настроенный профиль 99/110, b0 8964/5378/3586, ground wc 20, sat_z3_inhibit OFF. Gate открывается по одному разу, reset counter не меняется внутри записей; switch disarm. Это один аппарат, не универсальная проверка всех режимов | [Вложения](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6563767455), [результат](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6604362590) |
| Ground wc на 5 дюймах | 19.09 jmsweng сообщил успешные проверки 10/40 и отсутствие подъёма на арме. Blackbox был заполнен: это свидетельство пилота, не анализ приложенного лога | [Сообщение](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5744912670) |
| Перезапуск arm epoch | Исторические host-регрессии и повторный арм в b3/b4-корпусе; новые файлы показывают закрытый gate в начале, но не доказывают общую power-cycle историю двух записей | ADRC-017 в трекере |
| Законы b0 | Doublet/flight-сравнения выполнены; SQRT выбран дефолтом b11, селектор сохранён. Оптимальный закон на каждом аппарате не установлен универсально | [b11](https://github.com/betaflight/betaflight/pull/15400#issuecomment-5744161762), ADRC-021 |
| Кратковременное насыщение / ADRC-033 | Исторические OFF/ON сравнения; новые ноябрьские логи с OFF не расширяют проверку ON | ADRC-033, сентябрьские addenda |
| Лог для #15908 | Запрос мейнтейнера снят 27.10; ноябрьский PID-лог `f202c6d51` относится к отдельному PR. Он не закрывает CLASSIC-тест на `912827d69e` | [#15908](https://github.com/betaflight/betaflight/pull/15908) |

95 программ — не 95 уникальных тест-кейсов. В полном CI есть 1525 запусков кейсов с
повторным использованием PID-кейсов; `test_rx_rx_unittest` перечисляет 0 кейсов.
Старое «15/15 без USE_ADRC» неверно для текущего head. Старое число gate-e2e «2»
описывает два собственных кейса файла, но исполняемый файл реально запускает 37.
Исторический прогон `-ffast-math` и mutation-проверки не выдаются за новый такой прогон.

## Что остаётся открытым

**Дополнение 03.11 после локальной синхронизации:** подготовлен merge `a7c9d13995dc4fc5297d1aa5f840b9b33dbe2748`
(head PR + upstream `c5102518`, 55 новых коммитов), bookmark `adrc-sync-20261103`.
На нём локально прошли 100 тестовых программ и сборки G474/F405/F411; новые конфликтные
пути проверены regression/mutation. Ветка опубликована на трёх remotes, открыт [PR Бобу #6](https://github.com/bvandevliet/betaflight/pull/6).
Успешный upstream CI на этой новой голове ещё не подтверждён, полётов на ней нет. Далее перечисленные старые CI/flight результаты
по-прежнему относятся к `912827d69e`, не к merge.

1. **F411 timing, ADRC-012.** Нет опубликованного измерения нагрузки на реальном F411.
   Запрошенный `tasks` полезен для фактической частоты/нагрузки; конкретный бюджет 8 kHz
   требует измерения времени/циклов и запаса в соответствующем режиме. Компиляция F411 и
   логи G474 этого не заменяют.
2. **Синхронизация с новым master.** Боб сообщил о конфликтах pid.c/mixer.c 02.11.
   После их разрешения нужны проверки и сборки на новом SHA; существующие результаты
   и полёты нельзя молча перенести на него. Полёт после будущего sync ещё невозможен:
   такой head в этом аудите не создавался.
3. **5-дюймовый аппарат на текущей линии.** jmsweng обещал полёт на этой неделе при погоде.
   Пока получен только Air65. Это дополнительная широта проверки, а не основание
   отозвать уже выполненный пункт «полёт текущего head».
4. **CLASSIC и EEPROM на нынешнем head.** В просмотренных материалах нет отдельного
   CLASSIC-полёта на `912827d69e` и полного аппаратного протокола upgrade → save → reboot
   → readback на нём. Есть host-тесты и исторические аппаратные проверки. Не объявляем
   автоматически новые обязательные полёты: это явная граница имеющихся доказательств.
5. **Аппаратная полнота специальных режимов.** Host-тесты проверяют crash/yaw-spin recovery,
   Crash Flip и overrides ALT_HOLD/GPS Rescue, но не заменяют аппаратную/полётную матрицу
   всех этих режимов на текущем head. Такой полной матрицы в рассмотренных записях нет.

## Сознательно отложено или вне приёмки этого PR

- **Универсальный тюн / прежний ADRC-022:** исключён из целей PR; настройка под аппарат.
  Не держать старый запрос универсальных дефолтов как незакрытый release blocker.
- **ADRC-028:** механизм остаётся открытым; Боб согласовал предупреждение про повышение wo
  вместо нового обязательного опыта перед ревью. Это не объявление дефекта исправленным.
- **Длительный насыщенный demand ADRC-033:** throttle/yaw/payload тесты проводились, но
  целевой длительный режим не получили. 23.09 договорились не добиваться его дальнейшим
  стресс-тестированием; опция OFF по умолчанию. Сценарий не проверен в полёте, запрос
  дополнительных опытов снят. Не повторять испытания с повреждёнными пропами ради галочки.
- **ADRC-036:** mp1/mp2 и их A/B остаются отдельной линией. A/B/chirp на 2.5/5 дюймах
  выполнены; уточнение шума в штиль и перенос на другие аппараты не являются приёмкой
  #15400. Потерянный 2.5-дюймовый аппарат нельзя считать доступным для немедленного повтора.
- **ADRC-024/025/027:** прежние исследовательские вопросы не закрываются автоматически
  двумя ноябрьскими файлами; не назначать заново все старые манёвры как обязательный план.
- Configurator #5302 и документация #718 — сопутствующие PR; аппаратный end-to-end тест
  нового GUI не подменять unit round-trip. #944 закрыт после переноса viewer в App.

## Доказательства и воспроизводимость

GitHub snapshot и лог CI: `/home/danik/storage/adrc-test-plan-20261103/`.
Ноябрьские BBL, SHA256, оба декода, скрипт и результаты: `/home/danik/storage/adrc-pr15400-20261103/`.
В рамках этой сверки firmware unit-тесты/сборки заново не запускались: проверен официальный
успешный CI. Новых аппаратных действий не выполнялось.

## Блок для описания upstream PR

Готовый блок передан владельцу PR: [комментарий](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6604575596). Описание upstream PR напрямую не изменялось: у нашего аккаунта нет прав записи.

Ниже английская версия для владельца PR; её результаты ограничены указанными SHA.

## Test plan

Evidence baseline: PR head `912827d69e`. Results below do not automatically cover the next sync with master.

- [x] **Upstream CI:** [run 39300163902](https://github.com/betaflight/betaflight/actions/runs/39300163902), completed 2026-10-29: all 95 test executables and 41 build jobs passed. CI checked merge commit `0f4cfbd804` (`912827d69e` into base `b37531190d`).
- [x] **Controller and integration tests:** `pid_unittest` 35 tests with `USE_ADRC` enabled; `adrc_unittest` 64; `adrc_mixer_unittest` 20; `adrc_gate_e2e_unittest` 37 (35 shared PID cases plus 2 dedicated gate cases). Blackbox tests: 14 in `blackbox_unittest`, 6 in `blackbox_encoding_unittest`; EEPROM regression tests: 2 in `config_eeprom_unittest`. These are host tests, not hardware timing measurements.
- [x] **Hardware setup and earlier flight coverage:** profile selection/save/readback and props-off checks were reported on SpeedyBee F7 Mini V2; subsequent tester flights covered whoops through 5-inch craft and ACRO/Airmode behaviour. This is historical evidence from earlier revisions, not a repeat of every check on the current head.
- [x] **Flight on the current PR head:** [jmsweng's two logs](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6563767455), reviewed [here](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6604362590). Both headers identify `912827d69`, BETAFPVG473_V2 / STM32G474 and `pid_type = ADRC`; durations 24.42 s and 43.26 s. Both start gate-closed, open once, show no change of the ADRC reset counter within the recording, and end with switch disarm. This validates a tuned Air65 profile, not universal defaults or F411 performance; `adrc_sat_z3_inhibit` was OFF.
- [ ] **F411 runtime cost (ADRC-012):** obtain `tasks` output with ADRC enabled at the actual flown loop rate. A real-hardware cycle/worst-case timing measurement is still needed to establish the specifically proposed 8 kHz budget; a successful F411 build or G474 log does not establish it.
- [ ] **After syncing with current master:** repeat CI / relevant host tests and builds, and record the new head and any behaviour/configuration changes. Existing flight evidence remains attached to `912827d69e`.

Additional coverage: jmsweng [plans a 5-inch flight](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6603310710) on this line. A separate CLASSIC flight on `912827d69e` and a complete on-device configuration upgrade/save/reboot check on this head have not been supplied in the reviewed records; earlier hardware checks and host regressions remain the evidence for those paths. These are evidence limits, not new requests to repeat the whole flight programme.

Scope decisions:
- A universal default tune is not a target of this PR; per-craft tuning is intended.
- ADRC-028 remains a documented caution about raising `wo`, as agreed, rather than a new pre-review experiment.
- The sustained-demand saturation corner of ADRC-033 was not reached by the earlier throttle/yaw/payload tests. Further deliberate stress testing was explicitly deferred; the option remains OFF by default. Do not mark that corner as flight-validated.
- ADRC-036 / motor-pole experiments remain a separate follow-up, not an acceptance condition for this PR.

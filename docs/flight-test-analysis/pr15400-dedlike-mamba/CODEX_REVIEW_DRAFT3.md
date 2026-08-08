# Review of `DRAFT_CORRECTION3.md`

Вердикт: **NO-GO**. Большинство чисел пересчитано верно, но перед публикацией нужны четыре обязательные правки: утверждение про открытие гейта в b7+, объяснение нормализации yaw, инструкция по опасному props-on тесту и заявление о уже готовом blackbox-fix.

1. В [DRAFT_CORRECTION3.md:27](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:27) утверждение, что b7+ открыл бы гейт посреди события, неверно.

В b6 верно следующее:

- applied collective пересекает 40% на `87.017 ms`;
- commanded collective остаётся `0%`;
- гейт читает commanded throttle;
- закрытый гейт держит именно observer input `b0u = 0` весь эпизод (`6317fe2aa:src/main/flight/adrc.c:420-449,512-515`).

Но b7/b8 всё равно не открыли бы его: applied-throttle path требует `!throttleAtIdle`, то есть commanded throttle не ниже idle threshold `20%`, а также `250 ms` выше порога. Здесь commanded throttle равен нулю, а после `87.017 ms` до конца лога остаётся лишь около `124 ms`.

Заменить абзац на:

> The applied collective crosses 40% at 87.017 ms while b6’s gate still reads commanded collective at 0%, so the observer keeps `b0u = 0`. This demonstrates a mismatch between observer input and actuator state. It does not imply that b7/b8 would open the gate: their applied-collective path is interlocked on commanded throttle being above the 20% idle threshold and requires 250 ms above the applied threshold; neither condition is met here. The effect of opening the gate remains untested.

Ту же ошибку убрать из [ANALYSIS.md:52](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:52).

2. В [DRAFT_CORRECTION3.md:32](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:32) неверно, что yaw clamp сам по себе гарантирует `motorMixRange > 1` и нормализацию. Yaw `±0.4` даёт span только `0.8`; с `87.017` до `127.025 ms` yaw уже у лимита, но верхнего rail и нормализации ещё нет.

Верно:

- `12/205 = 5.9%` кадров имеют raw roll `|P+D| > 500`;
- applied roll ни разу не достигает `±0.49`;
- все 12 кадров находятся в `192.039–203.041 ms`, когда уже активны обе моторные границы и нормализуется совокупный mix.

Заменить объяснение на:

> All 12 raw-roll-limit frames occur at 192–203 ms with both motor rails active. The combined motor mix is then normalized, so the applied roll component remains below ±0.49.

Исправить также [ANALYSIS.md:172](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:172).

3. Распределение `0/0/10/53/10/13/0%` численно верно только при явно заданном критерии applied yaw `|Y| ≥ 0.399`: количества кадров `0/0/3/16/3/4/0`.

Это не наблюдаемое распределение raw `pidSum` clamp: после clamp исходный yaw command восстановить нельзя. Формулировать так:

> Applied mixer-axis yaw within quantization of the ±0.400 limit (`|Y| ≥ 0.399`) is distributed as 0/0/10/53/10/13/0% across the 30 ms windows.

4. Roll timings `5/10/15 dps` на `86.017/103.020/107.021 ms` верны для `gyroUnfilt[0]`, а не `gyroADC[0]`. Добавить это имя поля. Это также окончательно исправляет прежнюю ошибку с saturation timing:

- roll пересекает `5 dps` за `1 ms` до первого yaw-limit frame;
- `10` и `15 dps` достигаются после yaw clamp, но за `24` и `20 ms` до первого upper motor rail на `127.025 ms`;
- следовательно, “roll ignites only after the motors rail” опровергнуто.

5. Значения `120@109`, `121@112`, `113@140`, `128@170` существуют, но первые два не следует выдавать за два независимых oscillation peaks: это один широкий положительный crest, разделённый коротким провалом.

Лучше написать:

> Successive positive-cycle peaks are approximately +121 dps at 112 ms, +113 dps at 140 ms, and +128 dps at 170 ms.

Ещё честнее — привести чередующиеся extrema: `−134@96`, `+121@112`, `−135@125`, `+113@140`, `−106@154`, `+128@170`. Абсолютный максимум до последнего положительного пика равен `−135`, поэтому “largest last” допустимо только для положительных пиков.

6. Fit `37.0 Hz / τ=65.6 ms / R²=0.988 / 9.5×` подтверждён. `9.5×` — отношение SSE постоянной синусоиды к growing-envelope fit, не рост амплитуды.

Формулировка сейчас не слишком слабая. Максимально сильное защищаемое утверждение:

> A 37 Hz yaw oscillation whose envelope is well fit by exponential growth over the observed unsaturated first 80 ms.

Этого достаточно, чтобы уверенно говорить `fast-growing oscillation` и `approximately exponential growth over the observed window`. Недостаточно для `RHP pole`, глобальной `divergent instability` или исключения limit cycle.

7. Reconstruction:

- `p95 = 0.271`;
- `max = 0.420`;
- до `120 ms`: `max = 0.00148`;
- median для constant-b0 reconstruction: `0.000862`.

Числа верны. Но вместо `unsaturated segment` написать:

> the pre-mixer-normalisation portion (`t < 120 ms`) for roll and pitch

Yaw к этому времени уже ограничен.

Также знак debug указан неверно: реально `debug[7] = −100…−120`. Поэтому писать `|scale| ≈ 1.00…1.20` и `b0 ≈ 2000…2400`, а не точное `2000→2400`. Исправить и [ANALYSIS.md:196](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:196).

8. `D/P = 2.55` по std и `2.52` на `34 Hz` подтверждены. Для второго числа уточнить метод: time-aware rectangular DFT. Заголовок [ANALYSIS.md:156](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:156) `The D-equivalent path carries it` всё ещё причинный и сильнее данных. Заменить на:

> The D-equivalent term dominates the command composition

9. PID-числа подтверждены, но формулировку нужно разлепить:

- first 211 ms: `0.74/0.88`;
- per-axis maxima по всем 211-ms окнам: `5.01/3.38`, но они достигнуты в разных окнах;
- PID matched window: `1.18/1.71` при applied collective `7.697%`;
- ADRC opening 30-ms mean collective на самом деле `7.732%`;
- ADRC first 211 ms: `34.2/57.9`.

Заменить на:

> Per-axis maxima across all 211 ms PID windows are 5.01 dps roll and 3.38 dps yaw, reached in different windows. A PID 30 ms window at 7.697% applied collective, matching ADRC’s opening 30 ms mean of 7.732%, gives 1.18/1.71 dps versus ADRC’s 34.2/57.9 dps over its first 211 ms.

Сравнение поддерживает “PID log is quiet”, но не доказывает равные prop-on аэродинамические условия: PID motors заметно менее активны. Этот caveat оставить.

10. Невязка `1.1e−16` подтверждена. Она действительно показывает, что рост applied collective получается из lower-clamp offset `−min(axis mix)`. `airmode` разрешает attitude authority при нулевом stick; `motor_idle`/dynamic idle задают выходной floor. Они не являются альтернативным объяснением точного покадрового равенства. `throttle_boost` его также не объясняет.

11. Roll episode `≈0.11 s = 2–3 cycles at 23 Hz` верен, если onset определён как первое `|gyroUnfilt roll| ≥ 10 dps`: `103.020–210.045 ms = 0.108 s = 2.49 cycles`. Добавить это определение.

12. Запрещённые формулировки в самом черновике остались только как явно отозванные цитаты — это нормально. Но в опубликованном анализе ещё заменить:

- [ANALYSIS.md:107](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:107): `diverging transient` → `growing transient`;
- [ANALYSIS.md:230](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:230): `divergent from arm` → `fast-growing from arm`.

13. `set adrc_b0_yaw = 4000` существует в `6317fe2aa`, диапазон `100…65535`, значение `4000` допустимо. Это `PROFILE_VALUE`, поэтому для его active profile 1 корректная последовательность:

```text
profile 1
set adrc_b0_yaw = 4000
get adrc_b0_yaw
save
```

После reboot нужно повторно проверить `profile` и `get adrc_b0_yaw`. Удвоение `b0` уменьшает мгновенные P/D-equivalent terms при том же observer state, но не гарантирует устойчивость.

Совет про props-on, двухсекундные армы и «руку на тумблере» удалить полностью. Это небезопасно: yaw достигает лимита за `87 ms`, мотор — верхнего rail за `127 ms`, что быстрее надёжной реакции человека, а collective продолжает расти до реальной тяги.

Безопасная замена:

> Do not repeat this props-on ground arm unrestrained. A human hand on the switch is not a sufficient cutoff: yaw reaches its command limit in 87 ms and a motor reaches its upper rail in 127 ms. Repeat only on a purpose-built restraint/test stand with a cleared area and an automatic cutoff before those thresholds; otherwise do not request a reproduction. A props-off test can validate configuration and logging, but cannot reproduce the aerodynamic event.

14. Blackbox-правка в [blackbox.c:526](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/b7/src/main/blackbox/blackbox.c:526) по смыслу верна:

- при ADRC и включённом `PID` пишет все три `axisD`;
- header и data используют одно cached condition, поэтому рассинхронизации нет;
- decoder header-driven, менять его не требуется;
- classic PID проходит старую ветку и не меняется.

Но:

- изменение сейчас **не закоммичено**: HEAD всё ещё `3c85c4b5a`, а `blackbox.c` просто modified. Фраза `Fixed on fork side` ложна. Либо сначала commit/push и дать ссылку, либо написать `I have a local patch`.
- стоимость лога ненулевая: при текущих defaults добавится один `axisD[2]` varint на main frame, обычно `1–5 bytes/frame`, то есть примерно `1–5 kB/s` при 1 kHz плюс header.
- существующие blackbox unit tests проходят, как и сборка `MAMBAF722`, но unit tests не собираются с `USE_ADRC` и новую ветку не проверяют. Перед заявлением о готовом fix нужен regression/roundtrip для ADRC header с `axisD[0..2]`, classic PID и отключённого `FIELD_SELECT(PID)`.
- комментарий в коде `where yaw went divergent at arm` снова вводит отозванный диагноз. Заменить на нейтральное `where yaw showed a rapidly growing arm-time oscillation` либо убрать case-specific комментарий.

После этих правок, commit/push blackbox-патча и удаления опасной тестовой инструкции текст будет готов к публикации. В нынешнем виде — **не публиковать**.

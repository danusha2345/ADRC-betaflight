# Повторное ревью `DRAFT_CORRECTION3.md`

Вердикт: **NO-GO**. Основные исправления применены, Git-состояние подтверждено, но остались четыре прежних дефекта и несколько новых неточностей.

## Состояние 14 пунктов

1. **PASS** — b7/b8 не открыли бы гейт: корректно и в [черновике:29](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:29), и в [ANALYSIS.md:54](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:54). Условия `20%`, `250 ms`, remaining `124 ms` изложены правильно.

2. **PASS** — `12/205`, интервал `192.039–203.041 ms`, оба motor rails и отсутствие объяснения через yaw clamp исправлены корректно: [черновик:34](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:34), [ANALYSIS.md:183](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:183).

3. **PASS с одной редакционной правкой** — `|Y| ≥ 0.399`, `0/0/3/16/3/4/0` и невосстановимость raw pre-clamp command указаны правильно. Но `of ~29 per window` неточно: знаменатели — `30/30/30/30/30/30/23`. Лучше привести их явно в [черновике:15](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:15) и [ANALYSIS.md:124](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:124).

4. **PASS с небольшой формулировочной коллизией** — `gyroUnfilt[0]` названо явно. Но заголовок `Roll starts with the yaw clamp` противоречит следующей фразе, где roll пересекает `5 °/s` на `1 ms` раньше. Лучше:

> Roll starts essentially contemporaneously with the yaw clamp, not with the motor rail.

5. **PASS** — чередующиеся extrema и ограничение `largest` только положительными пиками изложены корректно.

6. **PASS** — `9.5×` явно названо отношением SSE, сильнейшая защищаемая формулировка присутствует в [черновике:21](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:21).

7. **FAIL** — прежняя ошибка со знаком `debug[7]` не исправлена ни в [черновике:33](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:33), ни в [ANALYSIS.md:202](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:202).

Нужно заменить:

- `debug[7] runs 100 → 120` → `debug[7] runs −100 → −120`;
- `b0 rises 2000 → 2400` → `|b0ThrottleScale| ≈ 1.00 → 1.20, so effective b0 ≈ 2000 → 2400`;
- `unsaturated segment` → `pre-mixer-normalisation portion (t < 120 ms) for roll and pitch`.

Yaw после `87.017 ms` уже clamped, поэтому весь участок до `120 ms` нельзя называть unsaturated.

8. **PASS** — заголовок раздела 4 теперь нейтральный: `The D-equivalent term is the larger one`.

9. **FAIL** — PID-формулировка осталась прежней и неверной в [черновике:40](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:40) и [ANALYSIS.md:155](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:155).

`5.01/3.38` — per-axis maxima из разных 211-ms окон, а `7.697%` относится к PID window, не к ADRC opening window. Нужная замена:

> Per-axis maxima across all 211 ms PID windows are 5.01 °/s roll and 3.38 °/s yaw, reached in different windows. A PID 30 ms window at 7.697% applied collective, matching ADRC’s opening 30 ms mean of 7.732%, gives 1.18/1.71 °/s versus ADRC’s 34.2/57.9 °/s.

10. **PASS** — lower-clamp residual `1.1e-16` и роли airmode/motor idle изложены корректно в черновике.

11. **PASS по длительности, нужна точность endpoint** — `0.108 s ≈ 2.5 cycles` и onset `|gyroUnfilt[0]| ≥ 10 °/s` указаны. Но `211.045 ms` — конец интервала последнего кадра, не logged timestamp. Последний logged sample — `210.045 ms`.

Лучше написать:

> The first `|gyroUnfilt[0]| ≥ 10 °/s` sample is at 103.020 ms; the last logged sample is at 210.045 ms, giving approximately 0.108 s when the final sample interval is included, or about 2.5 cycles at 23 Hz.

12. **FAIL частично** — требуемые замены `growing transient` и `fast-growing from arm` сделаны. Но в анализе остались два безоговорочных диагноза:

- [ANALYSIS.md:192](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:192): `the axis that actually goes unstable` → `the axis showing the fast-growing oscillation`;
- [ANALYSIS.md:241](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:241): `yaw instability at 34 Hz` → `yaw oscillation at 34 Hz`.

13. **FAIL в ANALYSIS.md** — в черновике опасная инструкция удалена, безопасная замена и CLI-последовательность корректны. Но опубликованный [ANALYSIS.md:259](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/worktrees/docs/docs/flight-test-analysis/pr15400-dedlike-mamba/ANALYSIS.md:259) всё ещё советует:

- `A few seconds`;
- `short repeated arms`;
- `a hard stop the moment motors move`.

Это тот же небезопасный human-reaction сценарий, который черновик отзывает. Заменить весь абзац безопасным текстом из черновика: только purpose-built restraint/test stand, cleared area и automatic cutoff до `87/127 ms`; иначе props-on повтор не запрашивать. Props-off допустим только для проверки configuration/logging.

14. **PASS по Git и коду, FAIL по нескольким формулировкам черновика.**

Подтверждено:

- HEAD: `31a29cf333c57ad2349e3944b3bda690e4bc5752`;
- parent: `3c85c4b5ad713c9974bfbdf8d78669d67037ab1a`;
- remote `fork/adrc-blackbox-dterm` указывает на тот же `31a29cf333`;
- рабочее дерево чистое;
- комментарий больше не содержит `divergent`: теперь `rapidly growing arm-time oscillation`;
- `fork/master` действительно опубликован на `fb1b7be616e361c2123cd17ea759439d50926afa`.

В [черновике:67](/home/danik/Projects_and_coding/ADRC-betaflight/.scratch/dedlike/DRAFT_CORRECTION3.md:67) исправить:

- stale reference `blackbox.c:523-526` → `blackbox.c:523-539`;
- `all three axes log their D whenever ADRC is the controller` → `a log started with ADRC selected and PID fields enabled includes all three axisD fields`, поскольку condition кэшируется при старте лога;
- `one extra ... 1–5 bytes/frame` → `on the shipped defaults, one extra ... 1–5 bytes/frame`; на другом профиле потенциально могут добавиться до трёх полей;
- `target build and bench inspection` не подтверждается опубликованным коммитом или артефактом. Если аппаратного bench-check не было, заменить на `target build and source inspection`.

Оговорка об отсутствии ADRC regression-теста присутствует и корректна. Classic PID path не изменён, decoder/header mismatch патч не создаёт.

После исправления пунктов 7, 9, оставшихся `instability/unstable`, опасного раздела 6 в `ANALYSIS.md` и уточнений blackbox-абзаца будет **GO**. Сейчас — **NO-GO**.

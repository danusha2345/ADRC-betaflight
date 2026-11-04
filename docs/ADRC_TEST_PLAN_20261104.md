# Актуализация тест-плана ADRC — 04.11.2026

Боб слил PR #6 и #7; текущая базовая голова — 5a19cf92a.
CI проверен по API и полному логу job 126730721489: 101 программа, 43 build job.
Следующее исправление e2e24f49 закрывает armed set pid_type и пробел проверки
производственного вызова Blackbox. Локально 100 программ PASS, CLI 27,
Blackbox 15; G474 text 473151 / data 7840 / bss 88736. Оба дефекта покрытия
проверены мутациями. Аппаратных проверок не было.

Ниже — английский блок для описания PR по просьбе Боба.

## Test plan

Evidence baseline: PR head `5a19cf92a`. Flight evidence remains tied to `912827d69e`; it is not relabelled as a flight on the new head.

- [x] **Upstream CI after master sync and PR 7:** [run 41861935987](https://github.com/betaflight/betaflight/actions/runs/41861935987) passed on 2026-11-04. The tested merge checkout was `abbeb9b1bdab84f20ef134d33d45b6f2d01508a8` (`5a19cf92a` into master `cfc1c66eccf7884f2057364b45bb8386740afcc1`). Its test log contains **101 passing test executables**, and all **43 build jobs** passed. The earlier local PR-7 run had 100 executables; these are different checkouts.
- [x] **Controller and integration tests in that CI run:** PID 39, ADRC 64, ADRC mixer 20, gate e2e 41 (39 shared PID cases plus 2 dedicated cases), Blackbox 15, Blackbox encoding 6, EEPROM regression 2, CLI 26. These are host tests, not hardware timing measurements.
- [x] **Historical hardware setup and flight coverage:** profile selection/save/readback and props-off checks were reported on SpeedyBee F7 Mini V2; earlier tester flights covered whoops through 5-inch craft and ACRO/Airmode behaviour. These checks were not all repeated on `5a19cf92a`.
- [x] **Air65 flights on `912827d69e`:** [two logs from jmsweng](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6563767455), [analysis](https://github.com/betaflight/betaflight/pull/15400#issuecomment-6604362590). Headers identify BETAFPVG473_V2 / STM32G474 and ADRC; durations 24.42 s and 43.26 s. Both recordings start gate-closed, open once, retain the ADRC reset count within the recording, and end with switch disarm. This supports that tuned Air65 profile; `adrc_sat_z3_inhibit` was OFF.
- [ ] **F411 runtime cost (ADRC-012):** obtain `tasks` output at the actual flown loop rate. Establishing the specifically proposed 8 kHz budget still needs real-hardware cycle/worst-case timing evidence; builds and G474 logs do not establish it.
- [ ] **Latest review follow-up:** block armed `set pid_type` through both CLI setting paths and exercise the production Blackbox capture call. Local regression/mutation tests and a G474 build pass on the follow-up branch; merge and upstream CI on its resulting head remain pending.

Behaviour clarification: the classic PID control law is unchanged, but CLI behaviour is intentionally tightened. `profile N` is refused while armed for all controller types; queries remain available. The follow-up also refuses armed `pid_type` writes. Therefore, “classic PID unchanged” refers to the control law, not every configuration interface.

Evidence limits: no flight, separate CLASSIC flight, or complete on-device upgrade/save/reboot/readback sequence has been supplied for `5a19cf92a`. Historical hardware checks and host regressions remain the available evidence. A 5-inch flight on this line was planned by jmsweng. These are evidence limits, not a request to repeat the whole flight programme.

Scope decisions:
- Universal defaults are not a target; per-craft tuning is intended.
- ADRC-028 remains a documented caution about raising `wo`, rather than a new pre-review experiment.
- The sustained-demand saturation corner of ADRC-033 was not reached by earlier throttle/yaw/payload tests. Deliberate stress testing was deferred; the option stays OFF by default and that corner is not flight-validated.
- ADRC-036 / motor-pole experiments remain a separate follow-up.

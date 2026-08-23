# Test-only bounded ARM guard

This guard was used only to make the restrained props-on ground-arm campaign
self-terminating. It is **not** proposed as a production patch.

Base firmware commit:
`919116fed7057b7597825c283a2c8a00008ee338` (`adrc-pr15400-b9`). Target:
`MAMBAF722_I2C`; target-config revision: `57abd54`.

The following source was added to `src/main/fc/core.c`:

```c
#if defined(USE_ADRC) && defined(ADRC_BOUNDED_ARM_TEST_US)
#ifndef ADRC_BOUNDED_ARM_TEST_PIDSUM
#define ADRC_BOUNDED_ARM_TEST_PIDSUM 300
#endif
static timeUs_t adrcBoundedArmStartedUs;
#endif
```

Immediately after `pidController(currentPidProfile, currentTimeUs)` and before
the next motor update:

```c
#if defined(USE_ADRC) && defined(ADRC_BOUNDED_ARM_TEST_US)
    if (ARMING_FLAG(ARMED)) {
        if (adrcBoundedArmStartedUs == 0) {
            adrcBoundedArmStartedUs = currentTimeUs;
        }

        const bool pidSumLimitReached =
            fabsf(pidData[FD_ROLL].Sum) >= ADRC_BOUNDED_ARM_TEST_PIDSUM
            || fabsf(pidData[FD_PITCH].Sum) >= ADRC_BOUNDED_ARM_TEST_PIDSUM
            || fabsf(pidData[FD_YAW].Sum) >= ADRC_BOUNDED_ARM_TEST_PIDSUM;
        const bool deadlineReached = cmpTimeUs(currentTimeUs, adrcBoundedArmStartedUs) >= ADRC_BOUNDED_ARM_TEST_US;
        if (pidSumLimitReached || deadlineReached) {
            setArmingDisabled(ARMING_DISABLED_RUNAWAY_TAKEOFF);
            disarm(DISARM_REASON_RUNAWAY_TAKEOFF);
        }
    } else {
        adrcBoundedArmStartedUs = 0;
    }
#endif
```

Build commands (GNU Arm Embedded 13.3.Rel1):

```bash
make MAMBAF722_I2C_clean
make MAMBAF722_I2C V=0 REVISION=b9t750p30 \
  EXTRA_FLAGS='-DADRC_BOUNDED_ARM_TEST_US=750000 -DADRC_BOUNDED_ARM_TEST_PIDSUM=300'

make MAMBAF722_I2C_clean
make MAMBAF722_I2C V=0 REVISION=b9t1000p30 \
  EXTRA_FLAGS='-DADRC_BOUNDED_ARM_TEST_US=1000000 -DADRC_BOUNDED_ARM_TEST_PIDSUM=300'
```

Artifact SHA-256:

| build | HEX | DFU | ELF |
|---|---|---|---|
| `b9t750p30` | `ce3ac9cf814c562ab2a6109cbb479ac7abcc9c8d5876fbd578d5f781c583b037` | `827f400a4e7c33041ef5cc91b5caa990ca954312509f4bb24cf18e78577c7aea` | `70b635bd18ab71a668cdfa263d19a4883f584280f9b4220409ecf96099744d48` |
| `b9t1000p30` | `4599c1b1ba87804bd846064ddf659005c999fa6fa72f68d00edc0f86a553920c` | `e291138fd6d787a0023cb3e2c8f07cacb695b532ceb04fd7663958d5d75820f5` | `76874a10fdb7614b4804fb2ce1328d8e48a043e9bc0a674232cdf1e27f539ebe` |

The only `subTaskPidController` machine-code difference between the two test
ELFs was the deadline literal (`749999` versus `999999`, because of the compare
form). A normal build without `EXTRA_FLAGS` contained no
`adrcBoundedArmStartedUs` symbol. The controller was returned to that normal b9
build after the campaign.

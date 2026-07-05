/*
 * This file is part of Cleanflight.
 *
 * Cleanflight is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Cleanflight is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cleanflight.  If not, see <http://www.gnu.org/licenses/>.
 */

// Characterization tests for the ADRC (LADRC + LESO) rate controller living in
// pid.c: the liftoff gate state machine (fix #8/#10), the throttle-scaled b0
// (fix #10), the z3 leaky decay (fix #11) and the state reset paths. These pin
// the current inline behavior so a later extraction into a dedicated adrc.c
// can be verified as behavior-neutral.

#include <stdint.h>
#include <stdbool.h>
#include <limits.h>
#include <cmath>

#include "unittest_macros.h"
#include "gtest/gtest.h"
#include "build/debug.h"

bool simulatedThrottleRaised = true;
float simulatedSetpointRate[3] = { 0, 0, 0 };
float simulatedPrevSetpointRate[3] = { 0, 0, 0 };
float simulatedRcDeflection[3] = { 0, 0, 0 };
float simulatedMaxRcDeflectionAbs = 0;
float simulatedMixerGetRcThrottle = 0;
float simulatedRawSetpoint[3] = { 0, 0, 0 };
float simulatedMaxRate[3] = { 670, 670, 670 };
float simulatedMotorMixRange = 0.0f;
float simulatedMixerThrottle = 0.0f;

int16_t debug[DEBUG16_VALUE_COUNT];
uint8_t debugMode;

extern "C" {
    #include "platform.h"

    #include "build/debug.h"

    #include "common/axis.h"
    #include "common/maths.h"
    #include "common/filter.h"

    #include "config/config.h"
    #include "config/config_reset.h"

    #include "drivers/sound_beeper.h"
    #include "drivers/time.h"

    #include "fc/controlrate_profile.h"
    #include "fc/core.h"
    #include "fc/rc.h"

    #include "fc/rc_controls.h"
    #include "fc/runtime_config.h"

    #include "flight/imu.h"
    #include "flight/mixer.h"
    #include "flight/pid.h"
    #include "flight/pid_init.h"
    #include "flight/position.h"

    #include "io/gps.h"

    #include "pg/pg.h"
    #include "pg/pg_ids.h"

    #include "pg/rx.h"
    #include "rx/rx.h"

    #include "sensors/gyro.h"
    #include "sensors/acceleration.h"

    acc_t acc;
    gyro_t gyro;
    attitudeEulerAngles_t attitude;

    rxRuntimeState_t rxRuntimeState = {};

    PG_REGISTER(accelerometerConfig_t, accelerometerConfig, PG_ACCELEROMETER_CONFIG, 0);
    PG_REGISTER(systemConfig_t, systemConfig, PG_SYSTEM_CONFIG, 2);
    PG_REGISTER(positionConfig_t, positionConfig, PG_SYSTEM_CONFIG, 4);

    bool unitLaunchControlActive = false;
    launchControlMode_e unitLaunchControlMode = LAUNCH_CONTROL_MODE_NORMAL;

    float getMotorMixRange(void) { return simulatedMotorMixRange; }
    float getSetpointRate(int axis) { return simulatedSetpointRate[axis]; }
    bool wasThrottleRaised(void) { return simulatedThrottleRaised; }
    float getRcDeflectionAbs(int axis) { return fabsf(simulatedRcDeflection[axis]); }
    float getMaxRcDeflectionAbs() { return fabsf(simulatedMaxRcDeflectionAbs); }
    float mixerGetRcThrottle() { return fabsf(simulatedMixerGetRcThrottle); }
    float mixerGetThrottle(void) { return simulatedMixerThrottle; }

    bool isBelowLandingAltitude(void) { return false; }

    void systemBeep(bool) { }
    bool gyroOverflowDetected(void) { return false; }
    float getRcDeflection(int axis) { return simulatedRcDeflection[axis]; }
    float getRcDeflectionRaw(int axis) { return simulatedRcDeflection[axis]; }
    float getRawSetpoint(int axis) { return simulatedRawSetpoint[axis]; }
    float getFeedforward(int axis) {
        return simulatedSetpointRate[axis] - simulatedPrevSetpointRate[axis];
    }
    void beeperConfirmationBeeps(uint8_t) { }
    bool isLaunchControlActive(void) { return unitLaunchControlActive; }
    void disarm(flightLogDisarmReason_e) { }
    float getMaxRcRate(int axis)
    {
        UNUSED(axis);
        return simulatedMaxRate[axis];
    }
    void initRcProcessing(void) { }
}

pidProfile_t *pidProfile;

static int loopIter = 0;

// Mirrors the firmware's gate/timing constants (pid.c defines are file-local).
static const float TEST_DT = 0.008f;                 // 8 kHz-equivalent test looptime is 8 ms here
static const int LOOPS_LIFTOFF_GYRO_HOLD = 10;       // > 25 ms of sustained rotation
static const int LOOPS_IDLE_REARM = 70;              // > 500 ms of idle stillness
static const int LOOPS_BRIEF_CHOP = 40;              // ~320 ms, shorter than the re-arm hold

static void setDefaultTestSettings(void)
{
    pgResetAll();
    pidProfile = pidProfilesMutable(1);
    // ADRC interpretation: P = wc (control bandwidth), I = wo (observer bandwidth),
    // D * adrc_b0_scale = b0 (system gain).
    pidProfile->pid[PID_ROLL]  = { 40, 40, 30, 0, 0 };
    pidProfile->pid[PID_PITCH] = { 40, 40, 30, 0, 0 };
    pidProfile->pid[PID_YAW]   = { 40, 40, 30, 0, 0 };
    pidProfile->pid[PID_LEVEL] = { 50, 50, 75, 50, 0 };

    pidProfile->pidSumLimit = PIDSUM_LIMIT;        // 500
    pidProfile->pidSumLimitYaw = PIDSUM_LIMIT_YAW; // 400
    pidProfile->pidAtMinThrottle = PID_STABILISATION_ON;
    pidProfile->angle_limit = 60;
    pidProfile->crash_recovery = PID_CRASH_RECOVERY_OFF;
    // ADRC knobs: pgResetAll already applied the firmware defaults
    // (adrc_b0_scale 10, adrc_hover_throttle 35, adrc_sigma_decay 3, sched 0);
    // tests override per-case where the value matters.

    gyro.targetLooptime = 8000;
}

static timeUs_t currentTestTime(void)
{
    return targetPidLooptime * loopIter++;
}

static float testB0(int axis)
{
    return (float)pidProfile->pid[axis].D * (float)pidProfile->adrc_b0_scale;
}

static void resetTest(void)
{
    loopIter = 0;
    pidRuntime.tpaFactor = 1.0f;
    simulatedMotorMixRange = 0.0f;
    simulatedMixerThrottle = 0.0f;
    debugMode = DEBUG_ADRC;

    pidStabilisationState(PID_STABILISATION_OFF);
    DISABLE_ARMING_FLAG(ARMED);

    setDefaultTestSettings();
    for (int axis = FD_ROLL; axis <= FD_YAW; axis++) {
        pidData[axis] = {};
        simulatedSetpointRate[axis] = 0;
        simulatedPrevSetpointRate[axis] = 0;
        simulatedRcDeflection[axis] = 0;
        simulatedRawSetpoint[axis] = 0;
        gyro.gyroADCf[axis] = 0;
    }
    attitude.values.roll = 0;
    attitude.values.pitch = 0;
    attitude.values.yaw = 0;

    flightModeFlags = 0;
    unitLaunchControlActive = false;
    pidProfile->launchControlMode = unitLaunchControlMode;
    pidInit(pidProfile);
    loadControlRateProfile();

    // Settle: a few loops with stabilisation off wipe all ADRC state.
    for (int loop = 0; loop < 20; loop++) {
        pidController(pidProfile, currentTestTime());
    }

    ENABLE_ARMING_FLAG(ARMED);
    pidStabilisationState(PID_STABILISATION_ON);
}

static void runLoops(int n)
{
    for (int i = 0; i < n; i++) {
        pidController(pidProfile, currentTestTime());
    }
}

// ---------------------------------------------------------------- gate (fix #8/#10)

TEST(adrcTest, gateStartsClosedAndOpensOnThrottle)
{
    resetTest();
    runLoops(1);
    EXPECT_FALSE(pidRuntime.adrc_liftoff);

    simulatedMixerThrottle = 0.39f; // just below ADRC_LIFTOFF_THROTTLE
    runLoops(5);
    EXPECT_FALSE(pidRuntime.adrc_liftoff);

    simulatedMixerThrottle = 0.41f; // above threshold: opens on the next loop
    runLoops(1);
    EXPECT_TRUE(pidRuntime.adrc_liftoff);
}

TEST(adrcTest, gateOpensOnSustainedRotation)
{
    resetTest();
    simulatedMixerThrottle = 0.1f; // stays below the throttle threshold

    gyro.gyroADCf[FD_ROLL] = 15.0f; // below ADRC_LIFTOFF_GYRO_DPS: never opens
    runLoops(LOOPS_LIFTOFF_GYRO_HOLD * 4);
    EXPECT_FALSE(pidRuntime.adrc_liftoff);

    gyro.gyroADCf[FD_ROLL] = 50.0f; // sustained rotation (toss launch) opens it
    runLoops(LOOPS_LIFTOFF_GYRO_HOLD);
    EXPECT_TRUE(pidRuntime.adrc_liftoff);
}

TEST(adrcTest, gateRearmsAfterIdleStillness)
{
    resetTest();
    simulatedMixerThrottle = 0.5f;
    runLoops(1);
    ASSERT_TRUE(pidRuntime.adrc_liftoff);

    // Landed: idle throttle, no rotation — re-arms after the hold.
    simulatedMixerThrottle = 0.02f;
    gyro.gyroADCf[FD_ROLL] = 0.0f;
    runLoops(LOOPS_IDLE_REARM);
    EXPECT_FALSE(pidRuntime.adrc_liftoff);

    // And a second takeoff re-opens it — the whole cycle works repeatedly.
    simulatedMixerThrottle = 0.5f;
    runLoops(1);
    EXPECT_TRUE(pidRuntime.adrc_liftoff);
}

TEST(adrcTest, gateDoesNotRearmDuringAirChopOrWhileRotating)
{
    resetTest();
    simulatedMixerThrottle = 0.5f;
    runLoops(1);
    ASSERT_TRUE(pidRuntime.adrc_liftoff);

    // A brief throttle chop (shorter than the hold) must not re-arm.
    simulatedMixerThrottle = 0.02f;
    runLoops(LOOPS_BRIEF_CHOP);
    EXPECT_TRUE(pidRuntime.adrc_liftoff);
    simulatedMixerThrottle = 0.5f;
    runLoops(1);
    EXPECT_TRUE(pidRuntime.adrc_liftoff);

    // A long dive at idle throttle but with the craft rotating (mixerGetThrottle
    // excludes airmode, so throttle alone would lie) must not re-arm either.
    simulatedMixerThrottle = 0.02f;
    gyro.gyroADCf[FD_PITCH] = 100.0f;
    runLoops(LOOPS_IDLE_REARM * 3);
    EXPECT_TRUE(pidRuntime.adrc_liftoff);
}

// ------------------------------------------------------- throttle-scaled b0 (fix #10)

TEST(adrcTest, throttleScaledB0InDebug7)
{
    resetTest();
    pidProfile->adrc_hover_throttle = 35;

    // At (and below) hover the multiplier is 1.0 — debug[7] = 100, negative while gated.
    simulatedMixerThrottle = 0.35f;
    runLoops(1);
    EXPECT_EQ(debug[7], -100);

    // Double hover: (2)^2 = 4.0 -> 400, positive once airborne (0.7 > liftoff threshold).
    simulatedMixerThrottle = 0.70f;
    runLoops(2);
    EXPECT_EQ(debug[7], 400);

    // Full throttle with a low hover point clamps at ADRC_B0_THR_SCALE_MAX = 9 -> 900.
    pidProfile->adrc_hover_throttle = 20;
    simulatedMixerThrottle = 1.0f;
    runLoops(1);
    EXPECT_EQ(debug[7], 900);

    // Below hover it never scales down.
    pidProfile->adrc_hover_throttle = 60;
    simulatedMixerThrottle = 0.45f;
    runLoops(1);
    EXPECT_EQ(debug[7], 100);
}

// ------------------------------------------------------------------- ESO core

TEST(adrcTest, esoTracksConstantRateWhileGated)
{
    resetTest();
    pidProfile->adrc_sigma_decay = 0;

    // Slow constant rotation, below both liftoff triggers: pure observer, no b0*u.
    gyro.gyroADCf[FD_ROLL] = 10.0f;
    runLoops(2000);
    ASSERT_FALSE(pidRuntime.adrc_liftoff);
    EXPECT_NEAR(10.0f, pidRuntime.adrc_z1[FD_ROLL], 0.5f);
    EXPECT_NEAR(0.0f, pidRuntime.adrc_z2[FD_ROLL], 1.0f);
    EXPECT_NEAR(0.0f, pidRuntime.adrc_z3[FD_ROLL] / testB0(FD_ROLL), 0.5f);
}

TEST(adrcTest, z3AntiWindupCapsItermAtPidsumLimit)
{
    resetTest();
    pidProfile->adrc_sigma_decay = 0;

    // A violent sustained rotation winds z3 hard; the clamp must cap |I| = |z3/b0|
    // at the per-axis pidsum limit.
    gyro.gyroADCf[FD_ROLL] = 2000.0f;
    gyro.gyroADCf[FD_YAW] = 2000.0f;
    runLoops(1000);
    EXPECT_LE(fabsf(pidRuntime.adrc_z3[FD_ROLL]), testB0(FD_ROLL) * PIDSUM_LIMIT * 1.001f);
    EXPECT_LE(fabsf(pidData[FD_ROLL].I), PIDSUM_LIMIT * 1.001f);
    EXPECT_LE(fabsf(pidRuntime.adrc_z3[FD_YAW]), testB0(FD_YAW) * PIDSUM_LIMIT_YAW * 1.001f);
    EXPECT_LE(fabsf(pidData[FD_YAW].I), PIDSUM_LIMIT_YAW * 1.001f);
}

// --------------------------------------------------------------- leaky decay (fix #11)

TEST(adrcTest, sigmaDecayZeroIsPureIntegrator)
{
    resetTest();
    pidProfile->adrc_sigma_decay = 0;

    // With zero observer error (z1 == gyro == 0) a pure integrator holds z3 exactly:
    // this pins the promised "set adrc_sigma_decay = 0 to get the classic behavior".
    pidRuntime.adrc_z3[FD_ROLL] = 1000.0f;
    runLoops(1);
    EXPECT_FLOAT_EQ(1000.0f, pidRuntime.adrc_z3[FD_ROLL]);
}

TEST(adrcTest, sigmaDecayBleedsZ3)
{
    resetTest();
    pidProfile->adrc_sigma_decay = 30; // sigma = 3.0/s

    // Same zero-error setup: z3 must bleed by exactly dt * sigma * z3 per loop.
    pidRuntime.adrc_z3[FD_ROLL] = 1000.0f;
    runLoops(1);
    EXPECT_NEAR(1000.0f * (1.0f - TEST_DT * 3.0f), pidRuntime.adrc_z3[FD_ROLL], 0.01f);
}

TEST(adrcTest, decaySchedulingSlowsTheBleed)
{
    resetTest();
    pidProfile->adrc_sigma_decay = 30;
    pidProfile->adrc_sigma_decay_sched = 100; // gain 1.0 per unit of |errLp|

    // With a large ESO-error low-pass preloaded, the effective decay must be smaller
    // than the unscheduled one (qualitative: scheduling only ever slows the bleed).
    pidRuntime.adrc_z3[FD_ROLL] = 1000.0f;
    pidRuntime.adrc_errLp[FD_ROLL] = 50.0f;
    runLoops(1);
    EXPECT_GT(pidRuntime.adrc_z3[FD_ROLL], 1000.0f * (1.0f - TEST_DT * 3.0f));
    EXPECT_LT(pidRuntime.adrc_z3[FD_ROLL], 1000.0f);
}

// ----------------------------------------------------------------- reset paths

TEST(adrcTest, pidResetItermClearsAllAdrcState)
{
    resetTest();
    simulatedMixerThrottle = 0.5f;
    gyro.gyroADCf[FD_ROLL] = 100.0f;
    runLoops(50);
    ASSERT_TRUE(pidRuntime.adrc_liftoff);
    ASSERT_NE(0.0f, pidRuntime.adrc_z1[FD_ROLL]);

    pidRuntime.adrc_idleS = 0.1f;
    pidRuntime.adrc_errLp[FD_ROLL] = 5.0f;

    pidResetIterm();

    for (int axis = FD_ROLL; axis <= FD_YAW; axis++) {
        // z1 is bumplessly re-seeded to the current gyro rate (not zeroed) so the
        // observer does not jump violently on arming — everything else clears.
        EXPECT_FLOAT_EQ(gyro.gyroADCf[axis], pidRuntime.adrc_z1[axis]);
        EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_z2[axis]);
        EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_z3[axis]);
        EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_lastOutput[axis]);
        EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_errLp[axis]);
    }
    EXPECT_FALSE(pidRuntime.adrc_liftoff);
    EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_gyroActiveS);
    EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_idleS);
}

TEST(adrcTest, stabilisationOffWipesAdrcStateEveryLoop)
{
    resetTest();
    simulatedMixerThrottle = 0.5f;
    gyro.gyroADCf[FD_ROLL] = 100.0f;
    runLoops(50);
    ASSERT_TRUE(pidRuntime.adrc_liftoff);

    pidStabilisationState(PID_STABILISATION_OFF);
    runLoops(1);
    EXPECT_FALSE(pidRuntime.adrc_liftoff);
    for (int axis = FD_ROLL; axis <= FD_YAW; axis++) {
        // Same bumpless re-seed as pidResetIterm: z1 = current gyro, the rest wiped.
        EXPECT_FLOAT_EQ(gyro.gyroADCf[axis], pidRuntime.adrc_z1[axis]);
        EXPECT_FLOAT_EQ(0.0f, pidRuntime.adrc_z3[axis]);
    }
}

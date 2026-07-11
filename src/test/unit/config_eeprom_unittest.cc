/*
 * This file is part of Cleanflight and Betaflight.
 *
 * Cleanflight and Betaflight are free software. You can redistribute
 * this software and/or modify this software under the terms of the
 * GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * Cleanflight and Betaflight are distributed in the hope that they
 * will be useful, but WITHOUT ANY WARRANTY; without even the implied
 * warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this software.
 *
 * If not, see <http://www.gnu.org/licenses/>.
 */

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

extern "C" {
#include "platform.h"

#include "common/crc.h"

#include "config/config_eeprom.h"

#include "drivers/system.h"

#include "fc/controlrate_profile.h"

#include "flight/pid.h"

#include "pg/pg.h"
#include "pg/pg_ids.h"

extern uint8_t eepromData[EEPROM_SIZE];

typedef struct testVersionedConfig_s {
    uint32_t value;
} testVersionedConfig_t;

typedef struct testNeighborConfig_s {
    uint32_t value;
} testNeighborConfig_t;

PG_DECLARE(testVersionedConfig_t, testVersionedConfig);
PG_DECLARE(testNeighborConfig_t, testNeighborConfig);

PG_REGISTER_WITH_RESET_FN(testVersionedConfig_t, testVersionedConfig, PG_RESERVED_FOR_TESTING_1, 2);
PG_REGISTER_WITH_RESET_FN(testNeighborConfig_t, testNeighborConfig, PG_RESERVED_FOR_TESTING_2, 1);
PG_REGISTER_ARRAY_WITH_RESET_FN(pidProfile_t, PID_PROFILE_COUNT, pidProfiles, PG_PID_PROFILE, 15);
PG_REGISTER_ARRAY_WITH_RESET_FN(controlRateConfig_t, CONTROL_RATE_PROFILE_COUNT, controlRateProfiles, PG_CONTROL_RATE_PROFILES, 7);

static void pgResetFn_testVersionedConfig(testVersionedConfig_t *config)
{
    config->value = 0x11223344;
}

static void pgResetFn_testNeighborConfig(testNeighborConfig_t *config)
{
    config->value = 0x55667788;
}

void pgResetFn_pidProfiles(pidProfile_t *profiles)
{
    memset(profiles, 0, sizeof(pidProfile_t) * PID_PROFILE_COUNT);
    for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
        profiles[profileIndex].pid_type = PID_TYPE_CLASSIC;
        profiles[profileIndex].adrc.gyroFilterHz = 150;
        profiles[profileIndex].adrc.liftoffThrottlePercent = 40;
        profiles[profileIndex].motor_output_limit = 100;
    }
}

void pgResetFn_controlRateProfiles(controlRateConfig_t *profiles)
{
    memset(profiles, 0, sizeof(controlRateConfig_t) * CONTROL_RATE_PROFILE_COUNT);
    for (int profileIndex = 0; profileIndex < CONTROL_RATE_PROFILE_COUNT; profileIndex++) {
        profiles[profileIndex].rcRates[FD_ROLL] = 7;
        profiles[profileIndex].rcRates[FD_PITCH] = 7;
        profiles[profileIndex].rcRates[FD_YAW] = 7;
        profiles[profileIndex].throttle_limit_percent = 100;
    }
}

static int failureModeCall = -1;

void failureMode(failureMode_e mode)
{
    failureModeCall = mode;
}
}

#include "gtest/gtest.h"

namespace {

constexpr uint16_t crcStartValue = 0xFFFF;

typedef struct testConfigHeader_s {
    uint8_t eepromConfigVersion;
    uint8_t magicBe;
} PG_PACKED testConfigHeader_t;

typedef struct testConfigRecord_s {
    uint16_t size;
    pgn_t pgn;
    uint8_t version;
    uint8_t flags;
    uint8_t pg[];
} PG_PACKED testConfigRecord_t;

testConfigRecord_t *findStoredRecord(pgn_t pgn)
{
    uint8_t *cursor = eepromData + sizeof(testConfigHeader_t);
    const uint8_t *const end = eepromData + EEPROM_SIZE;

    while (cursor + sizeof(testConfigRecord_t) < end) {
        testConfigRecord_t *record = reinterpret_cast<testConfigRecord_t *>(cursor);
        if (record->size == 0 || record->size < sizeof(testConfigRecord_t) || cursor + record->size >= end) {
            return nullptr;
        }
        if (record->pgn == pgn) {
            return record;
        }
        cursor += record->size;
    }

    return nullptr;
}

uint16_t storedConfigSize()
{
    const uint8_t *cursor = eepromData + sizeof(testConfigHeader_t);
    const uint8_t *const end = eepromData + EEPROM_SIZE;

    while (cursor + sizeof(testConfigRecord_t) < end) {
        const testConfigRecord_t *record = reinterpret_cast<const testConfigRecord_t *>(cursor);
        if (record->size == 0) {
            return static_cast<uint16_t>(cursor - eepromData + sizeof(uint16_t) + sizeof(uint16_t));
        }
        if (record->size < sizeof(testConfigRecord_t) || cursor + record->size >= end) {
            return 0;
        }
        cursor += record->size;
    }

    return 0;
}

void rewriteStoredCrc(uint16_t configSize)
{
    const size_t crcOffset = configSize - sizeof(uint16_t);
    const uint16_t crc = crc16_ccitt_update(crcStartValue, eepromData, crcOffset);
    const uint16_t invertedBigEndianCrc = static_cast<uint16_t>(~(((crc & 0xFF) << 8) | (crc >> 8)));
    std::memcpy(eepromData + crcOffset, &invertedBigEndianCrc, sizeof(invertedBigEndianCrc));
}

class ConfigEepromTest : public testing::Test {
protected:
    void SetUp() override
    {
        std::memset(eepromData, 0, EEPROM_SIZE);
        pgResetAll();
        failureModeCall = -1;
    }

    void writeCurrentConfig()
    {
        writeConfigToEEPROM();
        ASSERT_EQ(-1, failureModeCall);
        ASSERT_TRUE(isEEPROMVersionValid());
        ASSERT_TRUE(isEEPROMStructureValid());
    }

    void downgradeVersionedRecord()
    {
        ASSERT_TRUE(isEEPROMStructureValid());
        const uint16_t configSize = storedConfigSize();
        ASSERT_NE(0, configSize);
        testConfigRecord_t *record = findStoredRecord(PG_RESERVED_FOR_TESTING_1);
        ASSERT_NE(nullptr, record);
        ASSERT_EQ(2, record->version);
        record->version = 1;
        rewriteStoredCrc(configSize);
        ASSERT_TRUE(isEEPROMStructureValid());
    }

    void convertPidRecordToPg14()
    {
        ASSERT_TRUE(isEEPROMStructureValid());
        const uint16_t configSize = storedConfigSize();
        ASSERT_NE(0, configSize);
        testConfigRecord_t *record = findStoredRecord(PG_PID_PROFILE);
        ASSERT_NE(nullptr, record);
        ASSERT_EQ(15, record->version);
        ASSERT_EQ(sizeof(testConfigRecord_t) + sizeof(pidProfile_t) * PID_PROFILE_COUNT, record->size);

        constexpr size_t dtermFilterOffset = offsetof(pidProfile_t, adrc.dtermFilterHz);
        constexpr size_t legacyProfileSize = sizeof(pidProfile_t) - sizeof(uint16_t);
        std::array<uint8_t, legacyProfileSize * PID_PROFILE_COUNT> legacyPayload = {};
        for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
            const uint8_t *source = record->pg + profileIndex * sizeof(pidProfile_t);
            uint8_t *destination = legacyPayload.data() + profileIndex * legacyProfileSize;
            std::memcpy(destination, source, dtermFilterOffset);
            std::memcpy(destination + dtermFilterOffset,
                source + dtermFilterOffset + sizeof(uint16_t),
                sizeof(pidProfile_t) - dtermFilterOffset - sizeof(uint16_t));
        }

        const uint16_t currentRecordSize = record->size;
        const uint16_t legacyRecordSize = sizeof(testConfigRecord_t) + legacyPayload.size();
        const size_t recordOffset = reinterpret_cast<uint8_t *>(record) - eepromData;
        const size_t tailOffset = recordOffset + currentRecordSize;
        const size_t tailSize = configSize - tailOffset;
        std::memmove(eepromData + recordOffset + legacyRecordSize, eepromData + tailOffset, tailSize);

        record = reinterpret_cast<testConfigRecord_t *>(eepromData + recordOffset);
        record->size = legacyRecordSize;
        record->version = 14;
        std::memcpy(record->pg, legacyPayload.data(), legacyPayload.size());

        const uint16_t legacyConfigSize = configSize - (currentRecordSize - legacyRecordSize);
        std::memset(eepromData + legacyConfigSize, 0, configSize - legacyConfigSize);
        rewriteStoredCrc(legacyConfigSize);
        ASSERT_TRUE(isEEPROMStructureValid());
    }
};

TEST_F(ConfigEepromTest, VersionMismatchForcesDefaultOnlyConfigRewrite)
{
    writeCurrentConfig();
    downgradeVersionedRecord();

    EXPECT_FALSE(loadEEPROM());
    EXPECT_EQ(0x11223344U, testVersionedConfig()->value);
    EXPECT_EQ(0x55667788U, testNeighborConfig()->value);
    const uint32_t resetHash = fnv_update(FNV_OFFSET_BASIS, testVersionedConfig(), sizeof(*testVersionedConfig()));
    EXPECT_EQ(~resetHash, testVersionedConfig_fnv_hash);

    // initPhase1 responds to a failed readEEPROM() with resetEEPROM(); these are the
    // persistent operations performed by that reset path.
    pgResetAll();
    writeCurrentConfig();

    const testConfigRecord_t *rewrittenRecord = findStoredRecord(PG_RESERVED_FOR_TESTING_1);
    ASSERT_NE(nullptr, rewrittenRecord);
    EXPECT_EQ(2, rewrittenRecord->version);

    testVersionedConfigMutable()->value = 0;
    testNeighborConfigMutable()->value = 0;
    EXPECT_TRUE(loadEEPROM());
    EXPECT_EQ(0x11223344U, testVersionedConfig()->value);
    EXPECT_EQ(0x55667788U, testNeighborConfig()->value);
    EXPECT_EQ(resetHash, testVersionedConfig_fnv_hash);
}

TEST_F(ConfigEepromTest, VersionMismatchRejectsBlobAndResetsUserConfig)
{
    testVersionedConfigMutable()->value = 0xDEADBEEF;
    testNeighborConfigMutable()->value = 0xCAFEBABE;
    writeCurrentConfig();
    downgradeVersionedRecord();

    EXPECT_FALSE(loadEEPROM());
    EXPECT_EQ(0x11223344U, testVersionedConfig()->value);
    EXPECT_EQ(0xCAFEBABEU, testNeighborConfig()->value);

    pgResetAll();
    writeCurrentConfig();

    testVersionedConfigMutable()->value = 0;
    testNeighborConfigMutable()->value = 0;
    EXPECT_TRUE(loadEEPROM());
    EXPECT_EQ(0x11223344U, testVersionedConfig()->value);
    EXPECT_EQ(0x55667788U, testNeighborConfig()->value);
}

TEST_F(ConfigEepromTest, PidPg14BootRecoveryRewritesAllProfilesAsPg15)
{
    for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
        pidProfile_t *profile = pidProfilesMutable(profileIndex);
        profile->pid_type = PID_TYPE_ADRC;
        profile->adrc.dtermFilterHz = 120 + profileIndex;
        profile->adrc.gyroFilterHz = 300 + profileIndex;
        profile->motor_output_limit = 40 + profileIndex;
    }
    for (int profileIndex = 0; profileIndex < CONTROL_RATE_PROFILE_COUNT; profileIndex++) {
        controlRateProfilesMutable(profileIndex)->rcRates[FD_ROLL] = 20 + profileIndex;
        controlRateProfilesMutable(profileIndex)->throttle_limit_percent = 80 + profileIndex;
    }
    writeCurrentConfig();
    convertPidRecordToPg14();

    EXPECT_FALSE(loadEEPROM());
    for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
        EXPECT_EQ(PID_TYPE_CLASSIC, pidProfiles(profileIndex)->pid_type);
        EXPECT_EQ(0, pidProfiles(profileIndex)->adrc.dtermFilterHz);
        EXPECT_EQ(150, pidProfiles(profileIndex)->adrc.gyroFilterHz);
        EXPECT_EQ(100, pidProfiles(profileIndex)->motor_output_limit);
    }
    for (int profileIndex = 0; profileIndex < CONTROL_RATE_PROFILE_COUNT; profileIndex++) {
        EXPECT_EQ(20 + profileIndex, controlRateProfiles(profileIndex)->rcRates[FD_ROLL]);
        EXPECT_EQ(80 + profileIndex, controlRateProfiles(profileIndex)->throttle_limit_percent);
    }

    // This is the persistent core of resetEEPROM() after initPhase1 sees readEEPROM() fail.
    pgResetAll();
    writeCurrentConfig();

    const testConfigRecord_t *rewrittenRecord = findStoredRecord(PG_PID_PROFILE);
    ASSERT_NE(nullptr, rewrittenRecord);
    EXPECT_EQ(15, rewrittenRecord->version);
    EXPECT_EQ(sizeof(testConfigRecord_t) + sizeof(pidProfile_t) * PID_PROFILE_COUNT, rewrittenRecord->size);

    std::memset(pidProfilesMutable(0), 0xA5, sizeof(pidProfile_t) * PID_PROFILE_COUNT);
    std::memset(controlRateProfilesMutable(0), 0xA5, sizeof(controlRateConfig_t) * CONTROL_RATE_PROFILE_COUNT);
    EXPECT_TRUE(loadEEPROM());
    for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
        EXPECT_EQ(PID_TYPE_CLASSIC, pidProfiles(profileIndex)->pid_type);
        EXPECT_EQ(0, pidProfiles(profileIndex)->adrc.dtermFilterHz);
        EXPECT_EQ(150, pidProfiles(profileIndex)->adrc.gyroFilterHz);
        EXPECT_EQ(100, pidProfiles(profileIndex)->motor_output_limit);
    }
    for (int profileIndex = 0; profileIndex < CONTROL_RATE_PROFILE_COUNT; profileIndex++) {
        EXPECT_EQ(7, controlRateProfiles(profileIndex)->rcRates[FD_ROLL]);
        EXPECT_EQ(100, controlRateProfiles(profileIndex)->throttle_limit_percent);
    }
}

TEST_F(ConfigEepromTest, PidPg15RoundTripPreservesAdrcAndNeighborProfiles)
{
    for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
        pidProfile_t *profile = pidProfilesMutable(profileIndex);
        profile->pid_type = PID_TYPE_ADRC;
        profile->adrc.dtermFilterHz = 100 + 25 * profileIndex;
        profile->adrc.gyroFilterHz = 200 + 10 * profileIndex;
        profile->adrc.liftoffThrottlePercent = 50 + profileIndex;
        profile->motor_output_limit = 70 + profileIndex;
    }
    for (int profileIndex = 0; profileIndex < CONTROL_RATE_PROFILE_COUNT; profileIndex++) {
        controlRateConfig_t *profile = controlRateProfilesMutable(profileIndex);
        profile->rcRates[FD_ROLL] = 30 + profileIndex;
        profile->rcRates[FD_PITCH] = 40 + profileIndex;
        profile->rcRates[FD_YAW] = 50 + profileIndex;
        profile->throttle_limit_percent = 85 + profileIndex;
    }
    writeCurrentConfig();

    const testConfigRecord_t *storedRecord = findStoredRecord(PG_PID_PROFILE);
    ASSERT_NE(nullptr, storedRecord);
    EXPECT_EQ(15, storedRecord->version);
    std::memset(pidProfilesMutable(0), 0, sizeof(pidProfile_t) * PID_PROFILE_COUNT);
    std::memset(controlRateProfilesMutable(0), 0, sizeof(controlRateConfig_t) * CONTROL_RATE_PROFILE_COUNT);

    EXPECT_TRUE(loadEEPROM());
    for (int profileIndex = 0; profileIndex < PID_PROFILE_COUNT; profileIndex++) {
        const pidProfile_t *profile = pidProfiles(profileIndex);
        EXPECT_EQ(PID_TYPE_ADRC, profile->pid_type);
        EXPECT_EQ(100 + 25 * profileIndex, profile->adrc.dtermFilterHz);
        EXPECT_EQ(200 + 10 * profileIndex, profile->adrc.gyroFilterHz);
        EXPECT_EQ(50 + profileIndex, profile->adrc.liftoffThrottlePercent);
        EXPECT_EQ(70 + profileIndex, profile->motor_output_limit);
    }
    for (int profileIndex = 0; profileIndex < CONTROL_RATE_PROFILE_COUNT; profileIndex++) {
        const controlRateConfig_t *profile = controlRateProfiles(profileIndex);
        EXPECT_EQ(30 + profileIndex, profile->rcRates[FD_ROLL]);
        EXPECT_EQ(40 + profileIndex, profile->rcRates[FD_PITCH]);
        EXPECT_EQ(50 + profileIndex, profile->rcRates[FD_YAW]);
        EXPECT_EQ(85 + profileIndex, profile->throttle_limit_percent);
    }
}

} // namespace

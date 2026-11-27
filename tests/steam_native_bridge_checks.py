#!/usr/bin/env python3
"""Verify Nexus Steamworks native bridge against a real compiled C11 fake libsteam_api shared library."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

FAKE_STEAM_C = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static bool g_initialized = false;
static uint32_t g_app_id = 480;
static bool g_ach = false;
static int32_t g_stat_i = 0;
static float g_stat_f = 0.0f;
static char g_cloud_name[256] = {0};
static uint8_t g_cloud_data[65536];
static int32_t g_cloud_len = 0;
static char g_lobby_k[256] = {0};
static char g_lobby_v[512] = {0};
static int g_dummy_iface = 1;

bool SteamAPI_RestartAppIfNecessary(uint32_t unOwnAppID) { (void)unOwnAppID; return false; }
int SteamAPI_InitFlat(char *pOutErrMsg) { if (pOutErrMsg) pOutErrMsg[0] = 0; g_initialized = true; return 0; }
void SteamAPI_Shutdown(void) { g_initialized = false; }
void SteamAPI_RunCallbacks(void) {}
bool SteamAPI_IsSteamRunning(void) { return g_initialized; }

void *SteamAPI_SteamUser_v023(void) { return &g_dummy_iface; }
uint64_t SteamAPI_ISteamUser_GetSteamID(void *self) { (void)self; return 76561198012345678ULL; }
bool SteamAPI_ISteamUser_BLoggedOn(void *self) { (void)self; return true; }

void *SteamAPI_SteamFriends_v017(void) { return &g_dummy_iface; }
const char *SteamAPI_ISteamFriends_GetPersonaName(void *self) { (void)self; return "FakeSteamUser"; }
void SteamAPI_ISteamFriends_ActivateGameOverlay(void *self, const char *pchDialog) { (void)self; (void)pchDialog; }
bool SteamAPI_ISteamFriends_SetRichPresence(void *self, const char *pchKey, const char *pchValue) { (void)self; return pchKey && pchValue; }
void SteamAPI_ISteamFriends_ClearRichPresence(void *self) { (void)self; }
int SteamAPI_ISteamFriends_GetFriendCount(void *self, int iFriendFlags) { (void)self; (void)iFriendFlags; return 5; }

void *SteamAPI_SteamUserStats_v013(void) { return &g_dummy_iface; }
bool SteamAPI_ISteamUserStats_RequestCurrentStats(void *self) { (void)self; return true; }
bool SteamAPI_ISteamUserStats_StoreStats(void *self) { (void)self; return true; }
bool SteamAPI_ISteamUserStats_GetAchievement(void *self, const char *pchName, bool *pbAchieved) {
    (void)self; (void)pchName; if (pbAchieved) *pbAchieved = g_ach; return true;
}
bool SteamAPI_ISteamUserStats_SetAchievement(void *self, const char *pchName) { (void)self; (void)pchName; g_ach = true; return true; }
bool SteamAPI_ISteamUserStats_ClearAchievement(void *self, const char *pchName) { (void)self; (void)pchName; g_ach = false; return true; }
bool SteamAPI_ISteamUserStats_IndicateAchievementProgress(void *self, const char *pchName, uint32_t cur, uint32_t maxv) {
    (void)self; (void)pchName; return cur <= maxv;
}
bool SteamAPI_ISteamUserStats_GetStatInt32(void *self, const char *pchName, int32_t *pData) {
    (void)self; (void)pchName; if (pData) *pData = g_stat_i; return true;
}
bool SteamAPI_ISteamUserStats_SetStatInt32(void *self, const char *pchName, int32_t nData) {
    (void)self; (void)pchName; g_stat_i = nData; return true;
}
bool SteamAPI_ISteamUserStats_GetStatFloat(void *self, const char *pchName, float *pData) {
    (void)self; (void)pchName; if (pData) *pData = g_stat_f; return true;
}
bool SteamAPI_ISteamUserStats_SetStatFloat(void *self, const char *pchName, float fData) {
    (void)self; (void)pchName; g_stat_f = fData; return true;
}

void *SteamAPI_SteamRemoteStorage_v016(void) { return &g_dummy_iface; }
bool SteamAPI_ISteamRemoteStorage_IsCloudEnabledForApp(void *self) { (void)self; return true; }
bool SteamAPI_ISteamRemoteStorage_IsCloudEnabledForAccount(void *self) { (void)self; return true; }
bool SteamAPI_ISteamRemoteStorage_FileWrite(void *self, const char *pchFile, const void *pvData, int32_t cubData) {
    (void)self;
    if (!pchFile || cubData < 0 || cubData > (int32_t)sizeof(g_cloud_data)) return false;
    snprintf(g_cloud_name, sizeof(g_cloud_name), "%s", pchFile);
    if (cubData > 0 && pvData) memcpy(g_cloud_data, pvData, (size_t)cubData);
    g_cloud_len = cubData;
    return true;
}
int32_t SteamAPI_ISteamRemoteStorage_FileRead(void *self, const char *pchFile, void *pvData, int32_t cubDataToRead) {
    (void)self;
    if (!pchFile || strcmp(g_cloud_name, pchFile) != 0) return -1;
    int32_t n = g_cloud_len < cubDataToRead ? g_cloud_len : cubDataToRead;
    if (n > 0 && pvData) memcpy(pvData, g_cloud_data, (size_t)n);
    return n;
}
bool SteamAPI_ISteamRemoteStorage_FileExists(void *self, const char *pchFile) {
    (void)self; return pchFile && strcmp(g_cloud_name, pchFile) == 0;
}
bool SteamAPI_ISteamRemoteStorage_FileDelete(void *self, const char *pchFile) {
    (void)self; if (pchFile && strcmp(g_cloud_name, pchFile) == 0) { g_cloud_name[0] = 0; g_cloud_len = 0; return true; } return false;
}
int32_t SteamAPI_ISteamRemoteStorage_GetFileCount(void *self) { (void)self; return g_cloud_name[0] ? 1 : 0; }
bool SteamAPI_ISteamRemoteStorage_GetQuota(void *self, uint64_t *pnTotalBytes, uint64_t *puAvailableBytes) {
    (void)self;
    if (pnTotalBytes) *pnTotalBytes = 1048576ULL;
    if (puAvailableBytes) *puAvailableBytes = 1048576ULL - (uint64_t)g_cloud_len;
    return true;
}

void *SteamAPI_SteamApps_v008(void) { return &g_dummy_iface; }
bool SteamAPI_ISteamApps_BIsDlcInstalled(void *self, uint32_t appID) { (void)self; return appID == 482; }
const char *SteamAPI_ISteamApps_GetCurrentGameLanguage(void *self) { (void)self; return "english"; }

void *SteamAPI_SteamUtils_v010(void) { return &g_dummy_iface; }
uint32_t SteamAPI_ISteamUtils_GetAppID(void *self) { (void)self; return g_app_id; }
bool SteamAPI_ISteamUtils_IsOverlayEnabled(void *self) { (void)self; return true; }
bool SteamAPI_ISteamUtils_IsSteamRunningOnSteamDeck(void *self) { (void)self; return true; }
bool SteamAPI_ISteamUtils_IsSteamInBigPictureMode(void *self) { (void)self; return true; }

void *SteamAPI_SteamMatchmaking_v009(void) { return &g_dummy_iface; }
uint64_t SteamAPI_ISteamMatchmaking_CreateLobby(void *self, int eLobbyType, int cMaxMembers) {
    (void)self; (void)eLobbyType; (void)cMaxMembers; return 777001ULL;
}
uint64_t SteamAPI_ISteamMatchmaking_JoinLobby(void *self, uint64_t steamIDLobby) { (void)self; return steamIDLobby; }
void SteamAPI_ISteamMatchmaking_LeaveLobby(void *self, uint64_t steamIDLobby) { (void)self; (void)steamIDLobby; }
bool SteamAPI_ISteamMatchmaking_SetLobbyData(void *self, uint64_t steamIDLobby, const char *pchKey, const char *pchValue) {
    (void)self; (void)steamIDLobby;
    snprintf(g_lobby_k, sizeof(g_lobby_k), "%s", pchKey ? pchKey : "");
    snprintf(g_lobby_v, sizeof(g_lobby_v), "%s", pchValue ? pchValue : "");
    return true;
}
const char *SteamAPI_ISteamMatchmaking_GetLobbyData(void *self, uint64_t steamIDLobby, const char *pchKey) {
    (void)self; (void)steamIDLobby;
    if (pchKey && strcmp(g_lobby_k, pchKey) == 0) return g_lobby_v;
    return "";
}
int SteamAPI_ISteamMatchmaking_GetNumLobbyMembers(void *self, uint64_t steamIDLobby) { (void)self; (void)steamIDLobby; return 1; }

void *SteamAPI_SteamUGC_v020(void) { return &g_dummy_iface; }
uint32_t SteamAPI_ISteamUGC_GetNumSubscribedItems(void *self) { (void)self; return 1; }
uint32_t SteamAPI_ISteamUGC_GetSubscribedItems(void *self, uint64_t *pvecPublishedFileID, uint32_t cMaxEntries) {
    (void)self; if (cMaxEntries >= 1 && pvecPublishedFileID) pvecPublishedFileID[0] = 9001ULL; return cMaxEntries >= 1 ? 1 : 0;
}
bool SteamAPI_ISteamUGC_GetItemInstallInfo(void *self, uint64_t nPublishedFileID, uint64_t *punSizeOnDisk, char *pchFolder, uint32_t cchFolderSize, uint32_t *punTimeStamp) {
    (void)self;
    if (nPublishedFileID != 9001ULL) return false;
    if (punSizeOnDisk) *punSizeOnDisk = 4096ULL;
    if (pchFolder && cchFolderSize > 0) snprintf(pchFolder, cchFolderSize, "/tmp/steam/workshop/ugc_9001");
    if (punTimeStamp) *punTimeStamp = 1700000000U;
    return true;
}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    args = parser.parse_args()

    binary = ROOT / 'build/steam-native-checks'
    subprocess.run([args.xu, 'build', str(ROOT / 'tests/steam_native_checks.xu'), '-o', str(binary)],
                   cwd=ROOT, check=True)

    # 1. Verify missing Steam library falls back cleanly
    env_missing = os.environ.copy()
    env_missing['XU_NEXUS_STEAM_LIBRARY'] = '/nonexistent/no-steam'
    env_missing['NEXUS_EXPECT_NATIVE_STEAM'] = '0'
    subprocess.run([str(binary)], cwd=ROOT, env=env_missing, check=True)

    # 2. Compile fake libsteam_api shared library and verify live dlopen + C ABI
    with tempfile.TemporaryDirectory(prefix='nexus-fake-steam-') as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / 'fake_steam.c'
        src.write_text(FAKE_STEAM_C, encoding='utf-8')
        ext = '.dylib' if platform.system() == 'Darwin' else '.so'
        lib = tmpdir / ('libfake_steam_api' + ext)
        cc = os.environ.get('CC', 'clang' if platform.system() == 'Darwin' else 'cc')
        subprocess.run([cc, '-shared', '-fPIC', '-O2', '-std=c11', str(src), '-o', str(lib)], check=True)

        env_live = os.environ.copy()
        env_live['XU_NEXUS_STEAM_LIBRARY'] = str(lib)
        env_live['NEXUS_EXPECT_NATIVE_STEAM'] = '1'
        subprocess.run([str(binary)], cwd=ROOT, env=env_live, check=True)

    print('PASS: steam_native_bridge_checks (fallback + live dlopen C ABI)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

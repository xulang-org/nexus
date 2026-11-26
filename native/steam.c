// Dynamic Steamworks C-ABI bridge. libsteam_api is loaded at runtime, never vendored.
#define _POSIX_C_SOURCE 200809L
#include "xu_native.h"
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
typedef HMODULE steam_lib_t;
#else
#include <dlfcn.h>
typedef void *steam_lib_t;
#endif

#define API(name) XU_NATIVE_SYMBOL(xu_nexus_steam_native_##name)

typedef bool (*fn_RestartAppIfNecessary)(uint32_t app_id);
typedef int (*fn_InitFlat)(char *err_msg);
typedef bool (*fn_InitSimple)(void);
typedef void (*fn_Void)(void);
typedef bool (*fn_IsRunning)(void);
typedef void *(*fn_Accessor)(void);

typedef uint64_t (*fn_User_GetSteamID)(void *);
typedef bool (*fn_User_LoggedOn)(void *);

typedef const char *(*fn_Friends_Persona)(void *);
typedef void (*fn_Friends_ActivateOverlay)(void *, const char *);
typedef bool (*fn_Friends_SetRichPresence)(void *, const char *, const char *);
typedef void (*fn_Friends_ClearRichPresence)(void *);
typedef int (*fn_Friends_GetFriendCount)(void *, int);

typedef bool (*fn_Stats_Request)(void *);
typedef bool (*fn_Stats_Store)(void *);
typedef bool (*fn_Stats_GetAch)(void *, const char *, bool *);
typedef bool (*fn_Stats_SetAch)(void *, const char *);
typedef bool (*fn_Stats_ClearAch)(void *, const char *);
typedef bool (*fn_Stats_IndProgress)(void *, const char *, uint32_t, uint32_t);
typedef bool (*fn_Stats_GetInt)(void *, const char *, int32_t *);
typedef bool (*fn_Stats_SetInt)(void *, const char *, int32_t);
typedef bool (*fn_Stats_GetFloat)(void *, const char *, float *);
typedef bool (*fn_Stats_SetFloat)(void *, const char *, float);

typedef bool (*fn_Cloud_Enabled)(void *);
typedef bool (*fn_Cloud_Write)(void *, const char *, const void *, int32_t);
typedef int32_t (*fn_Cloud_Read)(void *, const char *, void *, int32_t);
typedef bool (*fn_Cloud_Exists)(void *, const char *);
typedef bool (*fn_Cloud_Delete)(void *, const char *);
typedef int32_t (*fn_Cloud_FileCount)(void *);
typedef bool (*fn_Cloud_Quota)(void *, uint64_t *, uint64_t *);

typedef bool (*fn_Apps_IsDlcInstalled)(void *, uint32_t);
typedef const char *(*fn_Apps_Language)(void *);

typedef uint32_t (*fn_Utils_GetAppID)(void *);
typedef bool (*fn_Utils_Bool)(void *);

typedef uint64_t (*fn_Match_CreateLobby)(void *, int, int);
typedef uint64_t (*fn_Match_JoinLobby)(void *, uint64_t);
typedef void (*fn_Match_LeaveLobby)(void *, uint64_t);
typedef bool (*fn_Match_SetLobbyData)(void *, uint64_t, const char *, const char *);
typedef const char *(*fn_Match_GetLobbyData)(void *, uint64_t, const char *);
typedef int (*fn_Match_NumLobbyMembers)(void *, uint64_t);

typedef uint32_t (*fn_UGC_GetNumSubscribed)(void *);
typedef uint32_t (*fn_UGC_GetSubscribed)(void *, uint64_t *, uint32_t);
typedef bool (*fn_UGC_GetItemInstallInfo)(void *, uint64_t, uint64_t *, char *, uint32_t, uint32_t *);

static steam_lib_t steam_lib = NULL;
static bool lib_loaded = false;
static bool steam_initialized = false;
static int configured_app_id = 0;

static fn_RestartAppIfNecessary p_RestartAppIfNecessary = NULL;
static fn_InitFlat p_InitFlat = NULL;
static fn_InitSimple p_InitSimple = NULL;
static fn_Void p_Shutdown = NULL;
static fn_Void p_RunCallbacks = NULL;
static fn_IsRunning p_IsRunning = NULL;

static fn_Accessor p_SteamUser = NULL;
static fn_User_GetSteamID p_GetSteamID = NULL;
static fn_User_LoggedOn p_LoggedOn = NULL;

static fn_Accessor p_SteamFriends = NULL;
static fn_Friends_Persona p_PersonaName = NULL;
static fn_Friends_ActivateOverlay p_ActivateOverlay = NULL;
static fn_Friends_SetRichPresence p_SetRichPresence = NULL;
static fn_Friends_ClearRichPresence p_ClearRichPresence = NULL;
static fn_Friends_GetFriendCount p_GetFriendCount = NULL;

static fn_Accessor p_SteamUserStats = NULL;
static fn_Stats_Request p_RequestCurrentStats = NULL;
static fn_Stats_Store p_StoreStats = NULL;
static fn_Stats_GetAch p_GetAchievement = NULL;
static fn_Stats_SetAch p_SetAchievement = NULL;
static fn_Stats_ClearAch p_ClearAchievement = NULL;
static fn_Stats_IndProgress p_IndicateProgress = NULL;
static fn_Stats_GetInt p_GetStatInt = NULL;
static fn_Stats_SetInt p_SetStatInt = NULL;
static fn_Stats_GetFloat p_GetStatFloat = NULL;
static fn_Stats_SetFloat p_SetStatFloat = NULL;

static fn_Accessor p_SteamRemoteStorage = NULL;
static fn_Cloud_Enabled p_CloudEnabledApp = NULL;
static fn_Cloud_Enabled p_CloudEnabledAcct = NULL;
static fn_Cloud_Write p_CloudWrite = NULL;
static fn_Cloud_Read p_CloudRead = NULL;
static fn_Cloud_Exists p_CloudExists = NULL;
static fn_Cloud_Delete p_CloudDelete = NULL;
static fn_Cloud_FileCount p_CloudFileCount = NULL;
static fn_Cloud_Quota p_CloudQuota = NULL;

static fn_Accessor p_SteamApps = NULL;
static fn_Apps_IsDlcInstalled p_IsDlcInstalled = NULL;
static fn_Apps_Language p_CurrentGameLanguage = NULL;

static fn_Accessor p_SteamUtils = NULL;
static fn_Utils_GetAppID p_UtilsGetAppID = NULL;
static fn_Utils_Bool p_UtilsOverlayEnabled = NULL;
static fn_Utils_Bool p_UtilsIsSteamDeck = NULL;
static fn_Utils_Bool p_UtilsIsBigPicture = NULL;

static fn_Accessor p_SteamMatchmaking = NULL;
static fn_Match_CreateLobby p_CreateLobby = NULL;
static fn_Match_JoinLobby p_JoinLobby = NULL;
static fn_Match_LeaveLobby p_LeaveLobby = NULL;
static fn_Match_SetLobbyData p_SetLobbyData = NULL;
static fn_Match_GetLobbyData p_GetLobbyData = NULL;
static fn_Match_NumLobbyMembers p_GetNumLobbyMembers = NULL;

static fn_Accessor p_SteamUGC = NULL;
static fn_UGC_GetNumSubscribed p_UGCGetNumSubscribed = NULL;
static fn_UGC_GetSubscribed p_UGCGetSubscribed = NULL;
static fn_UGC_GetItemInstallInfo p_UGCGetItemInstallInfo = NULL;

static _Thread_local char last_error[1024];

static xu_int fail(const char *msg) {
    snprintf(last_error, sizeof(last_error), "%s", msg ? msg : "unknown steam error");
    return -1;
}

static void clear_err(void) {
    last_error[0] = '\0';
}

static void *find_sym(const char *name) {
    if (!steam_lib || !name) return NULL;
#ifdef _WIN32
    return (void *)GetProcAddress(steam_lib, name);
#else
    return dlsym(steam_lib, name);
#endif
}

static void *find_any_sym(const char **names, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        void *s = find_sym(names[i]);
        if (s) return s;
    }
    return NULL;
}

static bool load_steam_library(void) {
    if (lib_loaded) return true;
#ifdef _WIN32
    const char *override = getenv("XU_NEXUS_STEAM_LIBRARY");
    const char *candidates[] = {"steam_api64.dll", "steam_api.dll"};
    if (override && *override) {
        steam_lib = LoadLibraryA(override);
    } else {
        for (size_t i = 0; !steam_lib && i < sizeof(candidates) / sizeof(candidates[0]); ++i) {
            steam_lib = LoadLibraryA(candidates[i]);
        }
    }
#else
    const char *override = getenv("XU_NEXUS_STEAM_LIBRARY");
    if (override && *override) {
        steam_lib = dlopen(override, RTLD_NOW | RTLD_LOCAL);
    } else {
#ifdef __APPLE__
        const char *candidates[] = {"./libsteam_api.dylib", "libsteam_api.dylib", "../Frameworks/libsteam_api.dylib"};
#else
        const char *candidates[] = {"./libsteam_api.so", "libsteam_api.so"};
#endif
        for (size_t i = 0; !steam_lib && i < sizeof(candidates) / sizeof(candidates[0]); ++i) {
            steam_lib = dlopen(candidates[i], RTLD_NOW | RTLD_LOCAL);
        }
    }
#endif
    if (!steam_lib) {
        fail("Steamworks runtime library not found; set XU_NEXUS_STEAM_LIBRARY or ship libsteam_api");
        return false;
    }
    p_RestartAppIfNecessary = (fn_RestartAppIfNecessary)find_sym("SteamAPI_RestartAppIfNecessary");
    p_InitFlat = (fn_InitFlat)find_sym("SteamAPI_InitFlat");
    p_InitSimple = (fn_InitSimple)find_sym("SteamAPI_Init");
    p_Shutdown = (fn_Void)find_sym("SteamAPI_Shutdown");
    p_RunCallbacks = (fn_Void)find_sym("SteamAPI_RunCallbacks");
    p_IsRunning = (fn_IsRunning)find_sym("SteamAPI_IsSteamRunning");
    if ((!p_InitFlat && !p_InitSimple) || !p_Shutdown || !p_RunCallbacks) {
#ifdef _WIN32
        FreeLibrary(steam_lib);
#else
        dlclose(steam_lib);
#endif
        steam_lib = NULL;
        fail("Steamworks library missing SteamAPI_Init/Shutdown/RunCallbacks");
        return false;
    }

    const char *user_accs[] = {"SteamAPI_SteamUser_v023", "SteamAPI_SteamUser_v021", "SteamUser"};
    p_SteamUser = (fn_Accessor)find_any_sym(user_accs, sizeof(user_accs) / sizeof(user_accs[0]));
    p_GetSteamID = (fn_User_GetSteamID)find_sym("SteamAPI_ISteamUser_GetSteamID");
    p_LoggedOn = (fn_User_LoggedOn)find_sym("SteamAPI_ISteamUser_BLoggedOn");

    const char *friends_accs[] = {"SteamAPI_SteamFriends_v017", "SteamFriends"};
    p_SteamFriends = (fn_Accessor)find_any_sym(friends_accs, sizeof(friends_accs) / sizeof(friends_accs[0]));
    p_PersonaName = (fn_Friends_Persona)find_sym("SteamAPI_ISteamFriends_GetPersonaName");
    p_ActivateOverlay = (fn_Friends_ActivateOverlay)find_sym("SteamAPI_ISteamFriends_ActivateGameOverlay");
    p_SetRichPresence = (fn_Friends_SetRichPresence)find_sym("SteamAPI_ISteamFriends_SetRichPresence");
    p_ClearRichPresence = (fn_Friends_ClearRichPresence)find_sym("SteamAPI_ISteamFriends_ClearRichPresence");
    p_GetFriendCount = (fn_Friends_GetFriendCount)find_sym("SteamAPI_ISteamFriends_GetFriendCount");

    const char *stats_accs[] = {"SteamAPI_SteamUserStats_v013", "SteamAPI_SteamUserStats_v012", "SteamUserStats"};
    p_SteamUserStats = (fn_Accessor)find_any_sym(stats_accs, sizeof(stats_accs) / sizeof(stats_accs[0]));
    p_RequestCurrentStats = (fn_Stats_Request)find_sym("SteamAPI_ISteamUserStats_RequestCurrentStats");
    p_StoreStats = (fn_Stats_Store)find_sym("SteamAPI_ISteamUserStats_StoreStats");
    p_GetAchievement = (fn_Stats_GetAch)find_sym("SteamAPI_ISteamUserStats_GetAchievement");
    p_SetAchievement = (fn_Stats_SetAch)find_sym("SteamAPI_ISteamUserStats_SetAchievement");
    p_ClearAchievement = (fn_Stats_ClearAch)find_sym("SteamAPI_ISteamUserStats_ClearAchievement");
    p_IndicateProgress = (fn_Stats_IndProgress)find_sym("SteamAPI_ISteamUserStats_IndicateAchievementProgress");
    p_GetStatInt = (fn_Stats_GetInt)find_sym("SteamAPI_ISteamUserStats_GetStatInt32");
    p_SetStatInt = (fn_Stats_SetInt)find_sym("SteamAPI_ISteamUserStats_SetStatInt32");
    p_GetStatFloat = (fn_Stats_GetFloat)find_sym("SteamAPI_ISteamUserStats_GetStatFloat");
    p_SetStatFloat = (fn_Stats_SetFloat)find_sym("SteamAPI_ISteamUserStats_SetStatFloat");

    const char *cloud_accs[] = {"SteamAPI_SteamRemoteStorage_v016", "SteamAPI_SteamRemoteStorage_v014", "SteamRemoteStorage"};
    p_SteamRemoteStorage = (fn_Accessor)find_any_sym(cloud_accs, sizeof(cloud_accs) / sizeof(cloud_accs[0]));
    p_CloudEnabledApp = (fn_Cloud_Enabled)find_sym("SteamAPI_ISteamRemoteStorage_IsCloudEnabledForApp");
    p_CloudEnabledAcct = (fn_Cloud_Enabled)find_sym("SteamAPI_ISteamRemoteStorage_IsCloudEnabledForAccount");
    p_CloudWrite = (fn_Cloud_Write)find_sym("SteamAPI_ISteamRemoteStorage_FileWrite");
    p_CloudRead = (fn_Cloud_Read)find_sym("SteamAPI_ISteamRemoteStorage_FileRead");
    p_CloudExists = (fn_Cloud_Exists)find_sym("SteamAPI_ISteamRemoteStorage_FileExists");
    p_CloudDelete = (fn_Cloud_Delete)find_sym("SteamAPI_ISteamRemoteStorage_FileDelete");
    p_CloudFileCount = (fn_Cloud_FileCount)find_sym("SteamAPI_ISteamRemoteStorage_GetFileCount");
    p_CloudQuota = (fn_Cloud_Quota)find_sym("SteamAPI_ISteamRemoteStorage_GetQuota");

    const char *apps_accs[] = {"SteamAPI_SteamApps_v008", "SteamApps"};
    p_SteamApps = (fn_Accessor)find_any_sym(apps_accs, sizeof(apps_accs) / sizeof(apps_accs[0]));
    p_IsDlcInstalled = (fn_Apps_IsDlcInstalled)find_sym("SteamAPI_ISteamApps_BIsDlcInstalled");
    p_CurrentGameLanguage = (fn_Apps_Language)find_sym("SteamAPI_ISteamApps_GetCurrentGameLanguage");

    const char *utils_accs[] = {"SteamAPI_SteamUtils_v010", "SteamAPI_SteamUtils_v009", "SteamUtils"};
    p_SteamUtils = (fn_Accessor)find_any_sym(utils_accs, sizeof(utils_accs) / sizeof(utils_accs[0]));
    p_UtilsGetAppID = (fn_Utils_GetAppID)find_sym("SteamAPI_ISteamUtils_GetAppID");
    p_UtilsOverlayEnabled = (fn_Utils_Bool)find_sym("SteamAPI_ISteamUtils_IsOverlayEnabled");
    p_UtilsIsSteamDeck = (fn_Utils_Bool)find_sym("SteamAPI_ISteamUtils_IsSteamRunningOnSteamDeck");
    p_UtilsIsBigPicture = (fn_Utils_Bool)find_sym("SteamAPI_ISteamUtils_IsSteamInBigPictureMode");

    const char *match_accs[] = {"SteamAPI_SteamMatchmaking_v009", "SteamMatchmaking"};
    p_SteamMatchmaking = (fn_Accessor)find_any_sym(match_accs, sizeof(match_accs) / sizeof(match_accs[0]));
    p_CreateLobby = (fn_Match_CreateLobby)find_sym("SteamAPI_ISteamMatchmaking_CreateLobby");
    p_JoinLobby = (fn_Match_JoinLobby)find_sym("SteamAPI_ISteamMatchmaking_JoinLobby");
    p_LeaveLobby = (fn_Match_LeaveLobby)find_sym("SteamAPI_ISteamMatchmaking_LeaveLobby");
    p_SetLobbyData = (fn_Match_SetLobbyData)find_sym("SteamAPI_ISteamMatchmaking_SetLobbyData");
    p_GetLobbyData = (fn_Match_GetLobbyData)find_sym("SteamAPI_ISteamMatchmaking_GetLobbyData");
    p_GetNumLobbyMembers = (fn_Match_NumLobbyMembers)find_sym("SteamAPI_ISteamMatchmaking_GetNumLobbyMembers");

    const char *ugc_accs[] = {"SteamAPI_SteamUGC_v020", "SteamAPI_SteamUGC_v018", "SteamUGC"};
    p_SteamUGC = (fn_Accessor)find_any_sym(ugc_accs, sizeof(ugc_accs) / sizeof(ugc_accs[0]));
    p_UGCGetNumSubscribed = (fn_UGC_GetNumSubscribed)find_sym("SteamAPI_ISteamUGC_GetNumSubscribedItems");
    p_UGCGetSubscribed = (fn_UGC_GetSubscribed)find_sym("SteamAPI_ISteamUGC_GetSubscribedItems");
    p_UGCGetItemInstallInfo = (fn_UGC_GetItemInstallInfo)find_sym("SteamAPI_ISteamUGC_GetItemInstallInfo");

    lib_loaded = true;
    clear_err();
    return true;
}

static bool copy_cstr(const xu_u8_span *span, char *out, size_t cap) {
    if (!span || !out || cap == 0) { fail("null string span"); return false; }
    if (span->len < 0 || (size_t)span->len >= cap) { fail("string span exceeds buffer"); return false; }
    if (span->len > 0 && !span->data) { fail("null span data"); return false; }
    for (xu_int i = 0; i < span->len; ++i) {
        if (span->data[i] == 0) { fail("embedded NUL byte in string span"); return false; }
        out[i] = (char)span->data[i];
    }
    out[span->len] = '\0';
    return true;
}

static xu_int write_cstr(const char *src, const xu_u8_span_mut *out) {
    if (!out || !out->data || out->len < 0) return fail("invalid mutable byte span");
    if (!src) return 0;
    size_t len = strlen(src);
    if ((xu_int)len > out->len) len = (size_t)out->len;
    if (len > 0) memcpy(out->data, src, len);
    return (xu_int)len;
}

static bool require_init(void) {
    if (!lib_loaded || !steam_initialized) {
        fail("Steamworks is not initialized");
        return false;
    }
    return true;
}

xu_int API(error_len)(void) { return (xu_int)strlen(last_error); }
xu_int API(error_byte)(xu_int index) {
    return index >= 0 && (uint64_t)index < strlen(last_error) ? (unsigned char)last_error[index] : 0;
}

xu_int API(is_available)(void) {
    return load_steam_library() ? 1 : 0;
}

xu_int API(restart_if_necessary)(xu_int app_id_val) {
    if (app_id_val <= 0 || app_id_val > 0x7fffffffLL) return fail("invalid Steam app_id");
    if (!load_steam_library()) return -1;
    if (!p_RestartAppIfNecessary) return 0;
    return p_RestartAppIfNecessary((uint32_t)app_id_val) ? 1 : 0;
}

xu_int API(init)(xu_int app_id_val) {
    if (!load_steam_library()) return -1;
    if (app_id_val > 0) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%llu", (unsigned long long)app_id_val);
#ifndef _WIN32
        setenv("SteamAppId", buf, 0);
        setenv("SteamGameId", buf, 0);
#else
        SetEnvironmentVariableA("SteamAppId", buf);
        SetEnvironmentVariableA("SteamGameId", buf);
#endif
        configured_app_id = (int)app_id_val;
    }
    if (p_InitFlat) {
        char err_msg[1024] = {0};
        int res = p_InitFlat(err_msg);
        if (res != 0) {
            return fail(err_msg[0] ? err_msg : "SteamAPI_InitFlat returned failure");
        }
    } else if (p_InitSimple) {
        if (!p_InitSimple()) {
            return fail("SteamAPI_Init returned false");
        }
    } else {
        return fail("Steamworks init symbol unavailable");
    }
    steam_initialized = true;
    clear_err();
    return 0;
}

xu_int API(shutdown)(void) {
    if (steam_initialized && p_Shutdown) {
        p_Shutdown();
    }
    steam_initialized = false;
    clear_err();
    return 0;
}

xu_int API(run_callbacks)(void) {
    if (!require_init()) return -1;
    p_RunCallbacks();
    return 0;
}

xu_int API(is_running)(void) {
    if (!lib_loaded) return 0;
    if (p_IsRunning) return p_IsRunning() ? 1 : 0;
    return steam_initialized ? 1 : 0;
}

xu_int API(app_id)(void) {
    if (!require_init()) return -1;
    if (p_SteamUtils && p_UtilsGetAppID) {
        void *u = p_SteamUtils();
        if (u) return (xu_int)p_UtilsGetAppID(u);
    }
    return (xu_int)configured_app_id;
}

xu_int API(steam_id)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUser || !p_GetSteamID) return 0;
    void *u = p_SteamUser();
    if (!u) return 0;
    uint64_t sid = p_GetSteamID(u);
    return (xu_int)(sid & 0x7fffffffffffffffULL);
}

xu_int API(logged_on)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUser || !p_LoggedOn) return 0;
    void *u = p_SteamUser();
    return (u && p_LoggedOn(u)) ? 1 : 0;
}

xu_int API(persona_name)(const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    if (!p_SteamFriends || !p_PersonaName) return write_cstr("", out);
    void *f = p_SteamFriends();
    return write_cstr(f ? p_PersonaName(f) : "", out);
}

xu_int API(game_language)(const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    if (!p_SteamApps || !p_CurrentGameLanguage) return write_cstr("english", out);
    void *a = p_SteamApps();
    const char *lang = a ? p_CurrentGameLanguage(a) : NULL;
    return write_cstr(lang && *lang ? lang : "english", out);
}

xu_int API(is_overlay_enabled)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUtils || !p_UtilsOverlayEnabled) return 0;
    void *u = p_SteamUtils();
    return (u && p_UtilsOverlayEnabled(u)) ? 1 : 0;
}

xu_int API(is_steam_deck)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUtils || !p_UtilsIsSteamDeck) return 0;
    void *u = p_SteamUtils();
    return (u && p_UtilsIsSteamDeck(u)) ? 1 : 0;
}

xu_int API(is_big_picture)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUtils || !p_UtilsIsBigPicture) return 0;
    void *u = p_SteamUtils();
    return (u && p_UtilsIsBigPicture(u)) ? 1 : 0;
}

xu_int API(activate_overlay)(const xu_u8_span *dialog) {
    if (!require_init()) return -1;
    char buf[128];
    if (!copy_cstr(dialog, buf, sizeof(buf))) return -1;
    if (!p_SteamFriends || !p_ActivateOverlay) return fail("SteamFriends overlay interface unavailable");
    void *f = p_SteamFriends();
    if (!f) return fail("SteamFriends singleton null");
    p_ActivateOverlay(f, buf);
    return 0;
}

xu_int API(set_rich_presence)(const xu_u8_span *key, const xu_u8_span *val) {
    if (!require_init()) return -1;
    char k[256], v[512];
    if (!copy_cstr(key, k, sizeof(k)) || !copy_cstr(val, v, sizeof(v))) return -1;
    if (!p_SteamFriends || !p_SetRichPresence) return fail("SteamFriends rich presence unavailable");
    void *f = p_SteamFriends();
    return (f && p_SetRichPresence(f, k, v)) ? 0 : fail("SetRichPresence failed");
}

xu_int API(clear_rich_presence)(void) {
    if (!require_init()) return -1;
    if (!p_SteamFriends || !p_ClearRichPresence) return 0;
    void *f = p_SteamFriends();
    if (f) p_ClearRichPresence(f);
    return 0;
}

xu_int API(friend_count)(void) {
    if (!require_init()) return -1;
    if (!p_SteamFriends || !p_GetFriendCount) return 0;
    void *f = p_SteamFriends();
    return f ? (xu_int)p_GetFriendCount(f, 0x04) : 0;
}

xu_int API(request_stats)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUserStats || !p_RequestCurrentStats) return 0;
    void *s = p_SteamUserStats();
    return (s && p_RequestCurrentStats(s)) ? 0 : fail("RequestCurrentStats failed");
}

xu_int API(get_achievement)(const xu_u8_span *id) {
    if (!require_init()) return -1;
    char aid[256];
    if (!copy_cstr(id, aid, sizeof(aid))) return -1;
    if (!p_SteamUserStats || !p_GetAchievement) return fail("SteamUserStats unavailable");
    void *s = p_SteamUserStats();
    bool achieved = false;
    if (!s || !p_GetAchievement(s, aid, &achieved)) return fail("GetAchievement failed");
    return achieved ? 1 : 0;
}

xu_int API(set_achievement)(const xu_u8_span *id) {
    if (!require_init()) return -1;
    char aid[256];
    if (!copy_cstr(id, aid, sizeof(aid))) return -1;
    if (!p_SteamUserStats || !p_SetAchievement) return fail("SteamUserStats unavailable");
    void *s = p_SteamUserStats();
    return (s && p_SetAchievement(s, aid)) ? 0 : fail("SetAchievement failed");
}

xu_int API(clear_achievement)(const xu_u8_span *id) {
    if (!require_init()) return -1;
    char aid[256];
    if (!copy_cstr(id, aid, sizeof(aid))) return -1;
    if (!p_SteamUserStats || !p_ClearAchievement) return fail("SteamUserStats unavailable");
    void *s = p_SteamUserStats();
    return (s && p_ClearAchievement(s, aid)) ? 0 : fail("ClearAchievement failed");
}

xu_int API(indicate_achievement_progress)(const xu_u8_span *id, xu_int cur, xu_int maxv) {
    if (!require_init()) return -1;
    char aid[256];
    if (!copy_cstr(id, aid, sizeof(aid))) return -1;
    if (cur < 0 || maxv <= 0) return fail("invalid achievement progress values");
    if (!p_SteamUserStats || !p_IndicateProgress) return fail("IndicateAchievementProgress unavailable");
    void *s = p_SteamUserStats();
    return (s && p_IndicateProgress(s, aid, (uint32_t)cur, (uint32_t)maxv)) ? 0 : fail("IndicateAchievementProgress failed");
}

xu_int API(get_stat_int)(const xu_u8_span *id, const xu_i64_span_mut *out) {
    if (!require_init()) return -1;
    if (!out || !out->data || out->len < 1) return fail("invalid output span for stat");
    char sid[256];
    if (!copy_cstr(id, sid, sizeof(sid))) return -1;
    if (!p_SteamUserStats || !p_GetStatInt) return fail("SteamUserStats GetStatInt32 unavailable");
    void *s = p_SteamUserStats();
    int32_t val = 0;
    if (!s || !p_GetStatInt(s, sid, &val)) return fail("GetStatInt32 failed");
    out->data[0] = (xu_int)val;
    return 0;
}

xu_int API(set_stat_int)(const xu_u8_span *id, xu_int val) {
    if (!require_init()) return -1;
    char sid[256];
    if (!copy_cstr(id, sid, sizeof(sid))) return -1;
    if (!p_SteamUserStats || !p_SetStatInt) return fail("SteamUserStats SetStatInt32 unavailable");
    void *s = p_SteamUserStats();
    return (s && p_SetStatInt(s, sid, (int32_t)val)) ? 0 : fail("SetStatInt32 failed");
}

double API(get_stat_float)(const xu_u8_span *id) {
    if (!require_init()) return NAN;
    char sid[256];
    if (!copy_cstr(id, sid, sizeof(sid))) return NAN;
    if (!p_SteamUserStats || !p_GetStatFloat) { fail("SteamUserStats GetStatFloat unavailable"); return NAN; }
    void *s = p_SteamUserStats();
    float val = 0.0f;
    if (!s || !p_GetStatFloat(s, sid, &val)) { fail("GetStatFloat failed"); return NAN; }
    clear_err();
    return (double)val;
}

xu_int API(set_stat_float)(const xu_u8_span *id, double val) {
    if (!require_init()) return -1;
    if (isnan(val) || isinf(val)) return fail("stat float must be finite");
    char sid[256];
    if (!copy_cstr(id, sid, sizeof(sid))) return -1;
    if (!p_SteamUserStats || !p_SetStatFloat) return fail("SteamUserStats SetStatFloat unavailable");
    void *s = p_SteamUserStats();
    return (s && p_SetStatFloat(s, sid, (float)val)) ? 0 : fail("SetStatFloat failed");
}

xu_int API(store_stats)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUserStats || !p_StoreStats) return fail("SteamUserStats StoreStats unavailable");
    void *s = p_SteamUserStats();
    return (s && p_StoreStats(s)) ? 0 : fail("StoreStats failed");
}

xu_int API(cloud_enabled)(void) {
    if (!require_init()) return -1;
    if (!p_SteamRemoteStorage) return 0;
    void *rs = p_SteamRemoteStorage();
    if (!rs) return 0;
    bool app_ok = p_CloudEnabledApp ? p_CloudEnabledApp(rs) : true;
    bool acct_ok = p_CloudEnabledAcct ? p_CloudEnabledAcct(rs) : true;
    return (app_ok && acct_ok) ? 1 : 0;
}

xu_int API(cloud_write)(const xu_u8_span *filename, const xu_u8_span *data) {
    if (!require_init()) return -1;
    char path[260];
    if (!copy_cstr(filename, path, sizeof(path))) return -1;
    if (!data || data->len < 0 || data->len > 16 * 1024 * 1024) return fail("invalid cloud write buffer");
    if (!p_SteamRemoteStorage || !p_CloudWrite) return fail("SteamRemoteStorage FileWrite unavailable");
    void *rs = p_SteamRemoteStorage();
    if (!rs) return fail("SteamRemoteStorage singleton null");
    return p_CloudWrite(rs, path, data->data, (int32_t)data->len) ? 0 : fail("Steam Cloud FileWrite failed");
}

xu_int API(cloud_read)(const xu_u8_span *filename, const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    char path[260];
    if (!copy_cstr(filename, path, sizeof(path))) return -1;
    if (!out || !out->data || out->len <= 0) return fail("invalid cloud read buffer");
    if (!p_SteamRemoteStorage || !p_CloudRead) return fail("SteamRemoteStorage FileRead unavailable");
    void *rs = p_SteamRemoteStorage();
    if (!rs) return fail("SteamRemoteStorage singleton null");
    int32_t n = p_CloudRead(rs, path, out->data, (int32_t)out->len);
    if (n < 0) return fail("Steam Cloud FileRead failed");
    return (xu_int)n;
}

xu_int API(cloud_exists)(const xu_u8_span *filename) {
    if (!require_init()) return -1;
    char path[260];
    if (!copy_cstr(filename, path, sizeof(path))) return -1;
    if (!p_SteamRemoteStorage || !p_CloudExists) return 0;
    void *rs = p_SteamRemoteStorage();
    return (rs && p_CloudExists(rs, path)) ? 1 : 0;
}

xu_int API(cloud_delete)(const xu_u8_span *filename) {
    if (!require_init()) return -1;
    char path[260];
    if (!copy_cstr(filename, path, sizeof(path))) return -1;
    if (!p_SteamRemoteStorage || !p_CloudDelete) return fail("SteamRemoteStorage FileDelete unavailable");
    void *rs = p_SteamRemoteStorage();
    return (rs && p_CloudDelete(rs, path)) ? 0 : fail("Steam Cloud FileDelete failed");
}

xu_int API(cloud_file_count)(void) {
    if (!require_init()) return -1;
    if (!p_SteamRemoteStorage || !p_CloudFileCount) return 0;
    void *rs = p_SteamRemoteStorage();
    return rs ? (xu_int)p_CloudFileCount(rs) : 0;
}

xu_int API(cloud_quota)(const xu_i64_span_mut *out) {
    if (!require_init()) return -1;
    if (!out || !out->data || out->len < 2) return fail("cloud_quota requires 2-element i64 buffer");
    if (!p_SteamRemoteStorage || !p_CloudQuota) return fail("SteamRemoteStorage GetQuota unavailable");
    void *rs = p_SteamRemoteStorage();
    uint64_t total = 0, avail = 0;
    if (!rs || !p_CloudQuota(rs, &total, &avail)) return fail("Steam Cloud GetQuota failed");
    out->data[0] = (xu_int)total;
    out->data[1] = (xu_int)avail;
    return 0;
}

xu_int API(is_dlc_installed)(xu_int dlc_app_id) {
    if (!require_init()) return -1;
    if (dlc_app_id <= 0) return 0;
    if (!p_SteamApps || !p_IsDlcInstalled) return 0;
    void *a = p_SteamApps();
    return (a && p_IsDlcInstalled(a, (uint32_t)dlc_app_id)) ? 1 : 0;
}

xu_int API(subscribed_ugc_count)(void) {
    if (!require_init()) return -1;
    if (!p_SteamUGC || !p_UGCGetNumSubscribed) return 0;
    void *u = p_SteamUGC();
    return u ? (xu_int)p_UGCGetNumSubscribed(u) : 0;
}

xu_int API(subscribed_ugc_ids)(const xu_i64_span_mut *out) {
    if (!require_init()) return -1;
    if (!out || !out->data || out->len <= 0) return 0;
    if (!p_SteamUGC || !p_UGCGetSubscribed) return 0;
    void *u = p_SteamUGC();
    if (!u) return 0;
    uint32_t max_items = out->len > 256 ? 256 : (uint32_t)out->len;
    uint64_t tmp[256];
    uint32_t count = p_UGCGetSubscribed(u, tmp, max_items);
    if (count > max_items) count = max_items;
    for (uint32_t i = 0; i < count; ++i) out->data[i] = (xu_int)tmp[i];
    return (xu_int)count;
}

xu_int API(ugc_install_info)(xu_int published_file_id, const xu_u8_span_mut *folder_out, const xu_i64_span_mut *meta_out) {
    if (!require_init()) return -1;
    if (!folder_out || !folder_out->data || folder_out->len <= 0) return fail("invalid UGC folder buffer");
    if (!meta_out || !meta_out->data || meta_out->len < 2) return fail("invalid UGC metadata buffer");
    if (!p_SteamUGC || !p_UGCGetItemInstallInfo) return fail("SteamUGC GetItemInstallInfo unavailable");
    void *u = p_SteamUGC();
    if (!u) return fail("SteamUGC singleton null");
    uint64_t size_on_disk = 0;
    uint32_t timestamp = 0;
    char path_buf[1024] = {0};
    if (!p_UGCGetItemInstallInfo(u, (uint64_t)published_file_id, &size_on_disk, path_buf, sizeof(path_buf), &timestamp)) {
        return fail("UGC item not installed");
    }
    meta_out->data[0] = (xu_int)size_on_disk;
    meta_out->data[1] = (xu_int)timestamp;
    return write_cstr(path_buf, folder_out);
}

xu_int API(lobby_create)(xu_int visibility, xu_int max_members) {
    if (!require_init()) return -1;
    if (!p_SteamMatchmaking || !p_CreateLobby) return fail("SteamMatchmaking CreateLobby unavailable");
    void *m = p_SteamMatchmaking();
    if (!m) return fail("SteamMatchmaking singleton null");
    return (xu_int)p_CreateLobby(m, (int)visibility, (int)max_members);
}

xu_int API(lobby_join)(xu_int lobby_id) {
    if (!require_init()) return -1;
    if (!p_SteamMatchmaking || !p_JoinLobby) return fail("SteamMatchmaking JoinLobby unavailable");
    void *m = p_SteamMatchmaking();
    if (!m) return fail("SteamMatchmaking singleton null");
    return (xu_int)p_JoinLobby(m, (uint64_t)lobby_id);
}

xu_int API(lobby_leave)(xu_int lobby_id) {
    if (!require_init()) return -1;
    if (!p_SteamMatchmaking || !p_LeaveLobby) return 0;
    void *m = p_SteamMatchmaking();
    if (m) p_LeaveLobby(m, (uint64_t)lobby_id);
    return 0;
}

xu_int API(lobby_set_data)(xu_int lobby_id, const xu_u8_span *key, const xu_u8_span *val) {
    if (!require_init()) return -1;
    char k[256], v[1024];
    if (!copy_cstr(key, k, sizeof(k)) || !copy_cstr(val, v, sizeof(v))) return -1;
    if (!p_SteamMatchmaking || !p_SetLobbyData) return fail("SteamMatchmaking SetLobbyData unavailable");
    void *m = p_SteamMatchmaking();
    return (m && p_SetLobbyData(m, (uint64_t)lobby_id, k, v)) ? 0 : fail("SetLobbyData failed");
}

xu_int API(lobby_get_data)(xu_int lobby_id, const xu_u8_span *key, const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    char k[256];
    if (!copy_cstr(key, k, sizeof(k))) return -1;
    if (!p_SteamMatchmaking || !p_GetLobbyData) return fail("SteamMatchmaking GetLobbyData unavailable");
    void *m = p_SteamMatchmaking();
    if (!m) return fail("SteamMatchmaking singleton null");
    const char *v = p_GetLobbyData(m, (uint64_t)lobby_id, k);
    return write_cstr(v ? v : "", out);
}

xu_int API(lobby_member_count)(xu_int lobby_id) {
    if (!require_init()) return -1;
    if (!p_SteamMatchmaking || !p_GetNumLobbyMembers) return 0;
    void *m = p_SteamMatchmaking();
    return m ? (xu_int)p_GetNumLobbyMembers(m, (uint64_t)lobby_id) : 0;
}

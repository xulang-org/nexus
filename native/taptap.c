// Runtime-loaded TapSDK v4 C ABI adapter (CN & Global; Android / iOS / PC).
// Never vendors proprietary TapTap SDK headers or binaries.
#define _POSIX_C_SOURCE 200809L
#include "xu_native.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
typedef HMODULE taptap_lib_t;
#else
#include <dlfcn.h>
typedef void *taptap_lib_t;
#endif

#define API(name) XU_NATIVE_SYMBOL(xu_nexus_taptap_native_##name)

typedef int (*fn_t_restart)(const char *client_id);
typedef int (*fn_t_init)(const char *client_id, const char *client_token, int region, int target_platform);
typedef void (*fn_t_void)(void);
typedef int (*fn_t_int)(void);
typedef int (*fn_t_poll)(int64_t *events_out, int cap);
typedef int (*fn_t_str)(const char *s);
typedef int (*fn_t_str_out)(char *out, int cap);
typedef int (*fn_t_i1)(int v);
typedef int (*fn_t_str_i2)(const char *s, int a, int b);
typedef int (*fn_t_str_i1)(const char *s, int a);
typedef int (*fn_t_cloud_write)(const char *name, const char *summary, const uint8_t *data, int len);
typedef int (*fn_t_cloud_read)(const char *name, uint8_t *out, int cap);

static taptap_lib_t tap_lib = NULL;
static bool initialized = false;

static fn_t_restart p_restart = NULL;
static fn_t_init p_init = NULL;
static fn_t_void p_shutdown = NULL;
static fn_t_poll p_poll = NULL;
static fn_t_str p_login = NULL;
static fn_t_int p_logout = NULL;
static fn_t_int p_is_logged_in = NULL;
static fn_t_str_out p_open_id = NULL;
static fn_t_str_out p_union_id = NULL;
static fn_t_str_out p_user_name = NULL;
static fn_t_int p_comp_startup = NULL;
static fn_t_int p_comp_exit = NULL;
static fn_t_int p_comp_age = NULL;
static fn_t_int p_comp_rem = NULL;
static fn_t_int p_comp_status = NULL;
static fn_t_i1 p_comp_chk_pay = NULL;
static fn_t_i1 p_comp_sub_pay = NULL;
static fn_t_int p_verify_license = NULL;
static fn_t_str p_has_dlc = NULL;
static fn_t_str p_query_dlc = NULL;
static fn_t_str p_unlock_ach = NULL;
static fn_t_str_i2 p_inc_ach = NULL;
static fn_t_str p_has_ach = NULL;
static fn_t_cloud_write p_cloud_write = NULL;
static fn_t_cloud_read p_cloud_read = NULL;
static fn_t_str p_cloud_exists = NULL;
static fn_t_str p_cloud_delete = NULL;
static fn_t_str_i1 p_lb_submit = NULL;
static fn_t_str p_open_moment = NULL;
static fn_t_int p_moment_open = NULL;
static fn_t_int p_check_update = NULL;

static _Thread_local char last_error[1024];

static xu_int fail(const char *msg) {
    snprintf(last_error, sizeof(last_error), "%s", msg ? msg : "unknown taptap driver error");
    return -1;
}

static void unload_taptap(void) {
    if (tap_lib) {
#ifdef _WIN32
        FreeLibrary(tap_lib);
#else
        dlclose(tap_lib);
#endif
        tap_lib = NULL;
    }
    initialized = false;
    p_restart = NULL;
    p_init = NULL;
    p_shutdown = NULL;
    p_poll = NULL;
    p_login = NULL;
    p_logout = NULL;
    p_is_logged_in = NULL;
    p_open_id = NULL;
    p_union_id = NULL;
    p_user_name = NULL;
    p_comp_startup = NULL;
    p_comp_exit = NULL;
    p_comp_age = NULL;
    p_comp_rem = NULL;
    p_comp_status = NULL;
    p_comp_chk_pay = NULL;
    p_comp_sub_pay = NULL;
    p_verify_license = NULL;
    p_has_dlc = NULL;
    p_query_dlc = NULL;
    p_unlock_ach = NULL;
    p_inc_ach = NULL;
    p_has_ach = NULL;
    p_cloud_write = NULL;
    p_cloud_read = NULL;
    p_cloud_exists = NULL;
    p_cloud_delete = NULL;
    p_lb_submit = NULL;
    p_open_moment = NULL;
    p_moment_open = NULL;
    p_check_update = NULL;
}

static void *find_sym(const char *name) {
    if (!tap_lib || !name) return NULL;
#ifdef _WIN32
    return (void *)GetProcAddress(tap_lib, name);
#else
    return dlsym(tap_lib, name);
#endif
}

static bool load_taptap(void) {
    if (tap_lib) return true;
    const char *override = getenv("XU_NEXUS_TAPTAP_LIBRARY");
#ifdef _WIN32
    const char *cands[] = {"nexus_taptap_sdk.dll", "taptap_api64.dll"};
    if (override && *override) {
        tap_lib = LoadLibraryA(override);
    } else {
        for (size_t i = 0; !tap_lib && i < 2; ++i) {
            tap_lib = LoadLibraryA(cands[i]);
        }
    }
#else
    if (override && *override) {
        tap_lib = dlopen(override, RTLD_NOW | RTLD_LOCAL);
    } else {
#ifdef __APPLE__
        const char *cands[] = {"./libnexus_taptap_sdk.dylib", "libnexus_taptap_sdk.dylib", "./libtaptap_api.dylib", "libtaptap_api.dylib"};
#else
        const char *cands[] = {"./libnexus_taptap_sdk.so", "libnexus_taptap_sdk.so", "./libtaptap_api.so", "libtaptap_api.so"};
#endif
        for (size_t i = 0; !tap_lib && i < 4; ++i) {
            tap_lib = dlopen(cands[i], RTLD_NOW | RTLD_LOCAL);
        }
    }
#endif
    if (!tap_lib) {
        fail("TapTap TapSDK runtime library not found; set XU_NEXUS_TAPTAP_LIBRARY or ship nexus_taptap_sdk");
        return false;
    }

    p_restart = (fn_t_restart)find_sym("nexus_taptap_v1_restart_if_necessary");
    p_init = (fn_t_init)find_sym("nexus_taptap_v1_init");
    p_shutdown = (fn_t_void)find_sym("nexus_taptap_v1_shutdown");
    p_poll = (fn_t_poll)find_sym("nexus_taptap_v1_poll_events");
    p_login = (fn_t_str)find_sym("nexus_taptap_v1_login");
    p_logout = (fn_t_int)find_sym("nexus_taptap_v1_logout");
    p_is_logged_in = (fn_t_int)find_sym("nexus_taptap_v1_is_logged_in");
    p_open_id = (fn_t_str_out)find_sym("nexus_taptap_v1_user_open_id");
    p_union_id = (fn_t_str_out)find_sym("nexus_taptap_v1_user_union_id");
    p_user_name = (fn_t_str_out)find_sym("nexus_taptap_v1_user_name");
    p_comp_startup = (fn_t_int)find_sym("nexus_taptap_v1_compliance_startup");
    p_comp_exit = (fn_t_int)find_sym("nexus_taptap_v1_compliance_exit");
    p_comp_age = (fn_t_int)find_sym("nexus_taptap_v1_compliance_age_range");
    p_comp_rem = (fn_t_int)find_sym("nexus_taptap_v1_compliance_remaining_time");
    p_comp_status = (fn_t_int)find_sym("nexus_taptap_v1_compliance_status");
    p_comp_chk_pay = (fn_t_i1)find_sym("nexus_taptap_v1_compliance_check_payment");
    p_comp_sub_pay = (fn_t_i1)find_sym("nexus_taptap_v1_compliance_submit_payment");
    p_verify_license = (fn_t_int)find_sym("nexus_taptap_v1_verify_license");
    p_has_dlc = (fn_t_str)find_sym("nexus_taptap_v1_has_dlc");
    p_query_dlc = (fn_t_str)find_sym("nexus_taptap_v1_query_dlc_page");
    p_unlock_ach = (fn_t_str)find_sym("nexus_taptap_v1_unlock_achievement");
    p_inc_ach = (fn_t_str_i2)find_sym("nexus_taptap_v1_increment_achievement");
    p_has_ach = (fn_t_str)find_sym("nexus_taptap_v1_has_achievement");
    p_cloud_write = (fn_t_cloud_write)find_sym("nexus_taptap_v1_cloud_write");
    p_cloud_read = (fn_t_cloud_read)find_sym("nexus_taptap_v1_cloud_read");
    p_cloud_exists = (fn_t_str)find_sym("nexus_taptap_v1_cloud_exists");
    p_cloud_delete = (fn_t_str)find_sym("nexus_taptap_v1_cloud_delete");
    p_lb_submit = (fn_t_str_i1)find_sym("nexus_taptap_v1_leaderboard_submit");
    p_open_moment = (fn_t_str)find_sym("nexus_taptap_v1_open_moment");
    p_moment_open = (fn_t_int)find_sym("nexus_taptap_v1_moment_is_open");
    p_check_update = (fn_t_int)find_sym("nexus_taptap_v1_check_update");

    if (!p_init || !p_shutdown) {
        unload_taptap();
        fail("TapTap driver missing mandatory nexus_taptap_v1_init/shutdown symbols");
        return false;
    }
    last_error[0] = '\0';
    return true;
}

static bool copy_cstr(const xu_u8_span *s, char *out, size_t cap) {
    if (!out || cap == 0) return false;
    if (!s || !s->data || s->len < 0) {
        fail("invalid string span");
        return false;
    }
    size_t n = (size_t)s->len;
    if (n >= cap) {
        fail("string argument exceeds buffer limit");
        return false;
    }
    if (n > 0) memcpy(out, s->data, n);
    out[n] = '\0';
    return true;
}

static bool require_init(void) {
    if (!initialized || !tap_lib) {
        fail("TapTap client not initialized");
        return false;
    }
    return true;
}

static xu_int read_str_via(fn_t_str_out fn, const xu_u8_span_mut *out, const char *fallback) {
    if (!require_init()) return -1;
    if (!out || !out->data || out->len <= 0) return fail("invalid output span");
    char buf[512];
    buf[0] = '\0';
    int raw_len = fn ? fn(buf, (int)sizeof(buf)) : snprintf(buf, sizeof(buf), "%s", fallback);
    if (raw_len < 0) return fail("taptap driver string query failed");
    size_t slen = strnlen(buf, sizeof(buf));
    size_t n = slen < (size_t)out->len ? slen : (size_t)out->len;
    if (n > 0) memcpy(out->data, buf, n);
    return (xu_int)n;
}

xu_int API(error_len)(void) {
    return (xu_int)strnlen(last_error, sizeof(last_error));
}

xu_int API(error_byte)(xu_int index) {
    size_t len = strnlen(last_error, sizeof(last_error));
    if (index < 0 || (size_t)index >= len) return 0;
    return (xu_int)(unsigned char)last_error[index];
}

xu_int API(is_available)(void) {
    return load_taptap() ? 1 : 0;
}

xu_int API(restart_if_necessary)(const xu_u8_span *client_id) {
    if (!load_taptap()) return -1;
    char buf[128];
    if (!copy_cstr(client_id, buf, sizeof(buf))) return -1;
    return (p_restart && p_restart(buf) != 0) ? 1 : 0;
}

xu_int API(init)(const xu_u8_span *client_id, const xu_u8_span *client_token, xu_int region, xu_int target_platform) {
    if (!load_taptap()) return -1;
    char cid[128], ctok[256];
    if (!copy_cstr(client_id, cid, sizeof(cid)) || !copy_cstr(client_token, ctok, sizeof(ctok))) return -1;
    if (p_init(cid, ctok, (int)region, (int)target_platform) != 0) {
        return fail("nexus_taptap_v1_init returned failure");
    }
    initialized = true;
    return 0;
}

xu_int API(shutdown)(void) {
    if (initialized && p_shutdown) p_shutdown();
    initialized = false;
    return 0;
}

xu_int API(poll_events)(const xu_i64_span_mut *events_out) {
    if (!require_init()) return -1;
    if (!events_out || !events_out->data || events_out->len <= 0) return fail("invalid events span");
    if (!p_poll) return 0;
    int n = p_poll(events_out->data, (int)events_out->len);
    return n < 0 ? 0 : (xu_int)n;
}

xu_int API(login)(const xu_u8_span *scopes) {
    if (!require_init()) return -1;
    char buf[256];
    if (!copy_cstr(scopes, buf, sizeof(buf))) return -1;
    if (!p_login) return fail("driver missing login");
    return p_login(buf) == 0 ? 0 : fail("login failed");
}

xu_int API(logout)(void) {
    if (!require_init()) return -1;
    if (!p_logout) return 0;
    return p_logout() == 0 ? 0 : fail("logout failed");
}

xu_int API(is_logged_in)(void) {
    if (!require_init()) return -1;
    return p_is_logged_in && p_is_logged_in() != 0 ? 1 : 0;
}

xu_int API(user_open_id)(const xu_u8_span_mut *out) { return read_str_via(p_open_id, out, "tap_open_id"); }
xu_int API(user_union_id)(const xu_u8_span_mut *out) { return read_str_via(p_union_id, out, "tap_union_id"); }
xu_int API(user_name)(const xu_u8_span_mut *out) { return read_str_via(p_user_name, out, "TapUser"); }

xu_int API(compliance_startup)(void) {
    if (!require_init()) return -1;
    if (!p_comp_startup) return 0;
    return p_comp_startup() == 0 ? 0 : fail("compliance_startup failed");
}

xu_int API(compliance_exit)(void) {
    if (!require_init()) return -1;
    if (!p_comp_exit) return 0;
    return p_comp_exit() == 0 ? 0 : fail("compliance_exit failed");
}

xu_int API(compliance_age_range)(void) {
    if (!require_init()) return -1;
    return p_comp_age ? (xu_int)p_comp_age() : 18;
}

xu_int API(compliance_remaining_time)(void) {
    if (!require_init()) return -1;
    return p_comp_rem ? (xu_int)p_comp_rem() : -1;
}

xu_int API(compliance_status)(void) {
    if (!require_init()) return -1;
    return p_comp_status ? (xu_int)p_comp_status() : 0;
}

xu_int API(compliance_check_payment)(xu_int amount_cents) {
    if (!require_init()) return -1;
    if (amount_cents <= 0) return fail("payment amount must be positive");
    if (!p_comp_chk_pay) return 0;
    return p_comp_chk_pay((int)amount_cents) == 0 ? 0 : fail("payment rejected by compliance limit");
}

xu_int API(compliance_submit_payment)(xu_int amount_cents) {
    if (!require_init()) return -1;
    if (amount_cents <= 0) return fail("payment amount must be positive");
    if (!p_comp_sub_pay) return 0;
    return p_comp_sub_pay((int)amount_cents) == 0 ? 0 : fail("compliance submit payment failed");
}

xu_int API(verify_license)(void) {
    if (!require_init()) return -1;
    return (!p_verify_license || p_verify_license() != 0) ? 1 : 0;
}

xu_int API(has_dlc)(const xu_u8_span *sku) {
    if (!require_init()) return -1;
    char buf[128];
    if (!copy_cstr(sku, buf, sizeof(buf))) return -1;
    return p_has_dlc && p_has_dlc(buf) != 0 ? 1 : 0;
}

xu_int API(query_dlc_page)(const xu_u8_span *sku) {
    if (!require_init()) return -1;
    char buf[128];
    if (!copy_cstr(sku, buf, sizeof(buf))) return -1;
    if (!p_query_dlc) return 0;
    return p_query_dlc(buf) == 0 ? 0 : fail("query_dlc_page failed");
}

xu_int API(unlock_achievement)(const xu_u8_span *id) {
    if (!require_init()) return -1;
    char buf[128];
    if (!copy_cstr(id, buf, sizeof(buf))) return -1;
    if (!p_unlock_ach) return fail("driver missing unlock_achievement");
    return p_unlock_ach(buf) == 0 ? 0 : fail("unlock_achievement failed");
}

xu_int API(increment_achievement)(const xu_u8_span *id, xu_int steps, xu_int max_steps) {
    if (!require_init()) return -1;
    char buf[128];
    if (!copy_cstr(id, buf, sizeof(buf))) return -1;
    if (!p_inc_ach) return 0;
    return p_inc_ach(buf, (int)steps, (int)max_steps) == 0 ? 0 : fail("increment_achievement failed");
}

xu_int API(has_achievement)(const xu_u8_span *id) {
    if (!require_init()) return -1;
    char buf[128];
    if (!copy_cstr(id, buf, sizeof(buf))) return -1;
    return p_has_ach && p_has_ach(buf) != 0 ? 1 : 0;
}

xu_int API(cloud_write)(const xu_u8_span *name, const xu_u8_span *summary, const xu_u8_span *data) {
    if (!require_init()) return -1;
    char nbuf[192], sbuf[256];
    if (!copy_cstr(name, nbuf, sizeof(nbuf)) || !copy_cstr(summary, sbuf, sizeof(sbuf))) return -1;
    if (!data || data->len < 0 || data->len > 10 * 1024 * 1024) return fail("invalid cloudsave payload");
    if (!p_cloud_write) return fail("driver missing cloud_write");
    return p_cloud_write(nbuf, sbuf, data->data, (int)data->len) == 0 ? 0 : fail("cloud_write failed");
}

xu_int API(cloud_read)(const xu_u8_span *name, const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    char nbuf[192];
    if (!copy_cstr(name, nbuf, sizeof(nbuf))) return -1;
    if (!out || !out->data || out->len <= 0) return fail("invalid cloud read span");
    if (!p_cloud_read) return fail("driver missing cloud_read");
    int n = p_cloud_read(nbuf, out->data, (int)out->len);
    if (n < 0) return fail("cloud_read failed");
    return (xu_int)n;
}

xu_int API(cloud_exists)(const xu_u8_span *name) {
    if (!require_init()) return -1;
    char nbuf[192];
    if (!copy_cstr(name, nbuf, sizeof(nbuf))) return -1;
    return p_cloud_exists && p_cloud_exists(nbuf) != 0 ? 1 : 0;
}

xu_int API(cloud_delete)(const xu_u8_span *name) {
    if (!require_init()) return -1;
    char nbuf[192];
    if (!copy_cstr(name, nbuf, sizeof(nbuf))) return -1;
    if (!p_cloud_delete) return 0;
    return p_cloud_delete(nbuf) == 0 ? 0 : fail("cloud_delete failed");
}

xu_int API(leaderboard_submit)(const xu_u8_span *board_id, xu_int score) {
    if (!require_init()) return -1;
    char bbuf[128];
    if (!copy_cstr(board_id, bbuf, sizeof(bbuf))) return -1;
    if (!p_lb_submit) return 0;
    return p_lb_submit(bbuf, (int)score) == 0 ? 0 : fail("leaderboard_submit failed");
}

xu_int API(open_moment)(const xu_u8_span *page) {
    if (!require_init()) return -1;
    char pbuf[128];
    if (!copy_cstr(page, pbuf, sizeof(pbuf))) return -1;
    if (!p_open_moment) return 0;
    return p_open_moment(pbuf) == 0 ? 0 : fail("open_moment failed");
}

xu_int API(moment_is_open)(void) {
    if (!require_init()) return -1;
    return p_moment_open && p_moment_open() != 0 ? 1 : 0;
}

xu_int API(check_update)(void) {
    if (!require_init()) return -1;
    return p_check_update ? (xu_int)p_check_update() : 0;
}

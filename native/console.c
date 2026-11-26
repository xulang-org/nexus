// Runtime-loaded Console SDK adapter (Xbox GDK / PlayStation SDK / Nintendo Switch).
// Never vendors proprietary vendor headers or redistributables.
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
typedef HMODULE console_lib_t;
#else
#include <dlfcn.h>
typedef void *console_lib_t;
#endif

#define API(name) XU_NATIVE_SYMBOL(xu_nexus_console_native_##name)

typedef int (*fn_c_init)(int platform_id);
typedef void (*fn_c_void)(void);
typedef int (*fn_c_poll_events)(int64_t *events_out, int cap);
typedef int (*fn_c_int)(void);
typedef int (*fn_c_str_out)(char *out, int cap);
typedef int (*fn_c_ach_set)(const char *id, int numeric_id, int progress_pct);
typedef int (*fn_c_ach_get)(const char *id, int numeric_id);
typedef int (*fn_c_str2)(const char *a, const char *b);
typedef int (*fn_c_str)(const char *a);
typedef int (*fn_c_str_i)(const char *a, int v);
typedef int (*fn_c_save_write)(const char *container, const char *blob, const uint8_t *data, int len);
typedef int (*fn_c_save_read)(const char *container, const char *blob, uint8_t *out, int cap);
typedef int (*fn_c_haptics)(int pad, double low_f, double high_f, double lt, double rt, const int64_t *params, int param_len);
typedef int (*fn_c_i_str)(int kind, const char *arg);
typedef int (*fn_c_i2)(int a, int b);
typedef int (*fn_c_i1)(int a);

static console_lib_t driver_lib = NULL;
static int loaded_family = 0; // 1 = Xbox, 2 = PlayStation, 3 = Nintendo Switch
static bool initialized = false;
static int active_platform = 0;

static fn_c_init p_init = NULL;
static fn_c_void p_shutdown = NULL;
static fn_c_poll_events p_poll_events = NULL;
static fn_c_int p_lifecycle_state = NULL;
static fn_c_int p_confirm_button = NULL;
static fn_c_int p_safe_area = NULL;
static fn_c_str_out p_user_id = NULL;
static fn_c_str_out p_user_name = NULL;
static fn_c_int p_user_flags = NULL;
static fn_c_ach_set p_unlock_ach = NULL;
static fn_c_ach_get p_has_ach = NULL;
static fn_c_str2 p_set_presence = NULL;
static fn_c_str p_activity_start = NULL;
static fn_c_str_i p_activity_end = NULL;
static fn_c_save_write p_save_write = NULL;
static fn_c_save_read p_save_read = NULL;
static fn_c_str2 p_save_exists = NULL;
static fn_c_str2 p_save_delete = NULL;
static fn_c_str p_has_entitlement = NULL;
static fn_c_haptics p_set_haptics = NULL;
static fn_c_i_str p_show_ui = NULL;
static fn_c_i2 p_session_create = NULL;
static fn_c_i1 p_session_join = NULL;
static fn_c_int p_session_leave = NULL;
static fn_c_int p_operation_mode = NULL;
static fn_c_int p_npad_style = NULL;

static _Thread_local char last_error[1024];

static xu_int fail(const char *msg) {
    snprintf(last_error, sizeof(last_error), "%s", msg ? msg : "unknown console driver error");
    return -1;
}

static int platform_family(int platform_id) {
    if (platform_id >= 2 && platform_id <= 4) return 1; // Xbox GDK / Series X|S / Xbox PC
    if (platform_id >= 5 && platform_id <= 7) return 2; // PlayStation 5 / 5 Pro / 4
    if (platform_id == 8 || platform_id == 9) return 3; // Nintendo Switch / Switch 2
    return 0;
}

static void unload_driver(void) {
    if (driver_lib) {
#ifdef _WIN32
        FreeLibrary(driver_lib);
#else
        dlclose(driver_lib);
#endif
        driver_lib = NULL;
    }
    loaded_family = 0;
    initialized = false;
    active_platform = 0;
    p_init = NULL; p_shutdown = NULL; p_poll_events = NULL;
    p_lifecycle_state = NULL; p_confirm_button = NULL; p_safe_area = NULL;
    p_user_id = NULL; p_user_name = NULL; p_user_flags = NULL;
    p_unlock_ach = NULL; p_has_ach = NULL; p_set_presence = NULL;
    p_activity_start = NULL; p_activity_end = NULL;
    p_save_write = NULL; p_save_read = NULL; p_save_exists = NULL; p_save_delete = NULL;
    p_has_entitlement = NULL; p_set_haptics = NULL; p_show_ui = NULL;
    p_session_create = NULL; p_session_join = NULL; p_session_leave = NULL;
    p_operation_mode = NULL; p_npad_style = NULL;
}

static void *find_sym(const char *name) {
    if (!driver_lib || !name) return NULL;
#ifdef _WIN32
    return (void *)GetProcAddress(driver_lib, name);
#else
    return dlsym(driver_lib, name);
#endif
}

static bool load_driver(int platform_id) {
    int fam = platform_family(platform_id);
    if (!fam) {
        fail("unsupported console platform id");
        return false;
    }
    if (driver_lib && loaded_family == fam) return true;
    unload_driver();

    const char *env_key = fam == 1 ? "XU_NEXUS_XBOX_DRIVER"
        : (fam == 2 ? "XU_NEXUS_PS_DRIVER" : "XU_NEXUS_SWITCH_DRIVER");
    const char *override = getenv(env_key);
#ifdef _WIN32
    const char *cands_xb[] = {"nexus_xbox_gdk.dll"};
    const char *cands_ps[] = {"nexus_ps_sdk.dll"};
    const char *cands_sw[] = {"nexus_switch_sdk.dll"};
    const char **cands = fam == 1 ? cands_xb : (fam == 2 ? cands_ps : cands_sw);
    if (override && *override) {
        driver_lib = LoadLibraryA(override);
    } else {
        driver_lib = LoadLibraryA(cands[0]);
    }
#else
    if (override && *override) {
        driver_lib = dlopen(override, RTLD_NOW | RTLD_LOCAL);
    } else {
#ifdef __APPLE__
        const char *cands_xb[] = {"./libnexus_xbox_gdk.dylib", "libnexus_xbox_gdk.dylib"};
        const char *cands_ps[] = {"./libnexus_ps_sdk.dylib", "libnexus_ps_sdk.dylib"};
        const char *cands_sw[] = {"./libnexus_switch_sdk.dylib", "libnexus_switch_sdk.dylib"};
#else
        const char *cands_xb[] = {"./libnexus_xbox_gdk.so", "libnexus_xbox_gdk.so"};
        const char *cands_ps[] = {"./libnexus_ps_sdk.so", "libnexus_ps_sdk.so"};
        const char *cands_sw[] = {"./libnexus_switch_sdk.so", "libnexus_switch_sdk.so"};
#endif
        const char **cands = fam == 1 ? cands_xb : (fam == 2 ? cands_ps : cands_sw);
        for (size_t i = 0; !driver_lib && i < 2; ++i) {
            driver_lib = dlopen(cands[i], RTLD_NOW | RTLD_LOCAL);
        }
    }
#endif
    if (!driver_lib) {
        fail(fam == 1
            ? "Xbox GDK runtime driver not found; set XU_NEXUS_XBOX_DRIVER or ship nexus_xbox_gdk"
            : (fam == 2
                ? "PlayStation SDK runtime driver not found; set XU_NEXUS_PS_DRIVER or ship nexus_ps_sdk"
                : "Nintendo Switch runtime driver not found; set XU_NEXUS_SWITCH_DRIVER or ship nexus_switch_sdk"));
        return false;
    }

    p_init = (fn_c_init)find_sym("nexus_console_v1_init");
    p_shutdown = (fn_c_void)find_sym("nexus_console_v1_shutdown");
    p_poll_events = (fn_c_poll_events)find_sym("nexus_console_v1_poll_events");
    p_lifecycle_state = (fn_c_int)find_sym("nexus_console_v1_lifecycle_state");
    p_confirm_button = (fn_c_int)find_sym("nexus_console_v1_confirm_button");
    p_safe_area = (fn_c_int)find_sym("nexus_console_v1_safe_area_percent");
    p_user_id = (fn_c_str_out)find_sym("nexus_console_v1_user_id");
    p_user_name = (fn_c_str_out)find_sym("nexus_console_v1_user_name");
    p_user_flags = (fn_c_int)find_sym("nexus_console_v1_user_flags");
    p_unlock_ach = (fn_c_ach_set)find_sym("nexus_console_v1_unlock_achievement");
    p_has_ach = (fn_c_ach_get)find_sym("nexus_console_v1_has_achievement");
    p_set_presence = (fn_c_str2)find_sym("nexus_console_v1_set_presence");
    p_activity_start = (fn_c_str)find_sym("nexus_console_v1_activity_start");
    p_activity_end = (fn_c_str_i)find_sym("nexus_console_v1_activity_end");
    p_save_write = (fn_c_save_write)find_sym("nexus_console_v1_save_write");
    p_save_read = (fn_c_save_read)find_sym("nexus_console_v1_save_read");
    p_save_exists = (fn_c_str2)find_sym("nexus_console_v1_save_exists");
    p_save_delete = (fn_c_str2)find_sym("nexus_console_v1_save_delete");
    p_has_entitlement = (fn_c_str)find_sym("nexus_console_v1_has_entitlement");
    p_set_haptics = (fn_c_haptics)find_sym("nexus_console_v1_set_haptics");
    p_show_ui = (fn_c_i_str)find_sym("nexus_console_v1_show_system_ui");
    p_session_create = (fn_c_i2)find_sym("nexus_console_v1_session_create");
    p_session_join = (fn_c_i1)find_sym("nexus_console_v1_session_join");
    p_session_leave = (fn_c_int)find_sym("nexus_console_v1_session_leave");
    p_operation_mode = (fn_c_int)find_sym("nexus_console_v1_operation_mode");
    p_npad_style = (fn_c_int)find_sym("nexus_console_v1_npad_style");

    if (!p_init || !p_shutdown) {
        unload_driver();
        fail("console driver missing nexus_console_v1_init/shutdown");
        return false;
    }
    loaded_family = fam;
    last_error[0] = '\0';
    return true;
}

static bool copy_cstr(const xu_u8_span *span, char *out, size_t cap) {
    if (!span || !out || cap == 0 || span->len < 0 || (size_t)span->len >= cap) {
        fail("invalid console string span");
        return false;
    }
    if (span->len > 0 && !span->data) { fail("null console string span"); return false; }
    for (xu_int i = 0; i < span->len; ++i) {
        if (span->data[i] == 0) { fail("embedded NUL in console string"); return false; }
        out[i] = (char)span->data[i];
    }
    out[span->len] = '\0';
    return true;
}

static bool require_init(void) {
    if (!driver_lib || !initialized) {
        fail("console service not initialized");
        return false;
    }
    return true;
}

xu_int API(error_len)(void) { return (xu_int)strlen(last_error); }
xu_int API(error_byte)(xu_int index) {
    return index >= 0 && (uint64_t)index < strlen(last_error) ? (unsigned char)last_error[index] : 0;
}

xu_int API(is_available)(xu_int platform_id) {
    return load_driver((int)platform_id) ? 1 : 0;
}

xu_int API(init)(xu_int platform_id) {
    if (!load_driver((int)platform_id)) return -1;
    if (p_init((int)platform_id) != 0) return fail("console driver init failed");
    initialized = true;
    active_platform = (int)platform_id;
    last_error[0] = '\0';
    return 0;
}

xu_int API(shutdown)(void) {
    if (initialized && p_shutdown) p_shutdown();
    unload_driver();
    return 0;
}

xu_int API(poll_events)(const xu_i64_span_mut *out) {
    if (!require_init()) return -1;
    if (!p_poll_events || !out || !out->data || out->len <= 0) return 0;
    return (xu_int)p_poll_events(out->data, (int)out->len);
}

xu_int API(lifecycle_state)(void) {
    if (!require_init()) return -1;
    return p_lifecycle_state ? (xu_int)p_lifecycle_state() : 0;
}

xu_int API(confirm_button)(void) {
    if (!require_init()) return -1;
    return p_confirm_button ? (xu_int)p_confirm_button() : 0;
}

xu_int API(safe_area_percent)(void) {
    if (!require_init()) return -1;
    if (p_safe_area) return (xu_int)p_safe_area();
    return active_platform == 4 ? 100 : 90;
}

static xu_int read_driver_str(fn_c_str_out fn, const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    if (!out || !out->data || out->len <= 0) return fail("invalid output span");
    if (!fn) return 0;
    char buf[512] = {0};
    int n = fn(buf, sizeof(buf));
    if (n <= 0) return 0;
    if ((xu_int)n > out->len) n = (int)out->len;
    memcpy(out->data, buf, (size_t)n);
    return (xu_int)n;
}

xu_int API(user_id)(const xu_u8_span_mut *out) { return read_driver_str(p_user_id, out); }
xu_int API(user_name)(const xu_u8_span_mut *out) { return read_driver_str(p_user_name, out); }

xu_int API(user_flags)(void) {
    if (!require_init()) return -1;
    return p_user_flags ? (xu_int)p_user_flags() : 0;
}

xu_int API(unlock_achievement)(const xu_u8_span *id, xu_int numeric_id, xu_int pct) {
    if (!require_init()) return -1;
    char buf[256];
    if (!copy_cstr(id, buf, sizeof(buf))) return -1;
    if (!p_unlock_ach) return fail("driver missing unlock_achievement");
    return p_unlock_ach(buf, (int)numeric_id, (int)pct) == 0 ? 0 : fail("unlock_achievement failed");
}

xu_int API(has_achievement)(const xu_u8_span *id, xu_int numeric_id) {
    if (!require_init()) return -1;
    char buf[256];
    if (!copy_cstr(id, buf, sizeof(buf))) return -1;
    if (!p_has_ach) return 0;
    return p_has_ach(buf, (int)numeric_id) ? 1 : 0;
}

xu_int API(set_presence)(const xu_u8_span *status, const xu_u8_span *activity_id) {
    if (!require_init()) return -1;
    char sbuf[256], abuf[256];
    if (!copy_cstr(status, sbuf, sizeof(sbuf)) || !copy_cstr(activity_id, abuf, sizeof(abuf))) return -1;
    if (!p_set_presence) return 0;
    return p_set_presence(sbuf, abuf) == 0 ? 0 : fail("set_presence failed");
}

xu_int API(activity_start)(const xu_u8_span *activity_id) {
    if (!require_init()) return -1;
    char abuf[256];
    if (!copy_cstr(activity_id, abuf, sizeof(abuf))) return -1;
    if (!p_activity_start) return 0;
    return p_activity_start(abuf) == 0 ? 0 : fail("activity_start failed");
}

xu_int API(activity_end)(const xu_u8_span *activity_id, xu_int outcome) {
    if (!require_init()) return -1;
    char abuf[256];
    if (!copy_cstr(activity_id, abuf, sizeof(abuf))) return -1;
    if (!p_activity_end) return 0;
    return p_activity_end(abuf, (int)outcome) == 0 ? 0 : fail("activity_end failed");
}

xu_int API(save_write)(const xu_u8_span *container, const xu_u8_span *blob, const xu_u8_span *data) {
    if (!require_init()) return -1;
    char cbuf[128], bbuf[128];
    if (!copy_cstr(container, cbuf, sizeof(cbuf)) || !copy_cstr(blob, bbuf, sizeof(bbuf))) return -1;
    if (!data || data->len < 0 || data->len > 16 * 1024 * 1024) return fail("invalid save payload");
    if (!p_save_write) return fail("driver missing save_write");
    return p_save_write(cbuf, bbuf, data->data, (int)data->len) == 0 ? 0 : fail("save_write failed");
}

xu_int API(save_read)(const xu_u8_span *container, const xu_u8_span *blob, const xu_u8_span_mut *out) {
    if (!require_init()) return -1;
    char cbuf[128], bbuf[128];
    if (!copy_cstr(container, cbuf, sizeof(cbuf)) || !copy_cstr(blob, bbuf, sizeof(bbuf))) return -1;
    if (!out || !out->data || out->len <= 0) return fail("invalid save read span");
    if (!p_save_read) return fail("driver missing save_read");
    int n = p_save_read(cbuf, bbuf, out->data, (int)out->len);
    if (n < 0) return fail("save_read failed");
    return (xu_int)n;
}

xu_int API(save_exists)(const xu_u8_span *container, const xu_u8_span *blob) {
    if (!require_init()) return -1;
    char cbuf[128], bbuf[128];
    if (!copy_cstr(container, cbuf, sizeof(cbuf)) || !copy_cstr(blob, bbuf, sizeof(bbuf))) return -1;
    return p_save_exists && p_save_exists(cbuf, bbuf) ? 1 : 0;
}

xu_int API(save_delete)(const xu_u8_span *container, const xu_u8_span *blob) {
    if (!require_init()) return -1;
    char cbuf[128], bbuf[128];
    if (!copy_cstr(container, cbuf, sizeof(cbuf)) || !copy_cstr(blob, bbuf, sizeof(bbuf))) return -1;
    if (!p_save_delete) return 0;
    return p_save_delete(cbuf, bbuf) == 0 ? 0 : fail("save_delete failed");
}

xu_int API(has_entitlement)(const xu_u8_span *id) {
    if (!require_init()) return -1;
    char buf[256];
    if (!copy_cstr(id, buf, sizeof(buf))) return -1;
    return p_has_entitlement && p_has_entitlement(buf) ? 1 : 0;
}

xu_int API(set_haptics)(xu_int pad_idx, double low_f, double high_f, double lt, double rt, const xu_i64_span *params) {
    if (!require_init()) return -1;
    if (!params || !params->data || params->len < 11) return fail("haptics requires 11-int parameter span");
    if (!p_set_haptics) return 0;
    return p_set_haptics((int)pad_idx, low_f, high_f, lt, rt, params->data, (int)params->len) == 0
        ? 0 : fail("set_haptics failed");
}

xu_int API(show_system_ui)(xu_int ui_kind, const xu_u8_span *arg) {
    if (!require_init()) return -1;
    char buf[256];
    if (!copy_cstr(arg, buf, sizeof(buf))) return -1;
    if (!p_show_ui) return 0;
    return p_show_ui((int)ui_kind, buf) == 0 ? 0 : fail("show_system_ui failed");
}

xu_int API(session_create)(xu_int max_players, xu_int crossplay) {
    if (!require_init()) return -1;
    if (!p_session_create) return fail("driver missing session_create");
    xu_int sid = (xu_int)p_session_create((int)max_players, (int)crossplay);
    return sid > 0 ? sid : fail("session_create rejected");
}

xu_int API(session_join)(xu_int session_id) {
    if (!require_init()) return -1;
    if (!p_session_join) return fail("driver missing session_join");
    return p_session_join((int)session_id) == 0 ? 0 : fail("session_join failed");
}

xu_int API(session_leave)(void) {
    if (!require_init()) return -1;
    if (!p_session_leave) return 0;
    return p_session_leave() == 0 ? 0 : fail("session_leave failed");
}

xu_int API(operation_mode)(void) {
    if (!require_init()) return -1;
    return p_operation_mode ? (xu_int)p_operation_mode() : (loaded_family == 3 ? 0 : 1);
}

xu_int API(npad_style)(void) {
    if (!require_init()) return -1;
    return p_npad_style ? (xu_int)p_npad_style() : 1;
}

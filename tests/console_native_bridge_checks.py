#!/usr/bin/env python3
"""Verify Nexus Console native bridge against separate compiled Xbox GDK, PlayStation 5, and Nintendo Switch fake C drivers."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

COMMON_DRIVER_HEAD = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int g_ach_done = 0;
static char g_cont[128] = {0};
static char g_blob[128] = {0};
static uint8_t g_save[65536];
static int g_save_len = 0;
static int g_haptics_ok = 0;
static int g_activity_started = 0;

int nexus_console_v1_poll_events(int64_t *events_out, int cap) {
    if (events_out && cap >= 1) { events_out[0] = 3; return 1; }
    return 0;
}
int nexus_console_v1_lifecycle_state(void) { return 0; }
int nexus_console_v1_safe_area_percent(void) { return 90; }
int nexus_console_v1_user_flags(void) { return 1 | 4 | 8; }
int nexus_console_v1_unlock_achievement(const char *id, int numeric_id, int pct) {
    (void)id; (void)numeric_id; if (pct >= 100) g_ach_done = 1; return 0;
}
int nexus_console_v1_has_achievement(const char *id, int numeric_id) {
    (void)id; (void)numeric_id; return g_ach_done;
}
int nexus_console_v1_set_presence(const char *status, const char *act) {
    (void)status; (void)act; return 0;
}
int nexus_console_v1_activity_start(const char *act) {
    g_activity_started = (act && *act) ? 1 : 0; return g_activity_started ? 0 : -1;
}
int nexus_console_v1_activity_end(const char *act, int outcome) {
    (void)outcome; return (g_activity_started && act && *act) ? 0 : -1;
}
int nexus_console_v1_save_write(const char *c, const char *b, const uint8_t *data, int len) {
    if (!c || !b || len < 0 || len > (int)sizeof(g_save)) return -1;
    snprintf(g_cont, sizeof(g_cont), "%s", c);
    snprintf(g_blob, sizeof(g_blob), "%s", b);
    if (len > 0 && data) memcpy(g_save, data, (size_t)len);
    g_save_len = len;
    return 0;
}
int nexus_console_v1_save_read(const char *c, const char *b, uint8_t *out, int cap) {
    if (!c || !b || strcmp(g_cont, c) != 0 || strcmp(g_blob, b) != 0) return -1;
    int n = g_save_len < cap ? g_save_len : cap;
    if (n > 0 && out) memcpy(out, g_save, (size_t)n);
    return n;
}
int nexus_console_v1_save_exists(const char *c, const char *b) {
    return (c && b && strcmp(g_cont, c) == 0 && strcmp(g_blob, b) == 0) ? 1 : 0;
}
int nexus_console_v1_save_delete(const char *c, const char *b) {
    if (c && b && strcmp(g_cont, c) == 0 && strcmp(g_blob, b) == 0) { g_cont[0] = 0; g_blob[0] = 0; g_save_len = 0; return 0; }
    return -1;
}
int nexus_console_v1_set_haptics(int pad, double lf, double hf, double lt, double rt, const int64_t *params, int n) {
    (void)pad; (void)lf; (void)hf; (void)lt; (void)rt;
    if (!params || n < 11) return -1;
    g_haptics_ok = 1;
    return 0;
}
int nexus_console_v1_show_system_ui(int kind, const char *arg) { (void)kind; (void)arg; return 0; }
int nexus_console_v1_session_create(int maxp, int xp) { (void)maxp; (void)xp; return 8801; }
int nexus_console_v1_session_join(int sid) { (void)sid; return 0; }
int nexus_console_v1_session_leave(void) { return 0; }
'''

XBOX_DRIVER_TAIL = r'''
int nexus_console_v1_init(int platform_id) { return (platform_id >= 2 && platform_id <= 4) ? 0 : -1; }
void nexus_console_v1_shutdown(void) {}
int nexus_console_v1_confirm_button(void) { return 0; }
int nexus_console_v1_user_id(char *out, int cap) { return snprintf(out, (size_t)cap, "xuid:999"); }
int nexus_console_v1_user_name(char *out, int cap) { return snprintf(out, (size_t)cap, "XboxFakeTag"); }
int nexus_console_v1_has_entitlement(const char *id) { return (id && strcmp(id, "9NX0DLC00001") == 0) ? 1 : 0; }
'''

PS_DRIVER_TAIL = r'''
int nexus_console_v1_init(int platform_id) { return (platform_id >= 5 && platform_id <= 7) ? 0 : -1; }
void nexus_console_v1_shutdown(void) {}
int nexus_console_v1_confirm_button(void) { return 1; }
int nexus_console_v1_user_id(char *out, int cap) { return snprintf(out, (size_t)cap, "psn:888"); }
int nexus_console_v1_user_name(char *out, int cap) { return snprintf(out, (size_t)cap, "PSNFakeOnlineId"); }
int nexus_console_v1_has_entitlement(const char *id) { return (id && strcmp(id, "SEASONPASS000001") == 0) ? 1 : 0; }
'''

SWITCH_DRIVER_TAIL = r'''
int nexus_console_v1_init(int platform_id) { return (platform_id == 8 || platform_id == 9) ? 0 : -1; }
void nexus_console_v1_shutdown(void) {}
int nexus_console_v1_confirm_button(void) { return 2; }
int nexus_console_v1_operation_mode(void) { return 1; }
int nexus_console_v1_npad_style(void) { return 5; }
int nexus_console_v1_user_id(char *out, int cap) { return snprintf(out, (size_t)cap, "nsa:777"); }
int nexus_console_v1_user_name(char *out, int cap) { return snprintf(out, (size_t)cap, "SwitchFakeUser"); }
int nexus_console_v1_has_entitlement(const char *id) { return (id && strcmp(id, "AOC:3") == 0) ? 1 : 0; }
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    args = parser.parse_args()

    binary = ROOT / 'build/console-native-checks'
    subprocess.run([args.xu, 'build', str(ROOT / 'tests/console_native_checks.xu'), '-o', str(binary)],
                   cwd=ROOT, check=True)

    # 1. Missing driver fallback check
    env_missing = os.environ.copy()
    env_missing['XU_NEXUS_XBOX_DRIVER'] = '/nonexistent/xbox.dylib'
    env_missing['XU_NEXUS_PS_DRIVER'] = '/nonexistent/ps.dylib'
    env_missing['XU_NEXUS_SWITCH_DRIVER'] = '/nonexistent/switch.dylib'
    env_missing['NEXUS_CONSOLE_TEST_MODE'] = 'missing'
    subprocess.run([str(binary)], cwd=ROOT, env=env_missing, check=True)

    # 2, 3, 4. Compile Xbox GDK, PlayStation 5 & Nintendo Switch C11 drivers and verify dlopen C ABI
    with tempfile.TemporaryDirectory(prefix='nexus-fake-consoles-') as tmp:
        tmpdir = Path(tmp)
        ext = '.dylib' if platform.system() == 'Darwin' else '.so'
        cc = os.environ.get('CC', 'clang' if platform.system() == 'Darwin' else 'cc')

        xb_src = tmpdir / 'fake_xbox.c'
        xb_lib = tmpdir / ('libfake_xbox' + ext)
        xb_src.write_text(COMMON_DRIVER_HEAD + XBOX_DRIVER_TAIL, encoding='utf-8')
        subprocess.run([cc, '-shared', '-fPIC', '-O2', '-std=c11', str(xb_src), '-o', str(xb_lib)], check=True)

        ps_src = tmpdir / 'fake_ps.c'
        ps_lib = tmpdir / ('libfake_ps' + ext)
        ps_src.write_text(COMMON_DRIVER_HEAD + PS_DRIVER_TAIL, encoding='utf-8')
        subprocess.run([cc, '-shared', '-fPIC', '-O2', '-std=c11', str(ps_src), '-o', str(ps_lib)], check=True)

        sw_src = tmpdir / 'fake_switch.c'
        sw_lib = tmpdir / ('libfake_switch' + ext)
        sw_src.write_text(COMMON_DRIVER_HEAD + SWITCH_DRIVER_TAIL, encoding='utf-8')
        subprocess.run([cc, '-shared', '-fPIC', '-O2', '-std=c11', str(sw_src), '-o', str(sw_lib)], check=True)

        env_xb = os.environ.copy()
        env_xb['XU_NEXUS_XBOX_DRIVER'] = str(xb_lib)
        env_xb['NEXUS_CONSOLE_TEST_MODE'] = 'xbox'
        subprocess.run([str(binary)], cwd=ROOT, env=env_xb, check=True)

        env_ps = os.environ.copy()
        env_ps['XU_NEXUS_PS_DRIVER'] = str(ps_lib)
        env_ps['NEXUS_CONSOLE_TEST_MODE'] = 'ps'
        subprocess.run([str(binary)], cwd=ROOT, env=env_ps, check=True)

        env_sw = os.environ.copy()
        env_sw['XU_NEXUS_SWITCH_DRIVER'] = str(sw_lib)
        env_sw['NEXUS_CONSOLE_TEST_MODE'] = 'switch'
        subprocess.run([str(binary)], cwd=ROOT, env=env_sw, check=True)

    print('PASS: console_native_bridge_checks (fallback + Xbox GDK + PlayStation + Switch dlopen C ABI)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

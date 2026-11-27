#!/usr/bin/env python3
"""Verify Nexus TapTap native bridge against a real compiled C11 fake TapSDK v4 shared library."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

FAKE_TAPTAP_C = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int g_init = 0;
static int g_logged_in = 1;
static int g_ach_done = 0;
static int g_moment_open = 0;
static int g_spent = 0;
static char g_cloud_name[128] = {0};
static uint8_t g_cloud_data[65536];
static int g_cloud_len = 0;

int nexus_taptap_v1_restart_if_necessary(const char *client_id) { (void)client_id; return 0; }
int nexus_taptap_v1_init(const char *cid, const char *ctok, int region, int target) {
    (void)region; (void)target;
    if (!cid || !*cid || !ctok || !*ctok) return -1;
    g_init = 1;
    return 0;
}
void nexus_taptap_v1_shutdown(void) { g_init = 0; g_moment_open = 0; }
int nexus_taptap_v1_poll_events(int64_t *events_out, int cap) {
    if (g_init && events_out && cap >= 1) { events_out[0] = 11; return 1; }
    return 0;
}
int nexus_taptap_v1_login(const char *scopes) { (void)scopes; g_logged_in = 1; return 0; }
int nexus_taptap_v1_logout(void) { g_logged_in = 0; return 0; }
int nexus_taptap_v1_is_logged_in(void) { return g_logged_in; }
int nexus_taptap_v1_user_open_id(char *out, int cap) { return snprintf(out, (size_t)cap, "tap_open_777"); }
int nexus_taptap_v1_user_union_id(char *out, int cap) { return snprintf(out, (size_t)cap, "tap_union_999"); }
int nexus_taptap_v1_user_name(char *out, int cap) { return snprintf(out, (size_t)cap, "TapNativeUser"); }

int nexus_taptap_v1_compliance_startup(void) { return 0; }
int nexus_taptap_v1_compliance_exit(void) { return 0; }
int nexus_taptap_v1_compliance_age_range(void) { return 16; }
int nexus_taptap_v1_compliance_remaining_time(void) { return 3600; }
int nexus_taptap_v1_compliance_status(void) { return 0; }
int nexus_taptap_v1_compliance_check_payment(int cents) { return (cents > 0 && cents <= 10000) ? 0 : -1; }
int nexus_taptap_v1_compliance_submit_payment(int cents) {
    if (cents <= 0 || cents > 10000) return -1;
    g_spent += cents;
    return 0;
}

int nexus_taptap_v1_verify_license(void) { return 1; }
int nexus_taptap_v1_has_dlc(const char *sku) { return (sku && strcmp(sku, "tap_dlc_1") == 0) ? 1 : 0; }
int nexus_taptap_v1_query_dlc_page(const char *sku) { return sku ? 0 : -1; }

int nexus_taptap_v1_unlock_achievement(const char *id) {
    if (id && strcmp(id, "ACH_TAP_1") == 0) { g_ach_done = 1; return 0; }
    return -1;
}
int nexus_taptap_v1_increment_achievement(const char *id, int steps, int max_steps) {
    (void)id; return (steps > 0 && max_steps > 0) ? 0 : -1;
}
int nexus_taptap_v1_has_achievement(const char *id) {
    return (id && strcmp(id, "ACH_TAP_1") == 0 && g_ach_done) ? 1 : 0;
}

int nexus_taptap_v1_cloud_write(const char *name, const char *summary, const uint8_t *data, int len) {
    (void)summary;
    if (!name || len < 0 || len > (int)sizeof(g_cloud_data)) return -1;
    snprintf(g_cloud_name, sizeof(g_cloud_name), "%s", name);
    if (len > 0 && data) memcpy(g_cloud_data, data, (size_t)len);
    g_cloud_len = len;
    return 0;
}
int nexus_taptap_v1_cloud_read(const char *name, uint8_t *out, int cap) {
    if (!name || strcmp(g_cloud_name, name) != 0) return -1;
    int n = g_cloud_len < cap ? g_cloud_len : cap;
    if (n > 0 && out) memcpy(out, g_cloud_data, (size_t)n);
    return n;
}
int nexus_taptap_v1_cloud_exists(const char *name) {
    return (name && strcmp(g_cloud_name, name) == 0) ? 1 : 0;
}
int nexus_taptap_v1_cloud_delete(const char *name) {
    if (name && strcmp(g_cloud_name, name) == 0) { g_cloud_name[0] = 0; g_cloud_len = 0; return 0; }
    return -1;
}

int nexus_taptap_v1_leaderboard_submit(const char *board_id, int score) {
    return (board_id && score >= 0) ? 0 : -1;
}
int nexus_taptap_v1_open_moment(const char *page) {
    (void)page; g_moment_open = 1; return 0;
}
int nexus_taptap_v1_moment_is_open(void) { return g_moment_open; }
int nexus_taptap_v1_check_update(void) { return 0; }
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    args = parser.parse_args()

    binary = ROOT / 'build/taptap-native-checks'
    subprocess.run([args.xu, 'build', str(ROOT / 'tests/taptap_native_checks.xu'), '-o', str(binary)],
                   cwd=ROOT, check=True)

    # 1. Verify missing TapTap library falls back cleanly
    env_missing = os.environ.copy()
    env_missing['XU_NEXUS_TAPTAP_LIBRARY'] = '/nonexistent/no-taptap'
    env_missing['NEXUS_EXPECT_NATIVE_TAPTAP'] = '0'
    subprocess.run([str(binary)], cwd=ROOT, env=env_missing, check=True)

    # 2. Compile fake TapSDK C11 library and verify live dlopen C ABI
    with tempfile.TemporaryDirectory(prefix='nexus-fake-taptap-') as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / 'fake_taptap.c'
        src.write_text(FAKE_TAPTAP_C, encoding='utf-8')
        ext = '.dylib' if platform.system() == 'Darwin' else '.so'
        lib = tmpdir / ('libfake_taptap' + ext)
        cc = os.environ.get('CC', 'clang' if platform.system() == 'Darwin' else 'cc')
        subprocess.run([cc, '-shared', '-fPIC', '-O2', '-std=c11', str(src), '-o', str(lib)], check=True)

        env_live = os.environ.copy()
        env_live['XU_NEXUS_TAPTAP_LIBRARY'] = str(lib)
        env_live['NEXUS_EXPECT_NATIVE_TAPTAP'] = '1'
        subprocess.run([str(binary)], cwd=ROOT, env=env_live, check=True)

    print('PASS: taptap_native_bridge_checks (fallback + live dlopen C ABI)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

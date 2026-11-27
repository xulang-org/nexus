#!/usr/bin/env python3
"""Cross-platform Nexus Engine CI runner (contracts, native bridges, shaders, checks, headless tests, and tools)."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

CHECK_TARGETS = (
    ("examples/model_formats/main.xu", False, None),
    ("examples/lod/main.xu", False, None),
    ("examples/lighting/main.xu", False, None),
    ("examples/window_input/main.xu", False, None),
    ("examples/gpu_surface/main.xu", False, None),
    ("examples/gpu_offscreen/main.xu", False, None),
    ("examples/gpu_compute/main.xu", False, None),
    ("examples/arena/main.xu", False, None),
    ("examples/phone_arena", False, None),
    ("examples/phone_3d", False, None),
    ("examples/miniprogram", False, None),
    ("examples/webgl_3d/main.xu", False, None),
    ("examples/headless/main.xu", False, None),
    ("examples/two_d/main.xu", False, None),
    ("examples/three_d/main.xu", False, None),
    ("examples/isometric_2d", False, None),
    ("examples/hd2d_scene", False, None),
    ("examples/physics_3d/main.xu", False, None),
    ("examples/character_course/main.xu", False, None),
    ("examples/glb_preview/main.xu", False, None),
    ("examples/modern_sandbox/main.xu", False, None),
    ("cmd/scriptc/main.xu", False, None),
    ("cmd/project_validate/main.xu", False, None),
    ("cmd/project_viewport", False, None),
    ("cmd/nexus_studio", False, None),
    ("cmd/project", False, None),
    ("cmd/project_editor", True, None),
    ("cmd/tilemap_editor", False, None),
    ("tests/project_import_checks.xu", False, None),
    ("tests/project_editor_checks.xu", False, None),
    ("tests/scene_v10_modeling_checks.xu", False, None),
    ("tests/modeling_cpu_checks.xu", False, None),
    ("tests/glb_obj_roundtrip_checks.xu", False, None),
    ("tests/modeling_gpu_checks.xu", False, None),
    ("tests/studio_ui_checks.xu", False, None),
    ("tests/developer_systems_r2_checks.xu", False, None),
    ("tests/developer_systems_r3_checks.xu", False, None),
    ("tests/developer_systems_r4_checks.xu", False, None),
)

HEADLESS_TESTS = (
    ("tests/core_checks.xu", "core-tests", (), {}),
    ("tests/xacp_checks.xu", "xacp-tests", (), {}),
    ("tests/scene_soa_transform_checks.xu", "scene-soa-tests", (), {}),
    ("tests/scene_v9_modern_checks.xu", "scene-v9-tests", (), {}),
    ("tests/scene_v10_modeling_checks.xu", "scene-v10-modeling-checks", (), {"SDL_VIDEODRIVER": "nonexistent", "XU_NEXUS_SDL_LIBRARY": "/nonexistent/scene-v10-no-sdl"}),
    ("tests/scene_prefab_runtime_checks.xu", "prefab-runtime-checks", (), {}),
    ("tests/ecs_archetype_parallel_checks.xu", "ecs-parallel-checks", (), {}),
    ("tests/physics3d_checks.xu", "physics3d-checks", (), {}),
    ("tests/character3d_checks.xu", "character3d-checks", (), {}),
    ("tests/capsule3d_checks.xu", "capsule3d-checks", (), {}),
    ("tests/physics2d_platformer_checks.xu", "physics2d-platformer-checks", (), {}),
    ("tests/navigation_checks.xu", "navigation-checks", (), {}),
    ("tests/ai_bt_nav_checks.xu", "ai-bt-nav-checks", (), {}),
    ("tests/animation_timeline_checks.xu", "animation-timeline-checks", (), {}),
    ("tests/input_replay_timing_checks.xu", "input-replay-timing-checks", (), {}),
    ("tests/audio_mixer_checks.xu", "audio-mixer-checks", (), {}),
    ("tests/audio_dsp_adpcm_checks.xu", "audio-dsp-checks", (), {}),
    ("tests/audio_async_music_checks.xu", "audio-async-music-checks", (), {}),
    ("tests/spatial_audio_checks.xu", "spatial-audio-checks", (), {}),
    ("tests/networking_multiplayer_checks.xu", "networking-multiplayer-checks", (), {}),
    ("tests/bundle_hotreload_checks.xu", "bundle-checks", (), {}),
    ("tests/persistent_entities_checks.xu", "persistent-entities-checks", (), {}),
    ("tests/modeling_cpu_checks.xu", "modeling-cpu-checks", (), {"SDL_VIDEODRIVER": "nonexistent", "XU_NEXUS_SDL_LIBRARY": "/nonexistent/modeling-no-sdl"}),
    ("tests/gameplay_components_checks.xu", "gameplay-components-checks", (), {}),
    ("tests/gameplay_integration_checks.xu", "gameplay-integration-checks", (), {}),
    ("tests/i18n_checks.xu", "i18n-checks", (), {}),
    ("tests/steam_data_checks.xu", "steam-data-checks", (), {}),
    ("tests/console_data_checks.xu", "console-data-checks", (), {}),
    ("tests/taptap_data_checks.xu", "taptap-data-checks", (), {}),
    ("tests/developer_systems_r2_checks.xu", "developer-systems-r2-checks", (), {}),
    ("tests/developer_systems_r3_checks.xu", "developer-systems-r3-checks", (), {}),
    ("tests/developer_systems_r4_checks.xu", "developer-systems-r4-checks", (), {}),
)

RELEASE_TOOLS = (
    ("cmd/project", "nexus-project", (), False),
    ("cmd/project_validate/main.xu", "nexus-project-validate", (), False),
    ("cmd/project_viewport", "nexus-project-viewport", (), False),
    ("cmd/nexus_studio", "nexus-studio", (), False),
    ("cmd/scriptc/main.xu", "xu-nexus-script", (), False),
    ("cmd/project_editor", "nexus-project-editor", ("--desktop", "--no-webview"), True),
    ("cmd/tilemap_editor", "nexus-tilemap-editor", ("--desktop",), False),
)


def exe_name(stem: str) -> str:
    return f"{stem}.exe" if platform.system() == "Windows" else stem


def setup_env(xu_path: str | None) -> tuple[str, dict[str, str]]:
    env = os.environ.copy()
    xu_bin = xu_path or env.get("XU") or shutil.which("xu") or "xu"
    resolved = shutil.which(xu_bin) or xu_bin
    p = Path(resolved)
    if p.is_file():
        sdk_root = p.resolve().parent.parent
        if (sdk_root / "src").is_dir():
            env["NEXUS_XU_SDK"] = str(sdk_root)
            env["XU_ROOT"] = str(sdk_root)
            env["XU_STDLIB_ROOT"] = str(sdk_root / "src")
            xupath_parts = [str(sdk_root / "src")]
            if (sdk_root / "packages").is_dir():
                xupath_parts.append(str(sdk_root / "packages"))
            env["XUPATH"] = os.pathsep.join(xupath_parts)
        env["PATH"] = str(p.resolve().parent) + os.pathsep + env.get("PATH", "")
        xu_bin = str(p.resolve())
    env["XU"] = xu_bin

    if platform.system() == "Windows" and not shutil.which("dxc", path=env.get("PATH")):
        kits = Path("C:/Program Files (x86)/Windows Kits/10/bin")
        if kits.is_dir():
            dxc_hits = sorted(kits.glob("*/x64/dxc.exe"), reverse=True)
            if dxc_hits:
                env["PATH"] = str(dxc_hits[0].parent) + os.pathsep + env.get("PATH", "")
    return xu_bin, env


def run_step(cmd: list[str], env: dict[str, str], label: str | None = None) -> None:
    if label:
        print(f"=== {label} ===", flush=True)
    res = subprocess.run(cmd, cwd=ROOT, env=env)
    if res.returncode != 0:
        raise SystemExit(f"Step failed ({res.returncode}): {' '.join(cmd)}")


def run_contracts(xu_bin: str | None, env: dict[str, str]) -> None:
    py = sys.executable
    run_step([py, "-m", "compileall", "-q", "tools", "native", "tests"], env, "Python bytecode check")
    for script in (
        "tools/check_layers.py",
        "tests/layer_rules_checks.py",
        "tests/shader_cross_backend_checks.py",
    ):
        run_step([py, script], env, script)
    id_cmd = [py, "tools/check_release_identity.py"]
    if xu_bin and Path(xu_bin).is_file():
        id_cmd += ["--xu", xu_bin]
    run_step(id_cmd, env, "tools/check_release_identity.py")


def run_native(xu_bin: str, env: dict[str, str], sdl_include: str | None) -> None:
    run_step([sys.executable, "tools/check_sdk.py", "--xu", xu_bin], env, "SDK version contract")
    cmd = [sys.executable, "native/build.py", "--xu", xu_bin]
    if sdl_include:
        cmd += ["--sdl-include", sdl_include]
    run_step(cmd, env, "Build all native .xulib bridges")


def run_shaders(env: dict[str, str]) -> None:
    run_step([sys.executable, "tools/canvas_shaders.py"], env, "Prepare canvas shaders")
    run_step([sys.executable, "tools/mesh_shaders.py"], env, "Prepare 3D mesh shaders")


def run_check(xu_bin: str, env: dict[str, str]) -> None:
    for target, ui_pack, _ in CHECK_TARGETS:
        step_env = env.copy()
        if ui_pack:
            step_env["XU_UI_PACK"] = "1"
        run_step([xu_bin, "check", target], step_env, f"xu check {target}")


def run_test(xu_bin: str, env: dict[str, str]) -> None:
    build_dir = ROOT / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    run_step([sys.executable, "tests/make_glb_fixtures.py"], env, "Generate GLB fixtures")
    run_step([sys.executable, "tests/make_audio_fixtures.py"], env, "Generate audio fixtures")
    scriptc_bin = build_dir / exe_name("xu-nexus-script")
    run_step([xu_bin, "build", "cmd/scriptc/main.xu", "-o", str(scriptc_bin)], env, "build scriptc for fixture")
    run_step(
        [
            sys.executable,
            "tools/build_script_scene.py",
            "--project",
            "examples/scene_scripts/project.json",
            "--output",
            "build/scene-scripts/world.xuscene",
            "--tool",
            str(scriptc_bin),
        ],
        env,
        "Generate scene-script fixture",
    )
    for py_iso in ("tests/layer_headless_checks.py", "tests/canvas_isolation.py", "tests/scene_process_checks.py"):
        run_step([sys.executable, py_iso], env, py_iso)

    for src, out_stem, extra_args, extra_env in HEADLESS_TESTS:
        out_bin = build_dir / exe_name(out_stem)
        run_step([xu_bin, "build", *extra_args, src, "-o", str(out_bin)], env, f"build {src}")
        step_env = env.copy()
        step_env.update(extra_env)
        run_step([str(out_bin)], step_env, f"run {out_stem}")

    # Round-trip & bundle CLI integration tests
    cli_bin = build_dir / exe_name("nexus-project")
    val_bin = build_dir / exe_name("nexus-project-validate")
    rt_bin = build_dir / exe_name("glb-obj-roundtrip-checks")
    run_step([xu_bin, "build", "cmd/project", "-o", str(cli_bin)], env, "build nexus-project")
    run_step([xu_bin, "build", "cmd/project_validate/main.xu", "-o", str(val_bin)], env, "build nexus-project-validate")
    run_step([xu_bin, "build", "tests/glb_obj_roundtrip_checks.xu", "-o", str(rt_bin)], env, "build glb_obj_roundtrip_checks")
    rt_env = env.copy()
    rt_env["SDL_VIDEODRIVER"] = "nonexistent"
    run_step([str(rt_bin), "--project-cli", str(cli_bin), "--validator", str(val_bin)], rt_env, "run glb-obj-roundtrip-checks")

    if platform.system() != "Windows":
        bc_bin = build_dir / "project-bundle-cli-checks"
        run_step([xu_bin, "build", "tests/project_bundle_cli_checks.xu", "-o", str(bc_bin)], env, "build project_bundle_cli_checks")
        run_step([str(bc_bin)], env, "run project-bundle-cli-checks")


def run_build_tools(xu_bin: str, env: dict[str, str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for src, out_stem, flags, ui_pack in RELEASE_TOOLS:
        step_env = env.copy()
        if ui_pack:
            step_env["XU_UI_PACK"] = "1"
        out_bin = out_dir / exe_name(out_stem)
        run_step([xu_bin, "build", *flags, src, "-o", str(out_bin)], step_env, f"build tool {out_stem}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modes",
        default="contracts,native,shaders,check,test",
        help="Comma-separated modes from: contracts,native,shaders,check,test,build-tools,all",
    )
    parser.add_argument("--xu", help="Path to xu compiler executable")
    parser.add_argument("--sdl-include", help="Path to SDL3 include directory")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "build/release-tools", help="Output dir for build-tools")
    args = parser.parse_args()

    raw_modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    if "all" in raw_modes:
        modes = ["contracts", "native", "shaders", "check", "test", "build-tools"]
    else:
        modes = raw_modes

    xu_bin, env = setup_env(args.xu)
    for mode in modes:
        if mode == "contracts":
            run_contracts(xu_bin if Path(xu_bin).is_file() else None, env)
        elif mode == "native":
            run_native(xu_bin, env, args.sdl_include)
        elif mode == "shaders":
            run_shaders(env)
        elif mode == "check":
            run_check(xu_bin, env)
        elif mode == "test":
            run_test(xu_bin, env)
        elif mode == "build-tools":
            run_build_tools(xu_bin, env, args.out_dir.resolve())
        else:
            raise SystemExit(f"Unknown CI mode: {mode}")
    print(f"PASS: ci_run modes={','.join(modes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

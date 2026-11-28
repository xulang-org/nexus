#!/usr/bin/env python3
"""Build the Nexus WebGL example for WeChat, Douyin, or standard Web."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from webgl_demo_model import crate_glb

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/miniprogram"
PROJECTS = {
    "wechat": (EXAMPLE / "project", "nexus-miniprogram", "WeChat Mini Program"),
    "douyin": (ROOT / "examples/douyin_minigame/project", "nexus-douyin", "Douyin Mini Game"),
    "web": (ROOT / "examples/webgl_web/project", "nexus-web", "Standard Web"),
}
PLATFORM_CONFLICTS = {
    "wechat": ("game.json",),
    "douyin": ("app.json",),
    "web": ("app.json", "game.json"),
}


def build_scene(xu: str, stage: Path, scene: str, wasm_name: str) -> None:
    """Compile one Xu example scene and stage its bundled assets."""
    exports = ["--wasm-export", "nexus_reset", "--wasm-export", "nexus_frame"]
    if scene == "3d":
        example = ROOT / "examples/webgl_3d"
        pixels = (ROOT / "examples/textures3d/assets/uv-grid.png").read_bytes()
        (stage / "assets/crate.glb").write_bytes(crate_glb(pixels))
        exports += ["--wasm-export", "nexus_load_model"]
    else:
        example = EXAMPLE
        shutil.copyfile(ROOT / "examples/arena/assets/player.png", stage / "assets/player.png")
    subprocess.run(
        [xu, "build", str(example), "--target", "wasm32-wasi", *exports, "-o", str(stage / wasm_name)],
        check=True,
    )


def write_web_demo(path: Path, payload: dict) -> None:
    """Write a dual CommonJS / browser-global demo manifest for the web host."""
    encoded = json.dumps(payload, indent=2)
    path.write_text(
        "(function (root, factory) {\n"
        "    const value = factory();\n"
        "    if (typeof module === \"object\" && module.exports) module.exports = value;\n"
        "    root.NexusWebGL = Object.assign(root.NexusWebGL || {}, { demo: value });\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this, function () {\n"
        f"    return {encoded};\n"
        "});\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xu", default=os.environ.get("XU", "xu"))
    parser.add_argument("--platform", "--target", dest="platform", choices=PROJECTS, default="wechat")
    parser.add_argument("--scene", choices=("2d", "3d", "both"), default=None)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--appid")
    args = parser.parse_args()
    scene = args.scene or ("both" if args.platform == "web" else "2d")
    if args.platform != "web" and scene == "both":
        parser.error("--scene both is only supported for web")
    template, directory, label = PROJECTS[args.platform]
    mesh = scene == "3d"
    if scene == "3d":
        directory += "-3d"
    elif scene == "2d" and args.platform == "web":
        directory += "-2d"
    if args.appid is not None:
        if args.platform == "wechat":
            if args.appid != "touristappid" and not re.fullmatch(r"wx[0-9a-f]{16}", args.appid):
                parser.error("expected a WeChat Mini Program AppID")
        elif args.platform == "douyin":
            if not re.fullmatch(r"tt[0-9A-Za-z]+", args.appid):
                parser.error("expected a Douyin Mini Game AppID")
        else:
            parser.error("--appid is not used for web")
    xu = shutil.which(args.xu)
    if not xu:
        parser.error("Xu SDK not found; use --xu to select the SDK")
    subprocess.run([sys.executable,
                    str(ROOT / "tools/check_sdk.py"), "--xu", xu], check=True)

    output = (args.output or ROOT / "build" / directory).resolve()
    if any((output / marker).exists() for marker in PLATFORM_CONFLICTS[args.platform]):
        parser.error("choose an output directory for this platform")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nexus-miniprogram-", dir=output.parent) as temporary:
        stage = Path(temporary)
        shutil.copytree(template, stage, dirs_exist_ok=True)
        shutil.copytree(ROOT / "platform/webgl", stage / "runtime")
        (stage / "assets").mkdir(exist_ok=True)
        if args.platform == "web":
            if scene == "both":
                build_scene(xu, stage, "3d", "game-3d.wasm")
                build_scene(xu, stage, "2d", "game-2d.wasm")
                demo_payload = {
                    "mesh": True,
                    "defaultScene": "3d",
                    "scenes": {
                        "3d": {"wasm": "game-3d.wasm", "model": "assets/crate.glb"},
                        "2d": {"wasm": "game-2d.wasm", "atlas": "assets/player.png"},
                    },
                }
            else:
                build_scene(xu, stage, scene, "game.wasm")
                scene_entry = (
                    {"wasm": "game.wasm", "model": "assets/crate.glb"}
                    if scene == "3d"
                    else {"wasm": "game.wasm", "atlas": "assets/player.png"}
                )
                demo_payload = {"mesh": mesh, "defaultScene": scene, "scenes": {scene: scene_entry}}
            write_web_demo(stage / "runtime/demo.js", demo_payload)
        else:
            (stage / "runtime/demo.js").write_text(f"module.exports = {{ mesh: {str(mesh).lower()} }};\n")
            build_scene(xu, stage, scene, "game.wasm")
            config = stage / "project.config.json"
            if config.is_file():
                if (mesh or args.platform == "douyin") and args.appid is None and (output / config.name).is_file():
                    config.unlink()
                elif args.appid is not None or mesh:
                    metadata = json.loads(config.read_text())
                    if args.appid is not None:
                        metadata["appid"] = args.appid
                    if mesh:
                        metadata["projectname"] += " 3D"
                    config.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        for file in stage.rglob("*"):
            if file.is_file():
                destination = output / file.relative_to(stage)
                destination.parent.mkdir(parents=True, exist_ok=True)
                file.replace(destination)
    print(f"{label} project: {output}")


if __name__ == "__main__":
    main()

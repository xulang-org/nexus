#!/usr/bin/env python3
"""Build the Nexus WebGL example for WeChat or Douyin."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/miniprogram"
PROJECTS = {
    "wechat": (EXAMPLE / "project", "nexus-miniprogram", "WeChat Mini Program"),
    "douyin": (ROOT / "examples/douyin_minigame/project", "nexus-douyin", "Douyin Mini Game"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xu", default=os.environ.get("XU", "xu"))
    parser.add_argument("--platform", choices=PROJECTS, default="wechat")
    parser.add_argument("--scene", choices=("2d", "3d"), default="2d")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--appid")
    args = parser.parse_args()
    template, directory, label = PROJECTS[args.platform]
    mesh = args.scene == "3d"
    example = ROOT / "examples/webgl_3d" if mesh else EXAMPLE
    if mesh:
        directory += "-3d"
    if args.appid is not None:
        if args.platform == "wechat":
            if args.appid != "touristappid" and not re.fullmatch(r"wx[0-9a-f]{16}", args.appid):
                parser.error("expected a WeChat Mini Program AppID")
        elif not re.fullmatch(r"tt[0-9A-Za-z]+", args.appid):
            parser.error("expected a Douyin Mini Game AppID")
    xu = shutil.which(args.xu)
    if not xu:
        parser.error("Xu SDK not found; use --xu to select the SDK")
    subprocess.run([sys.executable,
                    str(ROOT / "tools/check_sdk.py"), "--xu", xu], check=True)

    output = (args.output or ROOT / "build" / directory).resolve()
    other_manifest = "app.json" if args.platform == "douyin" else "game.json"
    if (output / other_manifest).exists():
        parser.error("choose an output directory for this platform")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nexus-miniprogram-", dir=output.parent) as temporary:
        stage = Path(temporary)
        shutil.copytree(template, stage, dirs_exist_ok=True)
        shutil.copytree(ROOT / "platform/webgl", stage / "runtime")
        (stage / "runtime/demo.js").write_text(f"module.exports = {{ mesh: {str(mesh).lower()} }};\n")
        if not mesh:
            (stage / "assets").mkdir()
            shutil.copyfile(ROOT / "examples/arena/assets/player.png", stage / "assets/player.png")
        config = stage / "project.config.json"
        if (mesh or args.platform == "douyin") and args.appid is None and (output / config.name).is_file():
            config.unlink()
        elif args.appid is not None or mesh:
            metadata = json.loads(config.read_text())
            if args.appid is not None:
                metadata["appid"] = args.appid
            if mesh:
                metadata["projectname"] += " 3D"
            config.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        subprocess.run([xu, "build", str(example), "--target", "wasm32-wasi",
                        "--wasm-export", "nexus_reset", "--wasm-export", "nexus_frame",
                        "-o", str(stage / "game.wasm")], check=True)
        for file in stage.rglob("*"):
            if file.is_file():
                destination = output / file.relative_to(stage)
                destination.parent.mkdir(parents=True, exist_ok=True)
                file.replace(destination)
    print(f"{label} project: {output}")


if __name__ == "__main__":
    main()

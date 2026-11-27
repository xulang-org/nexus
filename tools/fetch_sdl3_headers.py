#!/usr/bin/env python3
"""Download and verify pinned SDL3 headers (and optional minimal shared runtime) for Nexus CI."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

SDL_VERSION = "3.4.14"
SDL_URL = f"https://github.com/libsdl-org/SDL/releases/download/release-{SDL_VERSION}/SDL3-{SDL_VERSION}.tar.gz"
SDL_SHA256 = "30d4aa2b3037718142b32dffd4e72f917ebb6cc5227150e7bb9c45efb2153aeb"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def runtime_lib_name() -> str:
    sys_name = platform.system()
    if sys_name == "Darwin":
        return "libSDL3.dylib"
    if sys_name == "Windows":
        return "SDL3.dll"
    return "libSDL3.so.0"


def find_built_runtime(build_dir: Path) -> Path:
    sys_name = platform.system()
    if sys_name == "Windows":
        hits = sorted(build_dir.rglob("SDL3.dll"))
    elif sys_name == "Darwin":
        hits = [p for p in sorted(build_dir.rglob("libSDL3*.dylib")) if p.is_file() and not p.is_symlink()]
    else:
        hits = [p for p in sorted(build_dir.rglob("libSDL3.so*")) if p.is_file() and not p.is_symlink()]
    if not hits:
        raise SystemExit(f"Built SDL3 shared library not found under {build_dir}")
    return hits[0]


def ensure_sdl3_archive(archive_path: Path) -> None:
    req = urllib.request.Request(SDL_URL, headers={"User-Agent": "nexus-ci/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, archive_path.open("wb") as out:
        shutil.copyfileobj(resp, out)
    digest = sha256_file(archive_path)
    if digest != SDL_SHA256:
        raise SystemExit(f"SDL3 tarball SHA-256 mismatch: {digest} != {SDL_SHA256}")


def extract_sdl3(dest: Path, full_source: bool) -> Path:
    include_dir = dest / f"SDL3-{SDL_VERSION}" / "include"
    src_dir = dest / f"SDL3-{SDL_VERSION}"
    need_extract = not (include_dir / "SDL3" / "SDL.h").is_file() or (
        full_source and not (src_dir / "CMakeLists.txt").is_file()
    )
    if not need_extract:
        print(f"Reusing cached SDL3 {SDL_VERSION} at {src_dir}")
        return src_dir

    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexus-sdl3-") as tmp:
        archive = Path(tmp) / f"SDL3-{SDL_VERSION}.tar.gz"
        ensure_sdl3_archive(archive)
        prefix = f"SDL3-{SDL_VERSION}/" if full_source else f"SDL3-{SDL_VERSION}/include/"
        with tarfile.open(archive, "r:gz") as tf:
            members = []
            for m in tf.getmembers():
                if not m.name.startswith(prefix):
                    continue
                rel = Path(m.name)
                if rel.is_absolute() or ".." in rel.parts:
                    raise SystemExit(f"Unsafe tar entry: {m.name}")
                members.append(m)
            tf.extractall(dest, members=members, filter="data")
    return src_dir


def build_minimal_runtime(src_dir: Path, runtime_path: Path) -> None:
    if runtime_path.is_file():
        print(f"Reusing cached SDL3 {SDL_VERSION} runtime at {runtime_path}")
        return
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexus-sdl3-build-") as tmp_build:
        cfg_cmd = [
            "cmake",
            "-S", str(src_dir),
            "-B", tmp_build,
            "-DCMAKE_BUILD_TYPE=Release",
            "-DSDL_SHARED=ON",
            "-DSDL_STATIC=OFF",
            "-DSDL_TEST_LIBRARY=OFF",
            "-DSDL_TESTS=OFF",
            "-DSDL_EXAMPLES=OFF",
            "-DSDL_VIDEO=OFF",
            "-DSDL_RENDER=OFF",
            "-DSDL_GPU=OFF",
            "-DSDL_VULKAN=OFF",
            "-DSDL_OPENGL=OFF",
            "-DSDL_OPENGLES=OFF",
            "-DSDL_METAL=OFF",
            "-DSDL_DIRECTX=OFF",
            "-DSDL_JOYSTICK=OFF",
            "-DSDL_HAPTIC=OFF",
            "-DSDL_HIDAPI=OFF",
            "-DSDL_POWER=OFF",
            "-DSDL_SENSOR=OFF",
            "-DSDL_CAMERA=OFF",
            "-DSDL_DIALOG=OFF",
            "-DSDL_TRAY=OFF",
        ]
        subprocess.run(cfg_cmd, check=True)
        jobs = str(max(2, os.cpu_count() or 4))
        subprocess.run(
            ["cmake", "--build", tmp_build, "--config", "Release", "--parallel", jobs],
            check=True,
        )
        built = find_built_runtime(Path(tmp_build))
        shutil.copy2(built, runtime_path)
        if platform.system() != "Windows":
            runtime_path.chmod(0o755)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True, help="Directory to cache/extract SDL3 headers")
    parser.add_argument("--with-runtime", action="store_true", help="Also build minimal shared SDL3 runtime library")
    parser.add_argument("--github-env", action="store_true", help="Write NEXUS_SDL3_* vars to GITHUB_ENV")
    args = parser.parse_args()

    dest = args.dest.resolve()
    src_dir = extract_sdl3(dest, full_source=args.with_runtime)
    include_dir = src_dir / "include"
    if not (include_dir / "SDL3" / "SDL.h").is_file():
        raise SystemExit(f"SDL3/SDL.h missing under {include_dir}")

    runtime_path = dest / "runtime" / runtime_lib_name()
    if args.with_runtime:
        build_minimal_runtime(src_dir, runtime_path)
        # Keep headers and built runtime; source tree is not needed once runtime is cached.
        shutil.rmtree(src_dir / "src", ignore_errors=True)
        shutil.rmtree(src_dir / "test", ignore_errors=True)

    if args.github_env:
        env_file = os.environ.get("GITHUB_ENV")
        if env_file:
            with open(env_file, "a", encoding="utf-8") as fh:
                fh.write(f"NEXUS_SDL3_INCLUDE={include_dir}\n")
                if args.with_runtime and runtime_path.is_file():
                    fh.write(f"NEXUS_SDL3_RUNTIME={runtime_path}\n")
                    fh.write(f"XU_SDL_LIBRARY={runtime_path}\n")
                    fh.write(f"XU_NEXUS_SDL_LIBRARY={runtime_path}\n")
                    fh.write(f"XU_NEXUS_SDL_AUDIO_LIBRARY={runtime_path}\n")
    print(f"PASS: SDL3 {SDL_VERSION} headers ready at {include_dir}")
    if args.with_runtime:
        print(f"PASS: SDL3 {SDL_VERSION} minimal runtime ready at {runtime_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

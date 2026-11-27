#!/usr/bin/env python3
"""Download and verify pinned SDL3 headers for native bridge compilation."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True, help="Directory to cache/extract SDL3 headers")
    parser.add_argument("--github-env", action="store_true", help="Write NEXUS_SDL3_INCLUDE to GITHUB_ENV")
    args = parser.parse_args()

    dest = args.dest.resolve()
    include_dir = dest / f"SDL3-{SDL_VERSION}" / "include"
    if (include_dir / "SDL3" / "SDL.h").is_file():
        print(f"Reusing cached SDL3 {SDL_VERSION} headers at {include_dir}")
    else:
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nexus-sdl3-") as tmp:
            archive = Path(tmp) / f"SDL3-{SDL_VERSION}.tar.gz"
            req = urllib.request.Request(SDL_URL, headers={"User-Agent": "nexus-ci/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, archive.open("wb") as out:
                shutil.copyfileobj(resp, out)
            digest = sha256_file(archive)
            if digest != SDL_SHA256:
                raise SystemExit(f"SDL3 tarball SHA-256 mismatch: {digest} != {SDL_SHA256}")
            prefix = f"SDL3-{SDL_VERSION}/include/"
            with tarfile.open(archive, "r:gz") as tf:
                members = []
                for m in tf.getmembers():
                    if not m.name.startswith(prefix):
                        continue
                    rel = Path(m.name)
                    if rel.is_absolute() or ".." in rel.parts:
                        raise SystemExit(f"Unsafe tar entry: {m.name}")
                    members.append(m)
                tf.extractall(dest, members=members)

    if not (include_dir / "SDL3" / "SDL.h").is_file():
        raise SystemExit(f"SDL3/SDL.h missing under {include_dir}")
    if args.github_env:
        env_file = os.environ.get("GITHUB_ENV")
        if env_file:
            with open(env_file, "a", encoding="utf-8") as fh:
                fh.write(f"NEXUS_SDL3_INCLUDE={include_dir}\n")
    print(f"PASS: SDL3 {SDL_VERSION} headers ready at {include_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

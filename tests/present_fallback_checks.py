#!/usr/bin/env python3
"""Verify 2D, SDF, 3D, and Overlay2D behavior across GPU, software, and headless modes."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    xu = os.environ.get("XU", "xu")
    bin_path = ROOT / "build" / "present-fallback-checks"
    build = subprocess.run(
        [xu, "build", "tests/present_fallback_checks.xu", "-o", str(bin_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if build.returncode != 0:
        sys.stderr.write(build.stdout + build.stderr)
        return build.returncode

    cases = [
        ("gpu", {}),
        ("software", {"SDL_GPU_DRIVER": "nonexistent", "SDL_VIDEODRIVER": "dummy"}),
        (
            "headless",
            {
                "SDL_VIDEODRIVER": "nonexistent",
                "XU_SDL_LIBRARY": str(ROOT / "build" / "nonexistent_sdl.dylib"),
            },
        ),
    ]
    for mode, extra in cases:
        env = dict(os.environ, **extra)
        proc = subprocess.run(
            [str(bin_path), mode],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            sys.stderr.write(f"[{mode}] failed:\n{proc.stdout}\n{proc.stderr}")
            return proc.returncode
        expected = f"PASS: present fallback & overlay compositor verified in {mode} mode"
        if expected not in proc.stdout:
            sys.stderr.write(f"[{mode}] unexpected output:\n{proc.stdout}\n{proc.stderr}")
            return 1
        print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

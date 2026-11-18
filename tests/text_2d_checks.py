#!/usr/bin/env python3
"""Verify 2D text R8 mask rendering, atlas grow sync, clip, and 3D+SDF+Text overlay across GPU, software, and headless modes."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
ARIAL_PATH = Path("/System/Library/Fonts/Supplemental/Arial.ttf")


def read_png_rgba(path: Path):
    raw = path.read_bytes()
    w, h = struct.unpack_from(">II", raw, 16)
    at = 8
    packed = bytearray()
    while at < len(raw):
        size = struct.unpack_from(">I", raw, at)[0]
        if raw[at + 4:at + 8] == b"IDAT":
            packed.extend(raw[at + 8:at + 8 + size])
        at += size + 12
    rows = zlib.decompress(packed)
    assert all(rows[y * (w * 4 + 1)] == 0 for y in range(h))
    return w, h, b"".join(rows[y * (w * 4 + 1) + 1:(y + 1) * (w * 4 + 1)] for y in range(h))


def check_parity(prefix: str):
    gpu_path = ROOT / "build" / f"{prefix}-gpu.png"
    sw_path = ROOT / "build" / f"{prefix}-software.png"
    hd_path = ROOT / "build" / f"{prefix}-headless.png"
    gw, gh, gp = read_png_rgba(gpu_path)
    sw, sh, sp = read_png_rgba(sw_path)
    hw, hh, hp = read_png_rgba(hd_path)
    assert (gw, gh) == (sw, sh) == (hw, hh)
    assert sp == hp, f"{prefix}: software vs headless mismatch"
    max_delta = 0
    over4 = 0
    total_abs = 0
    n_bytes = len(gp)
    for i in range(n_bytes):
        d = abs(gp[i] - sp[i])
        if d > max_delta:
            max_delta = d
        if d > 4:
            over4 += 1
        total_abs += d
    mean_abs = total_abs / max(1, n_bytes)
    assert mean_abs < 1.0, f"{prefix}: mean GPU vs SW delta too high: {mean_abs}"
    assert over4 <= gw * gh * 4 * 0.02, f"{prefix}: too many GPU vs SW mismatched channels: {over4}/{n_bytes}"
    print(f"PARITY {prefix}: sw==hd exact, gpu-vs-sw max={max_delta} mean={mean_abs:.4f} over4={over4}/{n_bytes}")


def main() -> int:
    xu = os.environ.get("XU", "xu")
    bin_path = ROOT / "build" / "text-2d-checks"
    build = subprocess.run(
        [xu, "build", "tests/text_2d_checks.xu", "-o", str(bin_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if build.returncode != 0:
        sys.stderr.write(build.stdout + build.stderr)
        return build.returncode

    font_arg = str(ARIAL_PATH) if ARIAL_PATH.exists() else ""
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
        argv = [str(bin_path), mode]
        if font_arg:
            argv.append(font_arg)
        proc = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            sys.stderr.write(f"[{mode}] failed:\n{proc.stdout}\n{proc.stderr}")
            return proc.returncode
        expected = f"PASS: 2D text mask pipeline & 3D+SDF+Text overlay verified in {mode} mode"
        if expected not in proc.stdout:
            sys.stderr.write(f"[{mode}] unexpected output:\n{proc.stdout}\n{proc.stderr}")
            return 1
        print(proc.stdout.strip())

    check_parity("text-2d-builtin")
    check_parity("text-2d-grown")
    if font_arg:
        check_parity("text-2d-arial")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

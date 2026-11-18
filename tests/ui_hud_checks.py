#!/usr/bin/env python3
"""Verify nexus/integration/ui InputBridge, widgets, XDF1 replay, and 3D overlay parity."""
from __future__ import annotations

import os
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def load_png_rgba(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"invalid PNG signature: {path}")
    pos = 8
    width = 0
    height = 0
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
            if bit_depth != 8 or color_type != 6:
                raise AssertionError(f"expected 8-bit RGBA PNG in {path}, got {bit_depth}/{color_type}")
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    bpp = 4
    row_bytes = width * bpp
    stride = 1 + row_bytes
    if len(raw) != height * stride:
        raise AssertionError(f"unexpected decoded PNG size for {path}: {len(raw)} vs {height * stride}")
    out = bytearray(height * row_bytes)
    prev = bytes(row_bytes)
    for y in range(height):
        base = y * stride
        ftype = raw[base]
        row = bytearray(raw[base + 1 : base + 1 + row_bytes])
        if ftype == 1:
            for i in range(bpp, row_bytes):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(row_bytes):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(row_bytes):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(row_bytes):
                left = row[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(left, prev[i], up_left)) & 0xFF
        elif ftype != 0:
            raise AssertionError(f"unsupported PNG filter {ftype} in {path}")
        out[y * row_bytes : (y + 1) * row_bytes] = row
        prev = bytes(row)
    return width, height, bytes(out)


def check_parity(name: str, gpu_path: Path, sw_path: Path) -> None:
    gw, gh, gp = load_png_rgba(gpu_path)
    sw, sh, sp = load_png_rgba(sw_path)
    if (gw, gh) != (sw, sh):
        raise AssertionError(f"[{name}] GPU {gw}x{gh} vs SW {sw}x{sh} size mismatch")
    total_channels = gw * gh * 4
    total_abs = 0
    over4 = 0
    for idx in range(0, total_channels, 4):
        d = max(abs(gp[idx + c] - sp[idx + c]) for c in range(4))
        total_abs += abs(gp[idx] - sp[idx]) + abs(gp[idx + 1] - sp[idx + 1]) + abs(gp[idx + 2] - sp[idx + 2]) + abs(gp[idx + 3] - sp[idx + 3])
        if d > 4:
            over4 += 1
    mean_abs = total_abs / total_channels
    over4_ratio = over4 / (gw * gh)
    print(f"PARITY [{name}] gpu-vs-sw: mean_abs={mean_abs:.4f} over4={over4_ratio * 100.0:.2f}%")
    if mean_abs >= 1.0 or over4_ratio > 0.02:
        raise AssertionError(
            f"[{name}] GPU vs SW parity exceeded threshold: mean_abs={mean_abs:.4f}, over4={over4_ratio * 100.0:.2f}%"
        )


def main() -> int:
    xu = os.environ.get("XU", "xu")
    bin_path = ROOT / "build" / "ui-hud-checks"
    build = subprocess.run(
        [xu, "build", "tests/ui_hud_checks.xu", "-o", str(bin_path)],
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
        expected = f"PASS: UI HUD widgets, input, XDF1 replay, and 3D+Overlay2D verified in {mode} mode"
        if expected not in proc.stdout:
            sys.stderr.write(f"[{mode}] unexpected output:\n{proc.stdout}\n{proc.stderr}")
            return 1
        print(proc.stdout.strip())

    for scene_name in ("widgets", "xdf", "phone-widgets", "composite"):
        sw_file = ROOT / "build" / f"ui-{scene_name}-software.png"
        hd_file = ROOT / "build" / f"ui-{scene_name}-headless.png"
        if sw_file.read_bytes() != hd_file.read_bytes():
            raise AssertionError(f"software vs headless PNG mismatch for {scene_name}")
        print(f"EXACT [{scene_name}] software == headless ({sw_file.stat().st_size} bytes)")

    check_parity("widgets", ROOT / "build" / "ui-widgets-gpu.png", ROOT / "build" / "ui-widgets-software.png")
    check_parity("xdf", ROOT / "build" / "ui-xdf-gpu.png", ROOT / "build" / "ui-xdf-software.png")
    check_parity("phone-widgets", ROOT / "build" / "ui-phone-widgets-gpu.png", ROOT / "build" / "ui-phone-widgets-software.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

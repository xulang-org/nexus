#!/usr/bin/env python3
"""Download, verify, and activate the Xu SDK version pinned in xu.xun."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = "xulang-org/xu"


def host_target() -> str:
    systems = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}
    machines = {
        "arm64": "arm64",
        "ARM64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "AMD64": "x64",
    }
    sys_name = systems.get(platform.system())
    arch_name = machines.get(platform.machine())
    if not sys_name or not arch_name:
        raise SystemExit(f"Unsupported host platform: {platform.system()} {platform.machine()}")
    return f"{sys_name}-{arch_name}"


def read_pinned_xu_version() -> str:
    text = (ROOT / "xu.xun").read_text(encoding="utf-8")
    m = re.search(r"^xu:\s*!ver\s+([^\s]+)$", text, re.MULTILINE)
    if not m:
        raise SystemExit("Unable to locate `xu: !ver ...` in xu.xun")
    return m.group(1)


def sdk_compiler_path(sdk_root: Path, target: str) -> Path:
    suffix = ".exe" if target.startswith("windows-") else ""
    return sdk_root / "bin" / f"xu{suffix}"


def verify_compiler(compiler: Path, expected: str) -> bool:
    if not compiler.is_file():
        return False
    res = subprocess.run([str(compiler), "--version"], capture_output=True, text=True, timeout=15)
    m = re.search(r"Xu Compiler Toolchain v([^\s]+)", res.stdout + res.stderr)
    actual = m.group(1) if m else ""
    return res.returncode == 0 and actual == expected


def download_asset(tag: str, filename: str, dest: Path) -> None:
    if shutil.which("gh"):
        cmd = [
            "gh", "release", "download", tag,
            "--repo", REPO,
            "--pattern", filename,
            "--dir", str(dest.parent),
            "--clobber",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and dest.is_file():
            return
    url = f"https://github.com/{REPO}/releases/download/{tag}/{filename}"
    req = urllib.request.Request(url, headers={"User-Agent": "nexus-ci/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def parse_sha256sums(path: Path) -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            digest, name = parts[0].strip(), parts[1].lstrip("*").strip()
            sums[name] = digest.lower()
    return sums


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_sdk(archive: Path, dest: Path, target: str) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexus-xu-extract-") as tmp:
        tmp_dir = Path(tmp)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    rel = Path(info.filename)
                    if rel.is_absolute() or ".." in rel.parts:
                        raise SystemExit(f"Unsafe zip entry: {info.filename}")
                zf.extractall(tmp_dir)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                for member in tf.getmembers():
                    rel = Path(member.name)
                    if rel.is_absolute() or ".." in rel.parts:
                        raise SystemExit(f"Unsafe tar entry: {member.name}")
                tf.extractall(tmp_dir, filter="data")
        entries = list(tmp_dir.iterdir())
        src_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp_dir
        shutil.copytree(src_root, dest, dirs_exist_ok=True)
    if not target.startswith("windows-"):
        bin_dir = dest / "bin"
        if bin_dir.is_dir():
            for child in bin_dir.iterdir():
                if child.is_file():
                    child.chmod(child.stat().st_mode | 0o755)


def write_github_env(sdk_root: Path, compiler: Path) -> None:
    sdk_str = str(sdk_root.resolve())
    stdlib_str = str((sdk_root / "src").resolve())
    pkg_dir = sdk_root / "packages"
    xupath_entries = [stdlib_str]
    if pkg_dir.is_dir():
        xupath_entries.append(str(pkg_dir.resolve()))
    xupath_str = os.pathsep.join(xupath_entries)

    env_file = os.environ.get("GITHUB_ENV")
    if env_file:
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write(f"NEXUS_XU_SDK={sdk_str}\n")
            fh.write(f"XU_ROOT={sdk_str}\n")
            fh.write(f"XU_STDLIB_ROOT={stdlib_str}\n")
            fh.write(f"XUPATH={xupath_str}\n")
            fh.write(f"XU={compiler.resolve()}\n")
    path_file = os.environ.get("GITHUB_PATH")
    if path_file:
        with open(path_file, "a", encoding="utf-8") as fh:
            fh.write(f"{(sdk_root / 'bin').resolve()}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Xu SDK version (defaults to xu.xun)")
    parser.add_argument("--target", help="Target platform (defaults to host)")
    parser.add_argument("--dest", type=Path, required=True, help="Destination SDK root directory")
    parser.add_argument("--github-env", action="store_true", help="Export SDK env vars to GITHUB_ENV/GITHUB_PATH")
    args = parser.parse_args()

    version = (args.version or read_pinned_xu_version()).removeprefix("v")
    target = args.target or host_target()
    tag = f"v{version}"
    ext = "zip" if target.startswith("windows-") else "tar.gz"
    asset_name = f"xu-{tag}-{target}.{ext}"
    dest = args.dest.resolve()
    compiler = sdk_compiler_path(dest, target)

    if verify_compiler(compiler, version):
        print(f"Reusing cached Xu SDK {version} at {dest}")
    else:
        with tempfile.TemporaryDirectory(prefix="nexus-xu-dl-") as tmp:
            dl_dir = Path(tmp)
            sums_path = dl_dir / "SHA256SUMS"
            asset_path = dl_dir / asset_name
            download_asset(tag, "SHA256SUMS", sums_path)
            sums = parse_sha256sums(sums_path)
            expected_digest = sums.get(asset_name)
            if not expected_digest:
                raise SystemExit(f"Missing {asset_name} entry in {tag} SHA256SUMS")
            download_asset(tag, asset_name, asset_path)
            actual_digest = file_sha256(asset_path)
            if actual_digest != expected_digest:
                raise SystemExit(f"SHA-256 mismatch for {asset_name}: {actual_digest} != {expected_digest}")
            extract_sdk(asset_path, dest, target)

    if not verify_compiler(compiler, version):
        raise SystemExit(f"Installed Xu compiler at {compiler} failed version check for {version}")
    if args.github_env:
        write_github_env(dest, compiler)
    print(f"PASS: Xu SDK {version} ({target}) ready at {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

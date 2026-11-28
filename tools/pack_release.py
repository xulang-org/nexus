#!/usr/bin/env python3
"""Stage per-platform Nexus Engine release bundles and assemble multi-platform .xulib + SHA256SUMS."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile

if __package__:
    from .manifest import DESKTOP_TARGETS, NATIVE_LIBS, RELEASE_TOOLS
else:
    from manifest import DESKTOP_TARGETS, NATIVE_LIBS, RELEASE_TOOLS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DATE_EPOCH = 1767225600


def read_nexus_version() -> str:
    text = (ROOT / "xu.xun").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*!ver\s+([^\s]+)$", text, re.MULTILINE)
    if not m:
        raise SystemExit("Unable to read `version:` from xu.xun")
    return m.group(1)


def read_xu_version() -> str:
    text = (ROOT / "xu.xun").read_text(encoding="utf-8")
    m = re.search(r"^xu:\s*!ver\s+([^\s]+)$", text, re.MULTILINE)
    return m.group(1) if m else "unknown"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_single_slice(xulib_path: Path, target: str) -> bytes:
    data = xulib_path.read_bytes()
    assert len(data) >= 19 and data[:7] == b"XULIB\x01\0", f"Invalid XULIB header in {xulib_path}"
    pos = 15 + struct.unpack_from("<I", data, 11)[0]
    count, = struct.unpack_from("<I", data, pos)
    pos += 4
    for _ in range(count):
        tlen, = struct.unpack_from("<H", data, pos)
        pos += 2
        tname = data[pos:pos + tlen].decode("ascii")
        pos += tlen
        klen = data[pos]
        pos += 1
        kind = data[pos:pos + klen]
        pos += klen
        offset, size = struct.unpack_from("<QQ", data, pos)
        pos += 16
        digest = data[pos:pos + 32]
        pos += 32
        raw = data[offset:offset + size]
        if tname == target:
            assert kind == b"archive" and len(raw) == size
            assert hashlib.sha256(raw).digest() == digest
            return raw
    raise SystemExit(f"Target slice {target} not found in {xulib_path}")


def resolve_source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is None or not raw.strip():
        return DEFAULT_SOURCE_DATE_EPOCH
    return int(raw)


def write_dir_archive(src_dir: Path, archive_prefix: str, dest_archive: Path, is_zip: bool) -> None:
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    dest_archive.parent.mkdir(parents=True, exist_ok=True)
    epoch = resolve_source_date_epoch()
    if is_zip:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        zip_dt = (max(dt.year, 1980), dt.month, dt.day, dt.hour, dt.minute, dt.second)
        with zipfile.ZipFile(dest_archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in files:
                rel = p.relative_to(src_dir).as_posix()
                zi = zipfile.ZipInfo(filename=f"{archive_prefix}/{rel}", date_time=zip_dt)
                zi.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if PurePosixPath(rel).parts[0] == "bin" else 0o644
                zi.create_system = 3
                zi.external_attr = (0o100000 | mode) << 16
                zf.writestr(zi, p.read_bytes())
    else:
        with dest_archive.open("wb") as raw_out:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, mtime=epoch) as gz:
                with tarfile.open(fileobj=gz, mode="w") as tf:
                    for p in files:
                        rel = p.relative_to(src_dir).as_posix()
                        info = tf.gettarinfo(str(p), arcname=f"{archive_prefix}/{rel}")
                        info.uid = 0
                        info.gid = 0
                        info.uname = "root"
                        info.gname = "root"
                        info.mtime = epoch
                        if PurePosixPath(rel).parts[0] == "bin":
                            info.mode = 0o755
                        else:
                            info.mode = 0o644
                        with p.open("rb") as fh:
                            tf.addfile(info, fh)


def stage_target(args: argparse.Namespace) -> int:
    version = (args.version or read_nexus_version()).removeprefix("v")
    tag = f"v{version}"
    target = args.target
    out_dir = args.out_dir.resolve()
    tools_dir = args.tools_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"nexus-stage-{target}-") as tmp:
        stage_root = Path(tmp) / "stage"
        (stage_root / "bin").mkdir(parents=True)
        (stage_root / "native").mkdir(parents=True)
        (stage_root / "shaders" / "canvas").mkdir(parents=True)
        (stage_root / "shaders" / "mesh").mkdir(parents=True)

        suffix = ".exe" if target.startswith("windows-") else ""
        for _, tool, _, _ in RELEASE_TOOLS:
            src_bin = tools_dir / f"{tool}{suffix}"
            if not src_bin.is_file():
                raise SystemExit(f"Missing built tool binary: {src_bin}")
            dst_bin = stage_root / "bin" / src_bin.name
            shutil.copy2(src_bin, dst_bin)
            if not target.startswith("windows-"):
                dst_bin.chmod(0o755)

        slices_dir = out_dir / "slices" / target
        slices_dir.mkdir(parents=True, exist_ok=True)
        for _, lib_name in NATIVE_LIBS:
            src_lib = ROOT / "native" / f"{lib_name}.xulib"
            if not src_lib.is_file():
                raise SystemExit(f"Missing native library: {src_lib}")
            # Validate slice presence before staging
            _ = extract_single_slice(src_lib, target)
            shutil.copy2(src_lib, stage_root / "native" / src_lib.name)
            shutil.copy2(src_lib, slices_dir / src_lib.name)

        for shader_kind, src_sub in (("canvas", ROOT / "build/canvas-shaders"), ("mesh", ROOT / "build/mesh-shaders")):
            if not src_sub.is_dir():
                raise SystemExit(f"Missing prepared shader dir: {src_sub}")
            shutil.copytree(src_sub, stage_root / "shaders" / shader_kind, dirs_exist_ok=True)

        for doc_name in ("xu.xun", "LICENSE", "README.md", "RELEASES.md", "RELEASES.zh-CN.md"):
            src_doc = ROOT / doc_name
            if src_doc.is_file():
                shutil.copy2(src_doc, stage_root / doc_name)

        inventory = {}
        for p in sorted(stage_root.rglob("*")):
            if p.is_file():
                inventory[p.relative_to(stage_root).as_posix()] = sha256_file(p)

        meta = {
            "product": "nexus",
            "version": version,
            "xu": read_xu_version(),
            "target": target,
            "files": inventory,
        }
        (stage_root / "bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        ext = "zip" if target.startswith("windows-") else "tar.gz"
        archive_path = out_dir / f"nexus-{tag}-{target}.{ext}"
        write_dir_archive(stage_root, f"nexus-{tag}", archive_path, is_zip=(ext == "zip"))
        print(f"Staged {archive_path} ({len(inventory)} files)")
    return 0


def assemble_release(args: argparse.Namespace) -> int:
    version = (args.version or read_nexus_version()).removeprefix("v")
    tag = f"v{version}"
    staged_dir = args.staged_dir.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    xu_bin = args.xu

    for target in DESKTOP_TARGETS:
        ext = "zip" if target.startswith("windows-") else "tar.gz"
        src_archive = staged_dir / f"nexus-{tag}-{target}.{ext}"
        if not src_archive.is_file():
            raise SystemExit(f"Missing staged archive for {target}: {src_archive}")
        shutil.copy2(src_archive, out_dir / src_archive.name)

    with tempfile.TemporaryDirectory(prefix="nexus-assemble-") as tmp:
        work = Path(tmp)
        unified_root = work / "native-all"
        (unified_root / "native").mkdir(parents=True)

        for manifest_name, lib_name in NATIVE_LIBS:
            cmd = [xu_bin, "native", "pack", "--manifest", str(ROOT / "native" / manifest_name)]
            for target in DESKTOP_TARGETS:
                slice_xulib = staged_dir / "slices" / target / f"{lib_name}.xulib"
                if not slice_xulib.is_file():
                    raise SystemExit(f"Missing target slice {slice_xulib}")
                raw_archive = extract_single_slice(slice_xulib, target)
                a_path = work / f"{lib_name}-{target}.a"
                a_path.write_bytes(raw_archive)
                cmd += ["--slice", f"{target}={a_path}"]
            out_xulib = unified_root / "native" / f"{lib_name}.xulib"
            cmd += ["-o", str(out_xulib)]
            subprocess.run(cmd, cwd=ROOT, check=True)

        for doc_name in ("xu.xun", "LICENSE", "README.md", "RELEASES.md", "RELEASES.zh-CN.md"):
            src_doc = ROOT / doc_name
            if src_doc.is_file():
                shutil.copy2(src_doc, unified_root / doc_name)

        inventory = {}
        for p in sorted(unified_root.rglob("*")):
            if p.is_file():
                inventory[p.relative_to(unified_root).as_posix()] = sha256_file(p)
        meta = {
            "product": "nexus",
            "version": version,
            "xu": read_xu_version(),
            "target": "native-all",
            "targets": list(DESKTOP_TARGETS),
            "files": inventory,
        }
        (unified_root / "bundle.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        native_all_archive = out_dir / f"nexus-{tag}-native-all.tar.gz"
        write_dir_archive(unified_root, f"nexus-{tag}-native-all", native_all_archive, is_zip=False)

    assets = [
        *[f"nexus-{tag}-{t}.{'zip' if t.startswith('windows-') else 'tar.gz'}" for t in DESKTOP_TARGETS],
        f"nexus-{tag}-native-all.tar.gz",
    ]
    sums_lines = [f"{sha256_file(out_dir / name)}  {name}" for name in assets]
    (out_dir / "SHA256SUMS").write_text("\n".join(sums_lines) + "\n", encoding="utf-8")

    manifest_lines = [
        "## 发布资产清单 (Release Assets)\n",
        "| 资产包 (Asset) | 平台范围 | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for name in assets:
        digest = sha256_file(out_dir / name)
        scope = "All 5 desktop platforms (merged .xulib slices)" if "native-all" in name else name.replace(f"nexus-{tag}-", "").split(".")[0]
        manifest_lines.append(f"| `{name}` | {scope} | `{digest}` |")
    manifest_lines.append("")
    manifest_path = out_dir / "RELEASE_MANIFEST.md"
    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")

    notes_cmd = [
        sys.executable,
        str(ROOT / "tools/generate_release_notes.py"),
        "--tag", tag,
        "--manifest", str(manifest_path),
        "--output", str(out_dir / "RELEASE_NOTES.md"),
    ]
    if args.prev_tag:
        notes_cmd += ["--prev-tag", args.prev_tag]
    if args.custom_notes:
        notes_cmd += ["--custom-notes", str(args.custom_notes)]
    subprocess.run(notes_cmd, cwd=ROOT, check=True)

    receipt_path = args.receipt or (out_dir.parent / "validation.json")
    verify_cmd = [
        sys.executable,
        str(ROOT / "tools/verify_release_bundle.py"),
        "--root", str(out_dir),
        "--version", version,
        "--commit", args.commit or "",
        "--receipt", str(receipt_path),
    ]
    subprocess.run(verify_cmd, cwd=ROOT, check=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_stage = sub.add_parser("stage-target", help="Stage a single platform release archive")
    p_stage.add_argument("--target", required=True, choices=DESKTOP_TARGETS)
    p_stage.add_argument("--version", help="Release version (defaults to xu.xun)")
    p_stage.add_argument("--tools-dir", type=Path, required=True)
    p_stage.add_argument("--out-dir", type=Path, required=True)
    p_stage.set_defaults(func=stage_target)

    p_asm = sub.add_parser("assemble", help="Merge all target slices and generate SHA256SUMS + receipt")
    p_asm.add_argument("--staged-dir", type=Path, required=True)
    p_asm.add_argument("--out-dir", type=Path, required=True)
    p_asm.add_argument("--xu", required=True, help="Path to xu compiler executable")
    p_asm.add_argument("--version", help="Release version (defaults to xu.xun)")
    p_asm.add_argument("--commit", default="")
    p_asm.add_argument("--prev-tag")
    p_asm.add_argument("--custom-notes", type=Path)
    p_asm.add_argument("--receipt", type=Path)
    p_asm.set_defaults(func=assemble_release)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

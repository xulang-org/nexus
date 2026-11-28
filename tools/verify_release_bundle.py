#!/usr/bin/env python3
"""Verify Nexus release archives, tool architectures, multi-platform .xulib slices, and SHA256SUMS."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile
import zipfile

if __package__:
    from .manifest import DESKTOP_TARGETS, NATIVE_LIBS, RELEASE_TOOLS
else:
    from manifest import DESKTOP_TARGETS, NATIVE_LIBS, RELEASE_TOOLS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def verify_binary_header(header: bytes, target: str, label: str) -> None:
    if target.startswith("windows-"):
        assert header[:2] == b"MZ", f"{label}: missing MZ header"
        pe_off = struct.unpack_from("<I", header, 60)[0]
        assert header[pe_off:pe_off + 4] == b"PE\0\0", f"{label}: missing PE signature"
        machine = struct.unpack_from("<H", header, pe_off + 4)[0]
        expected = 0xAA64 if target.endswith("arm64") else 0x8664
        assert machine == expected, f"{label}: PE machine {machine:#x} != {expected:#x}"
    elif target.startswith("linux-"):
        assert header[:6] == b"\x7fELF\x02\x01", f"{label}: missing ELF64 LE header"
        machine = struct.unpack_from("<H", header, 18)[0]
        expected = {"linux-x64": 62, "linux-arm64": 183}[target]
        assert machine == expected, f"{label}: ELF machine {machine} != {expected}"
    else:
        assert header[:4] == b"\xcf\xfa\xed\xfe", f"{label}: missing Mach-O 64-bit magic"
        cputype = struct.unpack_from("<I", header, 4)[0]
        expected = 0x100000C if target.endswith("arm64") else 0x1000007
        assert cputype == expected, f"{label}: Mach-O cputype {cputype:#x} != {expected:#x}"


def verify_xulib_slices(data: bytes, expected_targets: tuple[str, ...], label: str) -> None:
    assert len(data) >= 19 and data[:7] == b"XULIB\x01\0", f"{label}: invalid XULIB header"
    pos = 15 + struct.unpack_from("<I", data, 11)[0]
    count, = struct.unpack_from("<I", data, pos)
    pos += 4
    assert 1 <= count <= 32, f"{label}: unexpected slice count {count}"
    found: set[str] = set()
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
        assert kind == b"archive" and len(raw) == size, f"{label}/{tname}: invalid slice record"
        assert hashlib.sha256(raw).digest() == digest, f"{label}/{tname}: slice SHA-256 mismatch"
        found.add(tname)
    assert set(expected_targets) <= found, f"{label}: missing slices {set(expected_targets) - found}; got {found}"


def read_archive_entries(archive_path: Path) -> tuple[dict[str, str], bytes | None, dict[str, bytes], dict[str, bytes]]:
    prefix_dir = None
    digests: dict[str, str] = {}
    bundle_raw: bytes | None = None
    bin_headers: dict[str, bytes] = {}
    xulibs: dict[str, bytes] = {}

    def handle(name: str, stream) -> None:
        nonlocal prefix_dir, bundle_raw
        parts = PurePosixPath(name).parts
        assert parts and ".." not in parts and "\\" not in name, f"Unsafe archive path: {name}"
        if prefix_dir is None:
            prefix_dir = parts[0] + "/"
        assert name.startswith(prefix_dir), f"Mixed root prefix in {name}"
        rel = name[len(prefix_dir):]
        assert rel not in digests, f"Duplicate entry {rel}"
        h = hashlib.sha256()
        data = stream.read()
        h.update(data)
        digests[rel] = h.hexdigest()
        if rel == "bundle.json":
            bundle_raw = data
        elif rel.startswith("bin/"):
            bin_headers[rel] = data[:4096]
        elif rel.startswith("native/") and rel.endswith(".xulib"):
            xulibs[rel] = data

    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            for entry in zf.infolist():
                if not entry.is_dir():
                    with zf.open(entry) as src:
                        handle(entry.filename, src)
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            for entry in tf.getmembers():
                if entry.isdir():
                    continue
                assert entry.isfile(), f"Non-regular file in archive: {entry.name}"
                with tf.extractfile(entry) as src:
                    handle(entry.name, src)
    return digests, bundle_raw, bin_headers, xulibs


def verify_target_archive(archive_path: Path, version: str, target: str) -> None:
    digests, bundle_raw, bin_headers, xulibs = read_archive_entries(archive_path)
    assert bundle_raw is not None, f"{archive_path.name}: missing bundle.json"
    meta = json.loads(bundle_raw)
    assert meta["version"] == version and meta["target"] == target
    assert set(digests) == set(meta["files"]) | {"bundle.json"}
    assert all(digests[k] == v for k, v in meta["files"].items())

    suffix = ".exe" if target.startswith("windows-") else ""
    expected_bins = {f"bin/{t}{suffix}" for _, t, _, _ in RELEASE_TOOLS}
    assert expected_bins <= set(bin_headers), f"{archive_path.name}: missing tools {expected_bins - set(bin_headers)}"
    for rel, hdr in bin_headers.items():
        verify_binary_header(hdr, target, f"{archive_path.name}:{rel}")

    expected_libs = {f"native/{lib}.xulib" for _, lib in NATIVE_LIBS}
    assert expected_libs <= set(xulibs), f"{archive_path.name}: missing xulibs {expected_libs - set(xulibs)}"
    for rel, raw in xulibs.items():
        verify_xulib_slices(raw, (target,), f"{archive_path.name}:{rel}")

    assert "shaders/canvas/format" in digests and "shaders/mesh/format" in digests
    print(f"release-verify: {target} tools, binary headers, shaders, and native slice PASS", flush=True)


def verify_native_all_archive(archive_path: Path, version: str, targets: tuple[str, ...]) -> None:
    digests, bundle_raw, _, xulibs = read_archive_entries(archive_path)
    assert bundle_raw is not None, f"{archive_path.name}: missing bundle.json"
    meta = json.loads(bundle_raw)
    assert meta["version"] == version and meta["target"] == "native-all"
    assert set(digests) == set(meta["files"]) | {"bundle.json"}
    assert all(digests[k] == v for k, v in meta["files"].items())
    expected_libs = {f"native/{lib}.xulib" for _, lib in NATIVE_LIBS}
    assert set(xulibs) == expected_libs, f"native-all libs mismatch: {set(xulibs)}"
    for rel, raw in xulibs.items():
        verify_xulib_slices(raw, targets, f"{archive_path.name}:{rel}")
    print(f"release-verify: native-all ({len(targets)} target slices across {len(xulibs)} xulibs) PASS", flush=True)


def verify_sha256sums(root: Path, expected_assets: list[str]) -> dict[str, dict[str, object]]:
    sums_path = root / "SHA256SUMS"
    assert sums_path.is_file(), "Missing SHA256SUMS"
    recorded: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        recorded[name.lstrip("*").strip()] = digest.lower()
    assert set(recorded) == set(expected_assets), f"SHA256SUMS set mismatch: {set(recorded)} != {set(expected_assets)}"

    allowed_meta = {"SHA256SUMS", "RELEASE_MANIFEST.md", "RELEASE_NOTES.md"}
    receipt_assets: dict[str, dict[str, object]] = {}
    for path in sorted(root.iterdir()):
        assert path.is_file() and not path.is_symlink(), f"Unexpected entry in release dir: {path}"
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", path.name), f"Unsafe asset name: {path.name}"
        digest = sha256_file(path)
        if path.name in recorded:
            assert recorded[path.name] == digest, f"SHA256SUMS mismatch for {path.name}"
        else:
            assert path.name in allowed_meta, f"Unlisted file in release dir: {path.name}"
        receipt_assets[path.name] = {"sha256": digest, "size": path.stat().st_size}
    assert set(receipt_assets) == set(expected_assets) | allowed_meta, (
        f"Release asset set mismatch: {set(receipt_assets)} != {set(expected_assets) | allowed_meta}"
    )
    return receipt_assets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Release directory containing staged archives")
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", default="")
    parser.add_argument("--receipt", type=Path, help="Output validation.json receipt path")
    parser.add_argument("--single-target", help="Verify only a single staged target archive (for local smoke)")
    args = parser.parse_args()

    root = args.root.resolve()
    version = args.version.removeprefix("v")
    tag = f"v{version}"

    if args.single_target:
        t = args.single_target
        ext = "zip" if t.startswith("windows-") else "tar.gz"
        archive = root / f"nexus-{tag}-{t}.{ext}"
        assert archive.is_file(), f"Missing staged archive {archive}"
        verify_target_archive(archive, version, t)
        return 0

    for t in DESKTOP_TARGETS:
        ext = "zip" if t.startswith("windows-") else "tar.gz"
        archive = root / f"nexus-{tag}-{t}.{ext}"
        assert archive.is_file(), f"Missing target archive {archive}"
        verify_target_archive(archive, version, t)

    native_all = root / f"nexus-{tag}-native-all.tar.gz"
    assert native_all.is_file(), f"Missing unified native archive {native_all}"
    verify_native_all_archive(native_all, version, DESKTOP_TARGETS)

    for doc in ("RELEASE_MANIFEST.md", "RELEASE_NOTES.md"):
        assert (root / doc).is_file() and (root / doc).stat().st_size > 0, f"Missing {doc}"

    assets_for_sums = [
        *[f"nexus-{tag}-{t}.{'zip' if t.startswith('windows-') else 'tar.gz'}" for t in DESKTOP_TARGETS],
        f"nexus-{tag}-native-all.tar.gz",
    ]
    receipt_assets = verify_sha256sums(root, assets_for_sums)

    if args.receipt:
        receipt = {
            "version": version,
            "tag": tag,
            "source_commit": args.commit,
            "targets": list(DESKTOP_TARGETS),
            "assets": receipt_assets,
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote release receipt {args.receipt} ({len(receipt_assets)} verified assets)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

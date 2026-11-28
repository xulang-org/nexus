#!/usr/bin/env python3
"""Verify single-source version identity across manifests, code constants, docs, and releases."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def parse_manifest(path: Path) -> tuple[str | None, str | None]:
    text = path.read_text(encoding="utf-8")
    ver_m = re.search(r"^version:\s*!ver\s+([^\s]+)$", text, re.MULTILINE)
    xu_m = re.search(r"^xu:\s*!ver\s+([^\s]+)$", text, re.MULTILINE)
    return (ver_m.group(1) if ver_m else None, xu_m.group(1) if xu_m else None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xu", help="Optional xu binary to verify with tools/check_sdk.py")
    parser.add_argument("--expected-tag", help="Require tag to equal v<root version>")
    parser.add_argument("--check-release", action="store_true", help="Require non-prerelease identity and RELEASES*.md entries")
    parser.add_argument(
        "--allow-prerelease",
        action="store_true",
        help="Allow -(dev|alpha|beta) prerelease versions when --check-release is passed",
    )
    args = parser.parse_args()

    errors: list[str] = []
    root_ver, root_xu = parse_manifest(ROOT / "xu.xun")
    if not root_ver or not root_xu:
        raise SystemExit("Root xu.xun must define both `version:` and `xu:`")

    if args.expected_tag and args.expected_tag != f"v{root_ver}":
        errors.append(f"Expected tag {args.expected_tag!r} does not match root xu.xun version 'v{root_ver}'")

    if args.check_release and not args.allow_prerelease and re.search(r"-(dev|alpha|beta)", root_ver):
        errors.append(
            f"Release identity check failed: version {root_ver!r} is a prerelease (pass --allow-prerelease to override)"
        )

    proj_text = (ROOT / "resources/project/mod.xu").read_text(encoding="utf-8")
    m_nv = re.search(r'pub const DEFAULT_NEXUS_VERSION = "([^"]+)"', proj_text)
    m_xv = re.search(r'pub const DEFAULT_XU_VERSION = "([^"]+)"', proj_text)
    if not m_nv or m_nv.group(1) != root_ver:
        errors.append(
            f"resources/project/mod.xu DEFAULT_NEXUS_VERSION ({m_nv.group(1) if m_nv else 'missing'}) != root xu.xun ({root_ver})"
        )
    if not m_xv or m_xv.group(1) != root_xu:
        errors.append(
            f"resources/project/mod.xu DEFAULT_XU_VERSION ({m_xv.group(1) if m_xv else 'missing'}) != root xu.xun ({root_xu})"
        )

    manifests = sorted(p for p in ROOT.rglob("xu.xun") if "build" not in p.relative_to(ROOT).parts)
    for manifest in manifests:
        _, m_xu = parse_manifest(manifest)
        rel = manifest.relative_to(ROOT).as_posix()
        if m_xu != root_xu:
            errors.append(f"{rel}: xu: {m_xu!r} != root xu.xun {root_xu!r}")

    iso_py = (ROOT / "tests/phone_isometric_checks.py").read_text(encoding="utf-8")
    if f"xu: !ver {root_xu}" not in iso_py:
        errors.append(f"tests/phone_isometric_checks.py missing 'xu: !ver {root_xu}'")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"当前开发版本 `{root_ver}`" not in readme and f"当前版本 `{root_ver}`" not in readme:
        errors.append(f"README.md missing current Nexus version badge `{root_ver}`")
    if f"Xu **{root_xu}**" not in readme:
        errors.append(f"README.md missing pinned Xu SDK `Xu **{root_xu}**`")
    for m_sdk in re.finditer(r"PASS: Xu SDK ([0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9.-]+)?)", readme):
        if m_sdk.group(1) != root_xu:
            errors.append(
                f"README.md has stale SDK output 'PASS: Xu SDK {m_sdk.group(1)}' != root xu.xun ({root_xu})"
            )

    if args.check_release:
        base_ver = root_ver.split("-", 1)[0]
        for rel_file in ("RELEASES.md", "RELEASES.zh-CN.md"):
            rel_path = ROOT / rel_file
            if not rel_path.is_file():
                errors.append(f"Missing release notes file: {rel_file}")
                continue
            rel_text = rel_path.read_text(encoding="utf-8")
            if f"## v{root_ver}" not in rel_text and f"## v{base_ver}" not in rel_text:
                errors.append(f"{rel_file} missing heading '## v{root_ver}' or '## v{base_ver}'")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if args.xu:
        subprocess.run([sys.executable, str(ROOT / "tools/check_sdk.py"), "--xu", args.xu], check=True)

    print(f"PASS: release identity verified ({len(manifests)} xu.xun manifests, nexus={root_ver}, xu={root_xu})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

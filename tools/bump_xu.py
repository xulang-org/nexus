#!/usr/bin/env python3
"""Update pinned Xu SDK version across xu.xun manifests, code constants, tests, and README.md."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$")


def apply_update(path: Path, updated: str, dry_run: bool, changed: list[str]) -> None:
    original = path.read_text(encoding="utf-8")
    if updated == original:
        return
    rel = path.relative_to(ROOT).as_posix()
    changed.append(rel)
    if not dry_run:
        path.write_text(updated, encoding="utf-8")


def bump_xu_version(version: str, dry_run: bool) -> list[str]:
    if not SEMVER_RE.fullmatch(version):
        raise SystemExit(f"Invalid Xu version {version!r}; expected X.Y.Z or X.Y.Z-prerelease")

    changed: list[str] = []

    manifests = sorted(p for p in ROOT.rglob("xu.xun") if "build" not in p.relative_to(ROOT).parts)
    for manifest in manifests:
        text = manifest.read_text(encoding="utf-8")
        updated, count = re.subn(r"^(xu:\s*!ver\s+)[^\s]+$", rf"\g<1>{version}", text, flags=re.MULTILINE)
        if count == 0:
            raise SystemExit(f"Manifest missing `xu: !ver ...`: {manifest.relative_to(ROOT)}")
        apply_update(manifest, updated, dry_run, changed)

    proj_path = ROOT / "resources/project/mod.xu"
    proj_text = proj_path.read_text(encoding="utf-8")
    proj_updated, count = re.subn(
        r'(pub const DEFAULT_XU_VERSION = ")[^"]+(")',
        rf"\g<1>{version}\g<2>",
        proj_text,
    )
    if count == 0:
        raise SystemExit("resources/project/mod.xu missing DEFAULT_XU_VERSION")
    apply_update(proj_path, proj_updated, dry_run, changed)

    iso_path = ROOT / "tests/phone_isometric_checks.py"
    iso_text = iso_path.read_text(encoding="utf-8")
    iso_updated, count = re.subn(
        r"(xu:\s*!ver\s+)[^\s\\'\"]+",
        rf"\g<1>{version}",
        iso_text,
    )
    if count == 0:
        raise SystemExit("tests/phone_isometric_checks.py missing `xu: !ver ...`")
    apply_update(iso_path, iso_updated, dry_run, changed)

    readme_path = ROOT / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    readme_updated = re.sub(
        r"Xu \*\*[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9.-]+)?\*\*",
        f"Xu **{version}**",
        readme_text,
    )
    readme_updated = re.sub(
        r"PASS: Xu SDK [0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9.-]+)?",
        f"PASS: Xu SDK {version}",
        readme_updated,
    )
    apply_update(readme_path, readme_updated, dry_run, changed)

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Target Xu SDK version (e.g. 0.14.4)")
    parser.add_argument("--dry-run", action="store_true", help="Print files that would change without modifying them")
    args = parser.parse_args()

    changed = bump_xu_version(args.version, args.dry_run)
    prefix = "[dry-run] " if args.dry_run else ""
    if changed:
        for rel in changed:
            print(f"{prefix}updated {rel}")
    else:
        print(f"{prefix}all files already at Xu {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

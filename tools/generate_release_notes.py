#!/usr/bin/env python3
"""Generate structured Nexus Engine release notes combining curated highlights, commits, and assets."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

CATEGORY_RULES = [
    (r"^(?:feat|feature)(?:\([^)]+\))?!?:", "Features"),
    (r"^fix(?:\([^)]+\))?!?:", "Bug Fixes"),
    (r"^perf(?:\([^)]+\))?!?:", "Performance"),
    (r"^refactor(?:\([^)]+\))?!?:", "Refactoring"),
    (r"^docs?(?:\([^)]+\))?!?:", "Documentation"),
    (r"^test(?:\([^)]+\))?!?:", "Tests"),
    (r"^(?:build|ci|chore)(?:\([^)]+\))?!?:", "Build & CI"),
]


def git(*args: str) -> str:
    res = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False)
    return res.stdout.strip()


def find_previous_tag(current_tag: str) -> str | None:
    ref = current_tag if git("rev-parse", "--verify", f"refs/tags/{current_tag}") else "HEAD"
    prev = git("describe", "--tags", "--abbrev=0", f"{ref}^")
    if prev and prev != current_tag:
        return prev
    for t in git("tag", "--sort=-creatordate").splitlines():
        t = t.strip()
        if t and t != current_tag:
            return t
    return None


def extract_curated_section(path: Path, tag: str) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    base_tag = "v" + tag.lstrip("v").split("-", 1)[0]
    for candidate in (tag, base_tag):
        pattern = re.compile(rf"^##\s+{re.escape(candidate)}\s*$(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


def collect_commits(prev_tag: str | None) -> dict[str, list[dict[str, str]]]:
    rev_range = f"{prev_tag}..HEAD" if prev_tag else "HEAD~30..HEAD"
    raw = git("log", rev_range, "--no-merges", "--pretty=format:%H|%h|%s")
    if not raw and prev_tag is None:
        raw = git("log", "--no-merges", "-n", "30", "--pretty=format:%H|%h|%s")
    grouped: dict[str, list[dict[str, str]]] = {}
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        full_hash, short_hash, subject = parts
        category = "Other Changes"
        clean = subject.strip()
        for pat, name in CATEGORY_RULES:
            m = re.match(pat, clean, re.IGNORECASE)
            if m:
                category = name
                clean = clean[m.end():].strip()
                break
        grouped.setdefault(category, []).append({"hash": full_hash, "short": short_hash, "subject": clean})
    return grouped


def read_xu_version() -> str:
    text = (ROOT / "xu.xun").read_text(encoding="utf-8")
    m = re.search(r"^xu:\s*!ver\s+([^\s]+)$", text, re.MULTILINE)
    return m.group(1) if m else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--prev-tag")
    parser.add_argument("--custom-notes", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    tag = args.tag
    prev_tag = args.prev_tag or find_previous_tag(tag)
    xu_ver = read_xu_version()
    commit_sha = git("rev-parse", "HEAD")

    sections: list[str] = [f"# Nexus Engine {tag}\n"]
    sections.append(f"- **Xu SDK**: `v{xu_ver}`")
    if commit_sha:
        sections.append(f"- **Source Commit**: `{commit_sha}`\n")

    if args.custom_notes and args.custom_notes.is_file():
        custom = args.custom_notes.read_text(encoding="utf-8").strip()
        if custom:
            sections.append("## Highlights\n\n" + custom + "\n")

    zh_section = extract_curated_section(ROOT / "RELEASES.zh-CN.md", tag)
    if zh_section:
        sections.append("## 发布说明\n\n" + zh_section + "\n")
    en_section = extract_curated_section(ROOT / "RELEASES.md", tag)
    if en_section:
        sections.append("## Release Notes\n\n" + en_section + "\n")

    if args.manifest and args.manifest.is_file():
        manifest_text = args.manifest.read_text(encoding="utf-8").strip()
        if manifest_text:
            sections.append(manifest_text + "\n")

    commits = collect_commits(prev_tag)
    if commits:
        sections.append("## Changelog\n")
        for _, cat_name in CATEGORY_RULES:
            entries = commits.get(cat_name, [])
            if entries:
                sections.append(f"### {cat_name}\n")
                for e in entries:
                    sections.append(f"- {e['subject']} (`{e['short']}`)")
                sections.append("")
        other = commits.get("Other Changes", [])
        if other:
            sections.append("### Other Changes\n")
            for e in other:
                sections.append(f"- {e['subject']} (`{e['short']}`)")
            sections.append("")

    rendered = "\n".join(sections).strip() + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

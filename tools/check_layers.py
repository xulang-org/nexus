#!/usr/bin/env python3
"""Check actual Xu package imports, ownership boundaries, and dependency cycles."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', 'build', 'tests', 'docs', 'native', '__pycache__'}
DECLARATION = re.compile(r'^\s*@(?:"([^"]+)"|([\w/-]+))\s*$', re.MULTILINE)
IMPORT = re.compile(r'^\s*(?:\w+\s+)?#(?:"([^"\n]+)"|([\w/-]+))\s*(?://[^\n]*)?$', re.MULTILINE)


@dataclass(frozen=True)
class Unit:
    path: str
    package: str
    imports: tuple[str, ...]


def read_units(root: Path) -> list[Unit]:
    units = []
    for path in sorted(root.rglob('*.xu')):
        relative = path.relative_to(root)
        if any(part in SKIP for part in relative.parts):
            continue
        source = path.read_text(encoding='utf-8')
        # Package/import directives are line-oriented in the selected Xu SDK.
        # Ignore complete comment lines so examples in comments cannot be edges.
        source = re.sub(r'^\s*//[^\n]*$', '', source, flags=re.MULTILINE)
        declaration = DECLARATION.search(source)
        package = (declaration[1] or declaration[2]) if declaration else ''
        imports = tuple(a or b for a, b in IMPORT.findall(source))
        units.append(Unit(relative.as_posix(), package, imports))
    return units


def application_rule(path: str, policy: dict) -> tuple[str, dict] | None:
    for prefix, rule in sorted(policy['applications'].items(), key=lambda item: -len(item[0])):
        if path.startswith(prefix + '/'):
            return '@' + path, rule
    return None


def audit(units: list[Unit], policy: dict) -> tuple[list[str], dict[str, set[str]]]:
    errors = []
    graph: dict[str, set[str]] = {}
    module = policy['module']
    seen = set()
    for package, rule in policy['packages'].items():
        if rule.get('layer') not in policy['layers']:
            errors.append(f'{package or "<root>"}: unknown architecture layer: {rule.get("layer")}')
    for unit in units:
        top = Path(unit.path).parts[0]
        if top in policy.get('reserved_roots', {}):
            errors.append(f'{unit.path}: reserved root: {policy["reserved_roots"][top]}')
        directory = Path(unit.path).parent.as_posix()
        local = '' if directory == '.' else directory
        application = application_rule(unit.path, policy)
        if application:
            key, rule = application
            expected = 'main'
        else:
            key = local
            rule = policy['packages'].get(local)
            expected = module + ('/' + local if local else '')
            seen.add(local)
            if rule is None:
                errors.append(f'{unit.path}: package has no architecture policy: {local}')
                continue
        if unit.package != expected:
            errors.append(f'{unit.path}: package declaration {unit.package!r} differs from {expected!r}')
        graph.setdefault(key, set())
        for imported in unit.imports:
            if imported == module or imported.startswith(module + '/'):
                target = imported[len(module):].lstrip('/')
                graph[key].add(target)
                if target not in policy['packages']:
                    errors.append(f'{unit.path}: unknown local dependency: {target}')
                if '*' not in rule['local'] and target not in rule['local']:
                    errors.append(f'{unit.path}: forbidden dependency: {key or "<root>"} -> {target or "<root>"}')
                if not application and target in policy['packages']:
                    source_layer = rule.get('layer')
                    target_layer = policy['packages'][target].get('layer')
                    if source_layer != target_layer and target_layer not in policy['layers'].get(source_layer, ()):
                        errors.append(f'{unit.path}: forbidden layer dependency: {source_layer} -> {target_layer}')
                if target == 'script/compiler' and not (rule.get('toolchain') or rule.get('layer') == 'toolchain'):
                    errors.append(f'{unit.path}: runtime/application cannot import script compiler')
            else:
                if imported not in rule['external']:
                    errors.append(f'{unit.path}: forbidden external import: {imported}')
                boundary = policy['native_modules'].get(imported)
                if boundary and key != boundary['owner']:
                    errors.append(f'{unit.path}: native {boundary["label"]} import must stay in {boundary["owner"]}')
                if imported.startswith('xu/') and rule.get('layer') != 'toolchain':
                    errors.append(f'{unit.path}: Xu frontend import belongs to toolchain')
    for source, targets in graph.items():
        for target in targets:
            if target not in seen:
                errors.append(f'{source or "<root>"}: missing source package: {target or "<root>"}')
    # Check every package, not just those reachable from one selected example.
    visited, active, stack = set(), set(), []

    def visit(package: str):
        if package in active:
            chain = stack[stack.index(package):] + [package]
            errors.append('dependency cycle: ' + ' -> '.join(p or '<root>' for p in chain))
            return
        if package in visited:
            return
        active.add(package)
        stack.append(package)
        for target in sorted(graph.get(package, ())):
            visit(target)
        stack.pop()
        active.remove(package)
        visited.add(package)

    for package in sorted(graph):
        visit(package)
    return errors, graph


def native_exports(root: Path, policy: dict) -> list[str]:
    errors = []
    for module, boundary in policy['native_modules'].items():
        manifest = json.loads((root / boundary['manifest']).read_text())
        expected = {item['name'] for item in manifest['exports']}
        source = (root / boundary['owner'] / 'mod.xu').read_text()
        actual = set(re.findall(r'^pub fn raw_(\w+)\(', source, re.MULTILINE))
        if manifest['module'] != module or actual != expected:
            errors.append(f'{boundary["owner"]}: transport exports differ from {module}: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
    return errors


def scene_constants(root: Path) -> list[str]:
    declaration = re.compile(r'^pub const ((?:NODE_|PROCESS_)\w+) = (\d+)\s*$', re.MULTILINE)
    data = dict(declaration.findall((root / 'resources/scene/mod.xu').read_text()))
    runtime = dict(declaration.findall((root / 'scene/scene_tree.xu').read_text()))
    errors = [f'scene data/runtime constant differs: {name}'
              for name, value in data.items() if runtime.get(name) != value]
    numeric = re.compile(r'^pub const (\w+) = (\d+)\s*$', re.MULTILINE)
    scene_audio = dict(numeric.findall((root / 'resources/scene/audio.xu').read_text()))
    mixer = dict(numeric.findall((root / 'audio/mixer/mod.xu').read_text()))
    for declared, actual in [('MAX_AUDIO_EMITTERS', 'MAX_VOICES'), ('MAX_AUDIO_BUSES', 'MAX_BUSES')]:
        if scene_audio.get(declared) != mixer.get(actual):
            errors.append(f'scene audio/mixer limit differs: {declared}')
    scene_script = dict(numeric.findall((root / 'resources/scene/scripts.xu').read_text()))
    host = dict(numeric.findall((root / 'script/host/scene_scripts.xu').read_text()))
    host.update(numeric.findall((root / 'script/host/signals.xu').read_text()))
    bytecode = dict(numeric.findall((root / 'script/bytecode/mod.xu').read_text()))
    for declared, actual, owner in [('MAX_SCENE_SCRIPTS', 'MAX_SCRIPTS', host), ('MAX_SCRIPT_CONNECTIONS', 'MAX_CONNECTIONS', host),
            ('MAX_SCRIPT_INITIALS', 'MAX_FIELDS', bytecode), ('MAX_SCRIPT_SCALAR', 'MAX_SCALAR', bytecode)]:
        if scene_script.get(declared) != owner.get(actual):
            errors.append(f'scene script/runtime limit differs: {declared}')
    return errors


def lighting_constants(root: Path) -> list[str]:
    data = (root / 'resources/lighting/mod.xu').read_text()
    shader = (root / 'rendering/three_d/shaders/lighting.inc').read_text()
    cpu = re.search(r'^pub const MAX_LIGHTS = (\d+)\s*$', data, re.MULTILINE)
    gpu = re.search(r'^#define XU_MAX_LIGHTS (\d+)\s*$', shader, re.MULTILINE)
    if not cpu or not gpu or cpu[1] != gpu[1]:
        return ['lighting data/shader constant differs: MAX_LIGHTS']
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', action='store_true', help='print concrete local package edges')
    args = parser.parse_args()
    policy = json.loads((ROOT / 'architecture.json').read_text())
    units = read_units(ROOT)
    errors, graph = audit(units, policy)
    errors += native_exports(ROOT, policy)
    errors += scene_constants(ROOT)
    errors += lighting_constants(ROOT)
    for name, reason in policy.get('reserved_roots', {}).items():
        if (ROOT / name).exists():
            errors.append(f'{name}: reserved root: {reason}')
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f'PASS: {len(units)} Xu source files, {len(policy["packages"])} packages; layer/package permissions, native/frontend ownership, declarations, mirrored constants, and acyclic imports')
    if args.graph:
        for source in sorted(graph):
            if source.startswith('@'):
                continue
            print((source or '<root>') + ' -> ' + ', '.join(t or '<root>' for t in sorted(graph[source])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

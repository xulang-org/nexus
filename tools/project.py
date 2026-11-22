#!/usr/bin/env python3
"""Import and publish a Nexus project with stable asset IDs."""

import argparse
from copy import deepcopy
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from build_script_scene import portable


PROJECT_FORMAT = "nexus.project"
MAX_SCENE = 4 * 1024**2
MAX_GLB = 16 * 1024**2
SHA256 = re.compile(r"[0-9a-f]{64}")
UID = re.compile(r"[0-9a-f]{32}")
SCENE_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}\.xuscene")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def read_bounded(path, maximum):
    if not path.is_file():
        raise ValueError(f"expected a regular file: {path}")
    with path.open("rb") as handle:
        data = handle.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"file exceeds {maximum} bytes: {path}")
    return data


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path, limit=MAX_SCENE):
    return json.loads(read_bounded(path, limit), object_pairs_hook=unique_keys)


def source_path(root, name):
    relative = portable(name)
    resolved = (root / relative).resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"source path leaves the project: {name}")
    return resolved


def atomic_write(path, data, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.close()
            if mode is not None:
                temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def project_config(path):
    config = read_json(path)
    if (not isinstance(config, dict) or set(config) != {"format", "version", "assets", "scenes"}
            or config["format"] != PROJECT_FORMAT or type(config["version"]) is not int
            or config["version"] != 1):
        raise ValueError("expected nexus.project version 1")
    assets, scenes = config["assets"], config["scenes"]
    if not isinstance(assets, dict) or not isinstance(scenes, dict) or not scenes:
        raise ValueError("project requires assets and a nonempty scenes table")
    if len(assets) > 4096 or len(scenes) > 256:
        raise ValueError("project asset or scene count exceeds budget")
    for uid, path in assets.items():
        if not UID.fullmatch(uid) or uid == "0" * 32 or portable(path).suffix.lower() != ".glb":
            raise ValueError(f"invalid GLB asset entry: {uid}")
    for name, path in scenes.items():
        if not SCENE_NAME.fullmatch(name) or not portable(path).name.endswith(".xuscene"):
            raise ValueError(f"invalid scene entry: {name}")
    unique_paths(assets.values(), "asset source paths")
    unique_paths(scenes, "output scene names")
    unique_paths(scenes.values(), "scene source paths")
    return config


def unique_paths(paths, label):
    folded = {path.casefold() for path in paths}
    if len(folded) != len(paths):
        raise ValueError(f"duplicate {label}")


def run_validator(validator, kind, path):
    check = subprocess.run([str(validator), kind, str(path)], capture_output=True, text=True)
    if check.returncode:
        raise ValueError(f"{kind} validation failed for {path.name}: {check.stderr.strip()}")
    return check.stdout.strip()


def check_glb_receipt(primitives):
    if not isinstance(primitives, list) or not 1 <= len(primitives) <= 1024:
        raise ValueError("GLB primitive count outside scene profile")
    for primitive in primitives:
        if (not isinstance(primitive, list) or len(primitive) != 5
                or any(type(item) is not int for item in primitive) or primitive[0] <= 0
                or any(flag not in (0, 1) for flag in primitive[1:])):
            raise ValueError("invalid GLB primitive validation receipt")


def import_glb(data, cache, validator, report):
    sha = digest(data)
    entry = cache / f"{sha}.glb"
    receipt = cache / f"{sha}.json"
    if receipt.exists():
        primitives = read_json(receipt, 32 * 1024)
        check_glb_receipt(primitives)
        if read_bounded(entry, MAX_GLB) != data:
            raise ValueError(f"immutable imported GLB has changed: {entry.name}")
    else:
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            candidate = Path(directory) / entry.name
            candidate.write_bytes(data)
            primitives = [list(map(int, line.split()))
                          for line in run_validator(validator, "glb", candidate).splitlines()]
            check_glb_receipt(primitives)
        atomic_write(entry, data, mode=0o444)
        atomic_write(receipt, encoded(primitives), mode=0o444)
        report["imported_assets"] += 1
    return sha, primitives, entry


def cook_scene(scene, assets, imported):
    if not isinstance(scene, dict) or not isinstance(scene.get("resources"), list):
        raise ValueError("scene requires a resources array")
    if len(scene["resources"]) > 32:
        raise ValueError("scene exceeds the 32-resource limit")
    dependencies = []
    source_bytes = 0
    for reference in scene["resources"]:
        if (not isinstance(reference, dict) or reference.get("type") != "glb_model"
                or not isinstance(reference.get("uid"), str) or reference["uid"] not in assets):
            raise ValueError("scene resources must be GLBs registered in the project")
        uid = reference["uid"]
        asset = imported(uid)
        dependencies.append(uid)
        source_bytes += asset["bytes"]
        reference.update(path=f"assets/{uid}.glb", sha256=asset["sha256"])
    if source_bytes > 32 * 1024**2:
        raise ValueError("scene exceeds the 32 MiB GLB source budget")
    return dependencies


def check_surface_bindings(scene, glbs):
    # The Xu validator has already checked the document structure and UID references.
    def primitive(item):
        table = glbs[item["resource"]]
        if item["primitive"] >= len(table):
            raise ValueError(f"primitive {item['primitive']} outside GLB {item['resource']}")
        return table[item["primitive"]]

    for surface in scene["surfaces"]:
        previous, _, _, needs_uvs, needs_tangents = primitive(surface)
        for item in surface.get("lod", {}).get("levels", []):
            triangles, has_uvs, has_tangents, _, _ = primitive(item)
            if triangles > previous:
                raise ValueError("coarser LOD must not increase triangle count")
            if (needs_uvs and not has_uvs) or (needs_tangents and not has_tangents):
                raise ValueError("LOD geometry does not support the base material")
            previous = triangles


def install_generation(output, generation, files):
    parent = output / "generations"
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / generation
    if not destination.exists():
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            stage = Path(temporary) / "generation"
            for relative, cached in files.items():
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(cached, target)
            try:
                stage.rename(destination)
            except OSError as error:
                if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                    raise
    for relative, cached in files.items():
        if not os.path.samefile(destination / relative, cached):
            limit = MAX_GLB if relative.endswith(".glb") else MAX_SCENE
            if read_bounded(destination / relative, limit) != read_bounded(cached, limit):
                raise ValueError(f"immutable output has changed: {relative}")


def publish(project, output, validator, *, scene_drafts=None):
    project = project.resolve(strict=True)
    validator = validator.resolve(strict=True)
    cache = output / "cache" / digest(read_bounded(validator, 64 * 1024**2))
    config = project_config(project)
    scenes = config["scenes"]
    if scene_drafts is not None:
        if not scene_drafts or set(scene_drafts) - scenes.keys():
            raise ValueError("viewport draft must address a project scene")
        scenes = {name: scenes[name] for name in scene_drafts}
    report = {"imported_assets": 0, "built_scenes": 0}
    assets = {}
    glbs = {}
    files = {}
    scene_ids = {}
    dependencies = {}

    def imported(uid):
        if uid not in assets:
            relative = config["assets"][uid]
            path = source_path(project.parent, relative)
            data = read_bounded(path, MAX_GLB)
            try:
                sha, primitives, cached = import_glb(data, cache, validator, report)
            except ValueError as error:
                raise ValueError(f"{relative}: {error}") from error
            glbs[uid] = primitives
            assets[uid] = {"source": relative, "sha256": sha, "primitives": len(primitives), "bytes": len(data)}
            files[f"assets/{uid}.glb"] = cached
        return assets[uid]

    for name, relative in sorted(scenes.items()):
        try:
            if scene_drafts is None:
                scene = read_json(source_path(project.parent, relative))
            else:
                scene = deepcopy(scene_drafts[name])
            dependencies[name] = cook_scene(scene, config["assets"], imported)
            data = encoded(scene)
            if len(data) > MAX_SCENE:
                raise ValueError("cooked scene exceeds 4 MiB")
            scene_id = digest(data)
            cached = cache / f"{scene_id}.xuscene"
            if cached.exists():
                if read_bounded(cached, MAX_SCENE) != data:
                    raise ValueError("immutable cooked scene has changed")
            else:
                cache.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=cache) as directory:
                    candidate = Path(directory) / name
                    candidate.write_bytes(data)
                    run_validator(validator, "scene", candidate)
                check_surface_bindings(scene, glbs)
                atomic_write(cached, data, mode=0o444)
                report["built_scenes"] += 1
            files[name] = cached
            scene_ids[name] = scene_id
        except ValueError as error:
            raise ValueError(f"{relative}: {error}") from error

    generation = digest(encoded(scene_ids))
    install_generation(output, generation, files)
    publication = {"generation": generation, "scenes": scene_ids,
                   "assets": assets, "dependencies": dependencies}
    pointer = output / "current.json"
    data = encoded(publication)
    if not pointer.exists() or read_bounded(pointer, MAX_SCENE) != data:
        atomic_write(pointer, data)
    return publication, report


def register(project, relative, uid):
    project = project.resolve(strict=True)
    config = project_config(project)
    source = source_path(project.parent, relative)
    if not source.is_file():
        raise ValueError(f"expected a regular source file: {relative}")
    if portable(relative).suffix.lower() != ".glb":
        raise ValueError("expected a .glb source")
    if uid is None:
        if len(config["assets"]) >= 4096:
            raise ValueError("project asset count exceeds budget")
        uid = uuid.uuid4().hex
        while uid in config["assets"]:
            uid = uuid.uuid4().hex
    elif uid not in config["assets"]:
        raise ValueError(f"unknown asset ID: {uid}")
    config["assets"][uid] = relative
    unique_paths(config["assets"].values(), "asset source paths")
    atomic_write(project, encoded(config), mode=project.stat().st_mode & 0o777)
    return uid


def published_scene(output, name):
    publication = read_json(output / "current.json")
    generation = publication["generation"]
    if not SCENE_NAME.fullmatch(name) or name not in publication["scenes"]:
        raise ValueError(f"scene is not published: {name}")
    if not SHA256.fullmatch(generation):
        raise ValueError("invalid published generation")
    return source_path(output, f"generations/{generation}/{name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("project", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--validator", type=Path, default=Path("build/nexus-project-validate"))
    locate = commands.add_parser("scene")
    locate.add_argument("name")
    locate.add_argument("--output", type=Path, required=True)
    for name in ("register", "relocate"):
        command = commands.add_parser(name)
        command.add_argument("project", type=Path)
        if name == "relocate":
            command.add_argument("uid")
        command.add_argument("source")
    args = parser.parse_args()
    try:
        if args.command == "build":
            publication, report = publish(args.project, args.output.resolve(), args.validator)
            print(encoded({**report, "generation": publication["generation"]}).decode().strip())
        elif args.command == "scene":
            print(published_scene(args.output.resolve(), args.name))
        else:
            print(register(args.project, args.source, getattr(args, "uid", None)))
    except (ValueError, OSError, RecursionError, KeyError, TypeError) as error:
        parser.exit(1, f"nexus project: {error}\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Exercise project imports with the actual Xu scene and GLB validators."""

import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/scene_assets/assets"
UID = "11001100110011001100110011001100"


def run(project, *args, valid=True):
    result = subprocess.run([sys.executable, str(ROOT / "tools/project.py"),
                             args[0], str(project), *map(str, args[1:])],
                            text=True, capture_output=True)
    if valid:
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    assert result.returncode != 0, result.stdout
    return result.stderr


def revised_glb(raw, edit):
    length = struct.unpack_from("<I", raw, 12)[0]
    document = json.loads(raw[20:20 + length])
    edit(document)
    content = json.dumps(document, separators=(",", ":")).encode()
    content += b" " * (-len(content) % 4)
    binary = raw[20 + length:]
    return struct.pack("<III", 0x46546c67, 2, 20 + len(content) + len(binary)) + (
        struct.pack("<I4s", len(content), b"JSON") + content + binary)


def recolor(document):
    document["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"] = [0.1, 0.9, 0.3, 1]


def remove_basis(document):
    attributes = document["meshes"][0]["primitives"][0]["attributes"]
    attributes.pop("TEXCOORD_0")
    attributes.pop("TANGENT")


def test(validator, preview):
    with tempfile.TemporaryDirectory(prefix="nexus-project-") as directory:
        project = Path(directory) / "project.json"
        root = project.parent
        output = root / "output"
        pointer = output / "current.json"
        source = root / "panels.glb"
        original = (SOURCE / "panels.glb").read_bytes()
        source.write_bytes(original)
        (root / "another.glb").write_bytes(original)
        authored = json.loads((SOURCE / "world.xuscene").read_bytes())
        (root / "atrium.xuscene").write_text(json.dumps(authored))
        authored["nodes"][0]["name"] = "Workshop"
        (root / "workshop.xuscene").write_text(json.dumps(authored))
        scenes = {name: name for name in ("atrium.xuscene", "workshop.xuscene")}
        project.write_text(json.dumps({"format": "nexus.project", "version": 1,
                                       "assets": {UID: source.name}, "scenes": scenes}))
        unrelated = run(project, "register", "another.glb")
        authored["resources"][0]["uid"] = unrelated
        for surface in authored["surfaces"]:
            surface["resource"] = unrelated
        (root / "outside.xuscene").write_text(json.dumps(authored))
        config = json.loads(project.read_bytes())
        config["scenes"]["outside.xuscene"] = "outside.xuscene"
        project.write_text(json.dumps(config))
        options = ("build", "--output", output, "--validator", validator)

        first = json.loads(run(project, *options))
        assert first["imported_assets"] == 1 and first["built_scenes"] == 3, first
        assert json.loads(run(project, *options)) == dict(first, imported_assets=0, built_scenes=0)
        before = output / "generations" / first["generation"]
        assert (before / "assets" / f"{UID}.glb").samefile(before / "assets" / f"{unrelated}.glb")

        relocated = root / "moved" / "shared.glb"
        relocated.parent.mkdir()
        source.rename(relocated)
        assert run(project, "relocate", UID, "moved/shared.glb") == UID
        assert json.loads(run(project, *options)) == dict(first, imported_assets=0, built_scenes=0)
        assert json.loads(pointer.read_bytes())["assets"][UID]["source"] == "moved/shared.glb"
        assert "outside.xuscene" not in [name for name, items in json.loads(pointer.read_bytes())[
            "dependencies"].items() if UID in items]

        updated = revised_glb(original, recolor)
        relocated.write_bytes(updated)
        second = json.loads(run(project, *options))
        assert second["imported_assets"] == 1 and second["built_scenes"] == 2, second
        after = output / "generations" / second["generation"]
        assert before != after
        assert (after / "outside.xuscene").samefile(before / "outside.xuscene")
        assert (after / "assets" / f"{unrelated}.glb").samefile(before / "assets" / f"{unrelated}.glb")
        assert (before / "assets" / f"{UID}.glb").read_bytes() == original
        assert (after / "assets" / f"{UID}.glb").read_bytes() == updated
        accepted = pointer.read_bytes()

        relocated.write_bytes(b"broken update")
        assert "glb validation failed" in run(project, *options, valid=False)
        assert pointer.read_bytes() == accepted
        relocated.write_bytes(updated)
        scene_path = root / "workshop.xuscene"
        valid_scene = scene_path.read_bytes()
        broken_scene = json.loads(valid_scene)
        broken_scene["surfaces"][-1]["primitive"] = 100
        scene_path.write_text(json.dumps(broken_scene))
        assert "primitive 100 outside GLB" in run(project, *options, valid=False)
        assert pointer.read_bytes() == accepted

        bad_lod = json.loads(valid_scene)
        bad_lod["version"] = 6
        bad_lod["resources"].append(dict(bad_lod["resources"][0], uid=unrelated))
        bad_lod["surfaces"][1]["lod"] = {"hysteresis": 0.125, "levels": [
            {"distance": 5, "resource": unrelated, "primitive": 0}]}
        (root / "another.glb").write_bytes(revised_glb(original, remove_basis))
        scene_path.write_text(json.dumps(bad_lod))
        assert "LOD geometry does not support the base material" in run(project, *options, valid=False)
        assert pointer.read_bytes() == accepted
        (root / "another.glb").write_bytes(original)
        scene_path.write_bytes(valid_scene)
        assert json.loads(run(project, *options)) == dict(second, imported_assets=0, built_scenes=0)

        if preview:
            for scene in (before / "atrium.xuscene", after / "atrium.xuscene",
                          after / "workshop.xuscene"):
                capture = root / f"{scene.parent.name}-{scene.name}.png"
                result = subprocess.run([str(preview), "--scene", str(scene),
                                         "--frames", "2", "--capture", str(capture)],
                                        cwd=ROOT, text=True, capture_output=True, check=True)
                assert "8 surfaces, 1 shared GLB model" in result.stdout, result.stdout
            captures = sorted(root.glob("*.png"))
            first_capture = root / f"{before.name}-atrium.xuscene.png"
            second_capture = root / f"{after.name}-atrium.xuscene.png"
            assert len(captures) == 3 and first_capture.read_bytes() != second_capture.read_bytes()
            print("PASS: real GPU renders the old and new project generations")

    print("PASS: project UID relocation, shared GLB, selective rebuild and rollback")


if __name__ == "__main__":
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--validator", type=Path, required=True)
    arguments.add_argument("--preview", type=Path)
    args = arguments.parse_args()
    test(args.validator.resolve(), args.preview.resolve() if args.preview else None)

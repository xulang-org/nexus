"""Render both camera types through the actual demos before and after scene save."""
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/scene-camera-gpu"
AUTHORING = ROOT / "examples/scene_file/assets/world.xuscene"
SAVED = OUTPUT / "saved.xuscene"


def render(demo, image, *args):
    path = OUTPUT / (image + ".png")
    subprocess.run(
        [str(OUTPUT / demo), "--frames", "1", "--capture", str(path), *map(str, args)],
        cwd=ROOT, check=True, timeout=30,
    )
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return data


def cameras(path):
    document = json.loads(path.read_text())
    assert document["version"] == 4
    return {node["name"]: node["camera"] for node in document["nodes"] if "camera" in node}


def main():
    authored_ortho = render(
        "scene-file", "ortho-authored", "--scene", AUTHORING, "--camera", "Ortho", "--cascades", 0, "--save", SAVED,
    )
    assert cameras(SAVED) == cameras(AUTHORING)
    restored_ortho = render("scene-file", "ortho-restored", "--scene", SAVED, "--camera", "Ortho", "--cascades", 0)
    perspective = render("scene-file", "perspective", "--scene", SAVED, "--camera", "Camera", "--cascades", 0)
    assert authored_ortho == restored_ortho
    assert restored_ortho != perspective

    ortho_cascades = render(
        "scene-file", "ortho-cascades", "--scene", AUTHORING, "--camera", "Ortho",
    )
    restored_cascades = render(
        "scene-file", "ortho-cascades-restored", "--scene", SAVED, "--camera", "Ortho",
    )
    assert ortho_cascades == restored_cascades
    authored = json.loads(AUTHORING.read_text())
    saved = json.loads(SAVED.read_text())
    assert saved["lights"][0]["cascades"] == authored["lights"][0]["cascades"]
    # Both runs have the same light, camera and geometry. Only the authored
    # shadow distance changes, so the distant preview wall is no longer shadowed.
    saved["lights"][0]["cascades"]["distance"] = 2
    short_file = OUTPUT / "short-shadow.xuscene"
    short_file.write_text(json.dumps(saved))
    short_cascades = render(
        "scene-file", "ortho-short-cascades", "--scene", short_file, "--camera", "Ortho",
    )
    assert short_cascades != restored_cascades

    authored_2d = render("two-d", "2d-authored", "--camera-scene", AUTHORING)
    restored_2d = render("two-d", "2d-restored", "--camera-scene", SAVED)
    default_2d = render("two-d", "2d-default")
    assert authored_2d == restored_2d
    assert restored_2d != default_2d
    print("PASS: authored CSM and 2D/3D cameras survive fresh-process Metal captures; editing saved shadow distance changes the rendered shadows")


if __name__ == "__main__":
    main()

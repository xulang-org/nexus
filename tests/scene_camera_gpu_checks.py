"""Render both camera types through the actual demos before and after scene save."""
from io import BytesIO
import json
from pathlib import Path
import subprocess

from PIL import Image


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


def check_punctual_shadow(kind):
    document = json.loads(AUTHORING.read_text())
    document["version"] = 5
    light = dict(node=document["lights"][0]["node"], type=kind, position=[0, 2, 5], radius=16,
                 radiance=[22, 20, 19], shadow=dict(near=.3, resolution=256, constant_bias=.00002, slope_bias=.00005))
    if kind == "spot":
        light.update(direction=[0, -.24, -1], inner_cosine=.9, outer_cosine=.65)
    document["lights"] = [light]
    scene = OUTPUT / f"{kind}-authored.xuscene"
    scene.write_text(json.dumps(document))
    restored = OUTPUT / f"{kind}-restored.xuscene"
    authored_png = render("scene-file", f"{kind}-authored", "--scene", scene, "--camera", "Ortho", "--save", restored)
    restored_png = render("scene-file", f"{kind}-restored", "--scene", restored, "--camera", "Ortho")
    assert authored_png == restored_png
    saved = json.loads(restored.read_text())
    assert saved["version"] == 5 and saved["lights"][0]["shadow"] == light["shadow"]

    # Keep lighting, caster geometry and receiver identical. Raising the depth
    # bias should brighten the pixels previously inside the punctual shadow.
    saved["lights"][0]["shadow"]["constant_bias"] = .05
    high_bias = OUTPUT / f"{kind}-high-bias.xuscene"
    high_bias.write_text(json.dumps(saved))
    adjusted_png = render("scene-file", f"{kind}-high-bias", "--scene", high_bias, "--camera", "Ortho")
    original_pixels = Image.open(BytesIO(restored_png)).convert("RGB").tobytes()
    adjusted_pixels = Image.open(BytesIO(adjusted_png)).convert("RGB").tobytes()
    brighter = sum(adjusted_pixels[i] - original_pixels[i] >= 8 for i in range(0, len(original_pixels), 3))
    assert brighter >= 512, (kind, brighter)
    print(f"PASS: {kind} shadow survives a fresh process, and the saved depth bias brightens {brighter} pixels")


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
    for kind in ("point", "spot"):
        check_punctual_shadow(kind)


if __name__ == "__main__":
    main()

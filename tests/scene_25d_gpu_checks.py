"""Exercise the 2.5D demo entry points and their rendered scene round trips."""
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def read_scene(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_scene(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def render(demo, scene, label, *args, frames=1):
    capture = scene.parent / f"{label}.png"
    subprocess.run(
        [str(BUILD / demo), "--scene", str(scene), "--frames", str(frames),
         "--capture", str(capture), *map(str, args)],
        cwd=ROOT, check=True, timeout=30,
    )
    with Image.open(capture) as image:
        return image.convert("RGB")


def changed_pixels(first, second):
    red, green, blue = ImageChops.difference(first, second).split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(maximum.histogram()[3:])


def check_pinned_atlas(demo, scene, attachments):
    document = read_scene(scene)
    source = document[attachments][-1]["resource"]
    reference = next(ref for ref in document["resources"] if ref["uid"] == source)
    alias = dict(reference, uid="0" * 31 + "1", path="mismatched.png")
    document["resources"].append(alias)
    document[attachments][-1]["resource"] = alias["uid"]
    (scene.parent / alias["path"]).write_bytes(b"modified atlas")
    bad = write_scene(scene.parent / "bad-hash.xuscene", document)
    result = subprocess.run(
        [str(BUILD / demo), "--scene", str(bad), "--frames", "1"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0 and "image content hash mismatch" in result.stderr, result.stderr


def check_isometric(scene):
    demo = "isometric-2d"
    saved = scene.parent / "saved.xuscene"
    authored = render(demo, scene, "behind", "--hero-y", 278, "--save", saved)
    assert authored.tobytes() == render(demo, saved, "restored").tobytes()
    document = read_scene(scene)
    restored = read_scene(saved)
    assert restored["version"] == 8 and restored["tilemaps_2d"] == document["tilemaps_2d"]
    assert restored["resources"] == document["resources"]

    hero = next(node for node in restored["nodes"] if node["name"] == "Hero")
    assert hero["transform"][-1] == 278
    front = deepcopy(restored)
    front["tilemaps_2d"][1]["y_offset"] = -80
    front_image = render(demo, write_scene(scene.parent / "front.xuscene", front), "front")
    hero["visible"] = False
    no_hero = render(demo, write_scene(scene.parent / "hidden.xuscene", restored), "hidden")
    behind_count = changed_pixels(authored, no_hero)
    front_count = changed_pixels(front_image, no_hero)
    assert behind_count > 100 and front_count > behind_count + 200, (behind_count, front_count)
    check_pinned_atlas(demo, scene, "tilemaps_2d")
    print(f"PASS: isometric v8 round trip, cross-atlas Y-sort ({behind_count}/{front_count} hero pixels), pinned tilesets")

    def walk(start, label, frames):
        output = scene.parent / f"{label}.xuscene"
        render(demo, start, label, "--autoplay", "--save", output, frames=frames)
        return output

    def hero_xy(path):
        return next(node["transform"][-2:] for node in read_scene(path)["nodes"] if node["name"] == "Hero")

    full = walk(scene, "walk-full", 12)
    first = walk(scene, "walk-first", 8)
    resumed = walk(first, "walk-resumed", 4)
    assert math.dist(hero_xy(resumed), hero_xy(full)) < 1e-7
    assert read_scene(resumed)["tilemaps_2d"][1]["solid_tiles"] == [2]

    document["version"] = 7
    for layer in document["tilemaps_2d"]:
        del layer["solid_tiles"]
    legacy = write_scene(scene.parent / "passable.xuscene", document)
    free = walk(legacy, "walk-free", 12)
    assert read_scene(free)["version"] == 7
    assert math.dist(hero_xy(free), [480, 252]) < 1e-7
    blocked_x, blocked_y = hero_xy(full)
    assert abs(blocked_x - 480) > 4 and 254 < blocked_y < 264, (blocked_x, blocked_y)
    print("PASS: isometric movement slides along the column, reload preserves the path, and legacy tiles remain passable")


def check_hd2d(scene):
    demo = "hd2d-scene"
    saved = scene.parent / "saved.xuscene"
    ortho = render(demo, scene, "ortho")
    perspective = render(demo, scene, "perspective", "--camera", "CameraPersp")
    assert changed_pixels(ortho, perspective) > 1000

    animated = render(demo, scene, "animated", "--flip-hero", "--save", saved, frames=12)
    assert changed_pixels(ortho, animated) > 100
    assert animated.tobytes() == render(demo, saved, "restored", frames=2).tobytes()
    document = read_scene(scene)
    restored = read_scene(saved)
    hero = next(sprite for sprite in restored["sprites_3d"] if sprite["node"] == 4)
    assert hero["flip_x"] and hero["region"] == [0.25, 0, 0.25, 1]
    assert restored["version"] == 7 and restored["resources"] == document["resources"]
    assert restored["lights"][0]["cascades"] == document["lights"][0]["cascades"]

    for sprite in document["sprites_3d"]:
        sprite["cast_shadow"] = False
    unshadowed = render(demo, write_scene(scene.parent / "no-sprite-shadows.xuscene", document), "no-sprite-shadows")
    shadow_pixels = changed_pixels(ortho, unshadowed)
    assert shadow_pixels > 1000, shadow_pixels
    check_pinned_atlas(demo, scene, "sprites_3d")
    print(f"PASS: HD-2D v7 round trip, two camera projections, atlas animation and flip, {shadow_pixels} sprite shadow pixels, pinned atlases")


def main():
    with TemporaryDirectory(prefix="scene-25d-", dir=BUILD) as directory:
        for example, check in [("isometric_2d", check_isometric), ("hd2d_scene", check_hd2d)]:
            assets = Path(directory) / example
            shutil.copytree(ROOT / "examples" / example / "assets", assets)
            check(assets / "world.xuscene")


if __name__ == "__main__":
    main()

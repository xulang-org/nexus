"""Load a staged v8 scene from outside the repository with the Phone layout."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_phone import ISOMETRIC_ASSETS, stage_isometric


def scene_pose(scene):
    nodes = {node['name']: node for node in scene['nodes']}
    return nodes['Hero']['transform'][-2:], nodes['Camera2D']['transform'][-2:]


def run_isometric(work, env, *args, frames=1):
    return subprocess.run(
        [str(ROOT / 'build/isometric-2d'), '--frames', str(frames), *map(str, args)],
        cwd=work, env=env, timeout=30, check=True, capture_output=True, text=True,
    )


def check_checkpoint(work, package, document, uninterrupted, env):
    data = work / 'phone-data'
    data.mkdir()
    env = env | {'XU_PHONE_DATA_ROOT': str(data)}
    save = data / 'isometric-v1.json'
    run_isometric(work, env, '--autoplay', frames=8)
    first = json.loads(save.read_bytes())
    assert first['hero'] != [480, 276]
    assert math.dist(first['camera'], [first['hero'][0], first['hero'][1] + 14]) < 1e-7
    run_isometric(work, env, '--autoplay', frames=4)
    resumed = json.loads(save.read_bytes())
    for pose, expected in zip((resumed['hero'], resumed['camera']), scene_pose(uninterrupted)):
        assert math.dist(pose, expected) < 1e-7, (pose, expected)

    paused = dict(resumed, paused=True)
    save.write_text(json.dumps(paused))
    run_isometric(work, env, '--autoplay', frames=4)
    assert json.loads(save.read_bytes()) == paused

    # This is the center of the solid column at cell (2, 2).
    save.write_text(json.dumps(dict(paused, hero=[480, 244])))
    result = run_isometric(work, env)
    assert 'initially overlapping collider' in result.stderr
    recovered = json.loads(save.read_bytes())
    assert (recovered['hero'], recovered['camera']) == scene_pose(document)
    assert not recovered['paused']

    # A new scene must use its own authored state, even at the same bundle ID.
    save.write_text(json.dumps(paused))
    new_scene = package / 'map/edited.xuscene'
    hero = next(node for node in document['nodes'] if node['name'] == 'Hero')
    hero['transform'][-2] += 8
    new_scene.write_text(json.dumps(document))
    run_isometric(work, env, '--scene', new_scene)
    edited = json.loads(save.read_bytes())
    assert edited['scene'] != paused['scene']
    assert (edited['hero'], edited['camera']) == scene_pose(document)
    assert not edited['paused']
    print('PASS: Isometric Phone checkpoint preserves collision path, camera and pause, rejects overlaps and changed scenes')


def main():
    with tempfile.TemporaryDirectory(prefix='nexus-isometric-phone-') as directory:
        work = Path(directory)
        check = work / 'touch-check'
        check.mkdir()
        (check / 'xu.xun').write_text('module: example/isometric_touch_check\nversion: !ver 0.1.0\nxu: !ver 0.14.4\n'
                                     f'require:\n  "github.com/xulang-org/nexus": file:{ROOT}\n')
        shutil.copyfile(ROOT / 'examples/isometric_2d/touch.xu', check / 'touch.xu')
        shutil.copyfile(ROOT / 'tests/phone_isometric_touch_checks.xu', check / 'main.xu')
        binary = work / 'touch-checks'
        subprocess.run([os.environ.get('XU', 'xu'), 'build', str(check), '-o', str(binary)],
                       cwd=ROOT, timeout=30, check=True)
        subprocess.run([str(binary)], cwd=work, timeout=10, check=True)

        source = work / 'source'
        (source / 'art').mkdir(parents=True)
        atlas = source / 'art/tiles.png'
        shutil.copyfile(ISOMETRIC_ASSETS / 'iso_tiles.png', atlas)
        document = json.loads((ISOMETRIC_ASSETS / 'world.xuscene').read_bytes())
        document['resources'][0]['path'] = 'art/tiles.png'
        scene = source / 'authored.xuscene'
        scene.write_text(json.dumps(document))
        package = work / 'phone-resources'
        resources = stage_isometric(scene, package)
        shutil.copytree(ROOT / 'build/canvas-shaders', package / 'canvas')
        assert all((package / name).is_file() for name in resources)
        assert (package / 'map/world.xuscene').read_bytes() == scene.read_bytes()

        capture = work / 'portrait.png'
        saved = package / 'map/saved.xuscene'
        env = os.environ | {'XU_PHONE_RESOURCE_ROOT': str(package)}
        env.pop('XU_PHONE_DATA_ROOT', None)
        run_isometric(work, env, '--autoplay', '--capture', capture, '--save', saved, frames=12)
        with Image.open(capture) as pixels:
            image = pixels.convert('RGB')
            width, height = image.size
            assert height > width
            assert image.getpixel((7, height - 7)) != image.getpixel((int(width * .18), int(height * .90)))
        restored = json.loads(saved.read_bytes())
        hero = next(node for node in restored['nodes'] if node['name'] == 'Hero')
        assert math.dist(hero['transform'][-2:], (480.0, 252.0)) > 4.0
        assert restored['version'] == 8 and restored['tilemaps_2d'][1]['solid_tiles'] == [2]
        assert restored['resources'][0]['path'] == 'art/tiles.png'
        check_checkpoint(work, package, document, restored, env)

        atlas.write_bytes(b'changed atlas')
        try:
            stage_isometric(scene, work / 'rejected')
        except ValueError as error:
            assert 'hash mismatch' in str(error)
        else:
            raise AssertionError('packager accepted an atlas with a different hash')
    print('PASS: Phone portrait HUD and pinned nested assets, v8 collision and save, and changed atlas rejection')


if __name__ == '__main__':
    main()

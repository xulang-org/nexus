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


def main():
    with tempfile.TemporaryDirectory(prefix='nexus-isometric-phone-') as directory:
        work = Path(directory)
        check = work / 'touch-check'
        check.mkdir()
        (check / 'xu.xun').write_text('module: example/isometric_touch_check\nversion: !ver 0.1.0\nxu: !ver 0.13.1\n'
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
        subprocess.run([str(ROOT / 'build/isometric-2d'), '--frames', '12', '--autoplay',
                        '--capture', str(capture), '--save', str(saved)], cwd=work,
                       env=os.environ | {'XU_PHONE_RESOURCE_ROOT': str(package)}, timeout=30, check=True)
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

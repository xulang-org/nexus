"""Run the packaged HD-2D example in its native Phone layout on the local GPU."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops
from scene_25d_gpu_checks import changed_pixels

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_phone import HD2D_ASSETS, stage_hd2d


def render(package, name, *args, frames=1, data_root=None):
    capture = package.parent / f'{name}.png'
    env = os.environ | {'XU_PHONE_RESOURCE_ROOT': str(package)}
    env.pop('XU_PHONE_DATA_ROOT', None)
    if data_root is not None:
        env['XU_PHONE_DATA_ROOT'] = str(data_root)
    result = subprocess.run(
        [str(ROOT / 'build/hd2d-scene'), '--frames', str(frames), '--capture', str(capture), *map(str, args)],
        cwd=package.parent, env=env,
        check=True, capture_output=True, text=True, timeout=30,
    )
    with Image.open(capture) as image:
        return image.convert('RGB'), result.stdout


def shadow_variant(document, package, name, enabled, opaque=False):
    variant = json.loads(json.dumps(document))
    for sprite in variant['sprites_3d']:
        sprite['cast_shadow'] &= enabled
        if opaque:
            sprite.update(alpha_mode='opaque', alpha_cutoff=0.0)
    scene = package / 'map' / f'{name}.xuscene'
    scene.write_text(json.dumps(variant))
    return render(package, name, '--scene', scene)[0]


def difference_mask(first, second):
    red, green, blue = ImageChops.difference(first, second).split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return maximum.point(lambda channel: 255 if channel >= 3 else 0)


def main():
    with tempfile.TemporaryDirectory(prefix='nexus-phone-hd2d-') as directory:
        package = Path(directory) / 'phone-resources'
        authored = HD2D_ASSETS / 'world.xuscene'
        entries = stage_hd2d(authored, package)
        shutil.copytree(ROOT / 'build/mesh-shaders', package / 'mesh')
        assert all((package / name).is_file() for name in entries)
        assert (package / 'map/world.xuscene').read_bytes() == authored.read_bytes()

        ortho, output = render(package, 'orthographic')
        layout = re.search(r'render=(\d+)x(\d+); present=(\d+)x(\d+); shadow=(\d+)', output)
        assert layout, output
        width, height, screen_w, screen_h, shadow = map(int, layout.groups())
        assert width * height <= 921600 and shadow == 256
        # Device3D.capture reads the bounded 3D target before upscaling and HUD composition.
        assert ortho.size == (width, height) and screen_h > screen_w
        if screen_w * screen_h > 921600:
            assert (width, height) != (screen_w, screen_h)

        perspective, _ = render(package, 'perspective', '--camera', 'CameraPersp')
        assert changed_pixels(ortho, perspective) > 5000
        saved = package / 'map/saved.xuscene'
        data_root = Path(directory) / 'phone-data'
        data_root.mkdir()
        walk, output = render(package, 'walk', '--autoplay', '--save', saved, frames=12, data_root=data_root)
        assert 'HD-2D perspective=true' in output and changed_pixels(perspective, walk) > 500
        document = json.loads(authored.read_bytes())
        restored = json.loads(saved.read_bytes())
        hero = next(node for node in restored['nodes'] if node['name'] == 'Hero')
        assert abs(hero['transform'][12] - .56) < 1e-6, hero['transform']
        assert [node.get('camera') for node in restored['nodes']] == [node.get('camera') for node in document['nodes']]
        assert restored['lights'][0]['cascades'] == document['lights'][0]['cascades']

        checkpoint_path = data_root / 'hd2d-v1.json'
        checkpoint = json.loads(checkpoint_path.read_bytes())
        assert checkpoint == {'version': 1, 'x': hero['transform'][12], 'z': 0.8,
                              'perspective': True, 'flip_x': False, 'paused': False}
        _, output = render(package, 'restarted', data_root=data_root)
        assert 'HD-2D restored: hero=0.560,0.800; perspective=true; flip_x=false; paused=false' in output
        assert json.loads(checkpoint_path.read_bytes()) == checkpoint
        checkpoint_path.write_text(json.dumps(dict(checkpoint, x=20)))
        recovered, _ = render(package, 'invalid-checkpoint', data_root=data_root)
        assert recovered.tobytes() == ortho.tobytes()
        assert json.loads(checkpoint_path.read_bytes())['x'] == 0

        no_cutouts = shadow_variant(document, package, 'no-cutout-shadows', False)
        opaque = shadow_variant(document, package, 'opaque-shadows', True, opaque=True)
        no_opaque = shadow_variant(document, package, 'no-opaque-shadows', False, opaque=True)
        # Opaque sprite quads also cover the floor in the main pass. Compare
        # shadows only on surfaces visible in both unshadowed images.
        shared_receivers = ImageChops.invert(difference_mask(no_cutouts, no_opaque))
        cutout_pixels = ImageChops.multiply(difference_mask(ortho, no_cutouts), shared_receivers).histogram()[255]
        opaque_pixels = ImageChops.multiply(difference_mask(opaque, no_opaque), shared_receivers).histogram()[255]
        assert cutout_pixels > 500 and opaque_pixels > cutout_pixels + 500, (cutout_pixels, opaque_pixels)
        print(f'PASS: Phone HD-2D two-finger movement/lens switch, {width}x{height} render at {screen_w}x{screen_h} present, '
              f'{shadow}px cascade tiles and {cutout_pixels}/{opaque_pixels} cutout/opaque shadow pixels')
        print('PASS: Phone HD-2D restores its private checkpoint and recovers from invalid state')


if __name__ == '__main__':
    main()

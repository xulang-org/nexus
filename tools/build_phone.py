#!/usr/bin/env python3
"""Build a self-contained Nexus Phone game project using the selected Xu SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from canvas_shaders import prepare
from mesh_shaders import prepare_mesh
from project import publish, published_scene

ROOT = Path(__file__).resolve().parents[1]
ISOMETRIC_ASSETS = ROOT / 'examples/isometric_2d/assets'
HD2D_ASSETS = ROOT / 'examples/hd2d_scene/assets'
CANVAS_FILES = ['canvas/format', 'canvas/canvas.vert.bin', 'canvas/canvas.frag.bin']
MESH_FILES = ['mesh/format', 'mesh/canvas.vert.bin', 'mesh/canvas.frag.bin',
              'mesh/mesh.vert.bin', 'mesh/mesh.frag.bin', 'mesh/shadow.vert.bin', 'mesh/shadow.frag.bin']
SCENE_EXAMPLES = ('isometric_2d', 'hd2d_scene')


def stage_atlas_scene(scene_path, stage, attachment, optional=(), *, name='world.xuscene', staged_assets=None):
    scene_path = scene_path.resolve()
    if scene_path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Phone scene exceeds the 4 MiB scene limit')
    raw_scene = scene_path.read_bytes()
    scene = json.loads(raw_scene)
    if (not isinstance(scene, dict) or scene.get('format') != 'xu.scene' or scene.get('version') not in (7, 8)
            or not scene.get(attachment)):
        raise ValueError(f'Phone scene needs version 7 or 8 and a nonempty {attachment} array')
    supported = (attachment, *optional)
    attachments = ('surfaces', 'audio_buses', 'audio_emitters', 'scripts', 'script_connections', 'lights', 'sprites_3d', 'tilemaps_2d')
    if any(scene.get(name) for name in attachments if name not in supported):
        raise ValueError(f'Phone scene accepts these attachments: {", ".join(supported)}')
    resources = [f'map/{name}']
    used_paths = {name.casefold()}
    if staged_assets is None:
        staged_assets = {}
    atlas_bytes = 0
    for reference in scene['resources']:
        relative = reference['path']
        if not isinstance(relative, str):
            raise ValueError('Phone atlas resource paths must be strings')
        parts = relative.split('/')
        if (reference['type'] != 'image_rgba' or relative.casefold() in used_paths or len(relative) > 236
                or any(part in ('', '.', '..') or not re.fullmatch(r'[A-Za-z0-9_.-]+', part) for part in parts)):
            raise ValueError(f'invalid Phone atlas resource path: {relative}')
        used_paths.add(relative.casefold())
        source = scene_path.parent.joinpath(*parts)
        atlas_bytes += source.stat().st_size
        if atlas_bytes > 32 * 1024 * 1024:
            raise ValueError('Phone atlases exceed the 32 MiB scene budget')
        image = source.read_bytes()
        if hashlib.sha256(image).hexdigest() != reference['sha256']:
            raise ValueError(f'Phone atlas hash mismatch: {relative}')
        if relative in staged_assets:
            if staged_assets[relative] != reference['sha256']:
                raise ValueError(f'conflicting Phone atlas path: {relative}')
            continue
        target = stage.joinpath('map', *parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image)
        staged_assets[relative] = reference['sha256']
        resources.append(f'map/{relative}')
    (stage / 'map').mkdir(exist_ok=True)
    (stage / 'map' / name).write_bytes(raw_scene)
    return resources


def stage_isometric(scene_path, stage):
    resources = stage_atlas_scene(scene_path, stage, 'tilemaps_2d')
    shutil.copyfile(ISOMETRIC_ASSETS / 'hero_iso.png', stage / 'hero_iso.png')
    return [*resources, 'hero_iso.png', *CANVAS_FILES]


def stage_hd2d(scene_path, stage):
    resources = stage_atlas_scene(scene_path, stage, 'sprites_3d', ('lights',))
    return [*resources, *MESH_FILES, 'mesh/ui_sdf.vert.bin', 'mesh/ui_sdf.frag.bin']


def stage_isometric_project(project, stage, entry, validator):
    with tempfile.TemporaryDirectory(prefix='nexus-phone-publish-') as directory:
        published = Path(directory).resolve()
        publication, _ = publish(project, published, validator)
        published_scene(published, entry)
        assets = {}
        resources = []
        for name in publication['scenes']:
            scene_path = published_scene(published, name)
            document = json.loads(scene_path.read_bytes())
            for node in document['nodes']:
                if node['parent'] == 0 and node['type'] == 'Node2D' and node['name'].startswith('Exit_'):
                    destination = node['name'][5:] + '.xuscene'
                    if destination not in publication['scenes']:
                        raise ValueError(f'{name} has an exit to an unpublished map: {destination}')
            resources.extend(stage_atlas_scene(scene_path, stage, 'tilemaps_2d', name=name, staged_assets=assets))
        (stage / 'map/campaign.entry').write_text(entry + '\n')
        shutil.copyfile(ISOMETRIC_ASSETS / 'hero_iso.png', stage / 'hero_iso.png')
        return [*resources, 'map/campaign.entry', 'hero_iso.png', *CANVAS_FILES]


def enable_android_activity_recreation(project):
    # Xu 0.13.1's Android template exits when SDL restarts its Activity.
    # Enable SDL's documented restart path and let Android finish the old Activity.
    app = project / 'App.c'
    activity = project / 'MainActivity.java'
    start = '    SDL_SetMainReady();\n'
    declaration = 'public final class MainActivity extends org.libsdl.app.SDLActivity {\n'
    native_source = app.read_text()
    java_source = activity.read_text()
    if native_source.count(start) != 1 or java_source.count(declaration) != 1:
        raise SystemExit('Xu Android game template changed; review the Activity recreation patch')
    app.write_text(native_source.replace(start, start + '''    if (!SDL_SetHint(SDL_HINT_ANDROID_ALLOW_RECREATE_ACTIVITY, "1")) {
        SDL_LogError(SDL_LOG_CATEGORY_APPLICATION, "SDL Activity recreation: %s", SDL_GetError());
        return (void *)1;
    }
'''))
    activity.write_text(java_source.replace(declaration, declaration + '''    @Override
    public void finish() {
        if (!isChangingConfigurations()) {
            super.finish();
        }
    }

'''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    parser.add_argument('--example', choices=('phone_arena', 'phone_3d', 'isometric_2d', 'hd2d_scene'), default='phone_arena')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--scene', type=Path, help='authored scene to package with isometric_2d or hd2d_scene')
    source.add_argument('--project', type=Path, help='publish and package an isometric project')
    parser.add_argument('--entry', default=None, help='published entry scene name for --project (default: world.xuscene)')
    parser.add_argument('--target', choices=('ios-arm64', 'android-arm64'), default='ios-arm64')
    parser.add_argument('--sdl-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle-id', default='org.xulang.nexus.probe')
    args = parser.parse_args()
    if args.scene and args.example not in SCENE_EXAMPLES:
        parser.error('--scene requires --example isometric_2d or hd2d_scene')
    if args.project and args.example != 'isometric_2d':
        parser.error('--project requires --example isometric_2d')
    if args.entry and not args.project:
        parser.error('--entry requires --project')
    if args.output.exists():
        raise SystemExit('Output already exists; choose a new project directory')
    xu = shutil.which(args.xu)
    if not xu:
        raise SystemExit('Xu SDK not found')
    subprocess.run(['python3', str(ROOT/'tools/check_sdk.py'), '--xu', xu], check=True)
    if args.project:
        subprocess.run(['make', 'project-validator', f'XU={xu}'], cwd=ROOT, check=True)
    subprocess.run(['python3', str(ROOT/'native/build.py'), '--xu', xu, '--only-image',
                    '--target', args.target, '--sdl-include', str(args.sdl_source.resolve()/'include')], check=True)
    if args.example == 'phone_arena':
        subprocess.run(['python3', str(ROOT/'native/build.py'), '--xu', xu, '--only-audio',
                        '--target', args.target, '--sdl-include', str(args.sdl_source.resolve()/'include')], check=True)
    slug = args.example.replace('_', '-')
    stage = ROOT/'build'/(f'{slug}-source-' + args.target)
    stage.mkdir(parents=True, exist_ok=True)
    for old in stage.glob('*.xu'):
        old.unlink()
    for source in (ROOT/'examples'/args.example).glob('*.xu'):
        shutil.copyfile(source, stage/source.name)
    shutil.copyfile(ROOT/'examples'/args.example/'xu.xun', stage/'xu.xun')
    backend = 'metal' if args.target == 'ios-arm64' else 'vulkan'
    if args.example != 'hd2d_scene':
        prepare(backend, stage/'canvas')
    if args.example == 'phone_arena':
        shutil.copyfile(ROOT/'examples/arena/assets/player.png', stage/'player.png')
        shutil.copyfile(ROOT/'examples/audio/assets/chime.wav', stage/'chime.wav')
        resources = ['player.png', 'chime.wav', *CANVAS_FILES]
    elif args.example in SCENE_EXAMPLES:
        try:
            if args.project:
                resources = stage_isometric_project(args.project, stage, args.entry or 'world.xuscene',
                    ROOT / 'build/nexus-project-validate')
            elif args.example == 'isometric_2d':
                resources = stage_isometric(args.scene or ISOMETRIC_ASSETS / 'world.xuscene', stage)
            else:
                resources = stage_hd2d(args.scene or HD2D_ASSETS / 'world.xuscene', stage)
                prepare_mesh(backend, stage/'mesh')
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SystemExit(f'Could not stage the Phone scene: {error}') from None
    else:
        shutil.copyfile(ROOT/'examples/arena/assets/player.png', stage/'player.png')
        prepare_mesh(backend, stage/'mesh')
        resources = ['player.png', *CANVAS_FILES, 'canvas/ui_sdf.vert.bin', 'canvas/ui_sdf.frag.bin',
                     'canvas/ui_text.frag.bin', *MESH_FILES]
    (stage/'phone.resources').write_text('\n'.join(resources) + '\n')
    env = dict(os.environ, XU_PHONE_SDL_SOURCE=str(args.sdl_source.resolve()))
    subprocess.run([xu, 'build', str(stage), '--target', args.target, '--phone-profile', 'game',
                    '--bundle-id', args.bundle_id, '-o', str(args.output.resolve())], env=env, check=True)
    if args.example in SCENE_EXAMPLES and args.target == 'android-arm64':
        enable_android_activity_recreation(args.output)

if __name__ == '__main__':
    main()

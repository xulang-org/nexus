#!/usr/bin/env python3
"""Build a self-contained Phone arena project using the selected Xu SDK."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from canvas_shaders import prepare

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    parser.add_argument('--example', choices=('phone_arena', 'phone_3d'), default='phone_arena')
    parser.add_argument('--target', choices=('ios-arm64', 'android-arm64'), default='ios-arm64')
    parser.add_argument('--sdl-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle-id', default='org.xulang.game.probe')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists; choose a new project directory')
    xu = shutil.which(args.xu)
    if not xu:
        raise SystemExit('Xu SDK not found')
    subprocess.run(['python3', str(ROOT/'tools/check_sdk.py'), '--xu', xu], check=True)
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
    if args.example == 'phone_arena':
        shutil.copyfile(ROOT/'examples/arena/assets/player.png', stage/'player.png')
        shutil.copyfile(ROOT/'examples/audio/assets/chime.wav', stage/'chime.wav')
        prepare(backend, stage/'canvas')
        (stage/'phone.resources').write_text('player.png\nchime.wav\ncanvas/format\ncanvas/canvas.vert.bin\ncanvas/canvas.frag.bin\n')
    else:
        shutil.copyfile(ROOT/'examples/arena/assets/player.png', stage/'player.png')
        prepare(backend, stage/'canvas')
        subprocess.run(['python3', str(ROOT/'tools/mesh_shaders.py'), '--backend', backend,
                        '--out-dir', str(stage/'mesh')], check=True)
        (stage/'phone.resources').write_text(
            'player.png\n'
            'canvas/format\ncanvas/canvas.vert.bin\ncanvas/canvas.frag.bin\n'
            'canvas/ui_sdf.vert.bin\ncanvas/ui_sdf.frag.bin\ncanvas/ui_text.frag.bin\n'
            'mesh/format\nmesh/canvas.vert.bin\nmesh/canvas.frag.bin\n'
            'mesh/mesh.vert.bin\nmesh/mesh.frag.bin\nmesh/shadow.vert.bin\nmesh/shadow.frag.bin\n'
        )
    env = dict(os.environ, XU_PHONE_SDL_SOURCE=str(args.sdl_source.resolve()))
    subprocess.run([xu, 'build', str(stage), '--target', args.target, '--phone-profile', 'game',
                    '--bundle-id', args.bundle_id, '-o', str(args.output.resolve())], env=env, check=True)

if __name__ == '__main__':
    main()

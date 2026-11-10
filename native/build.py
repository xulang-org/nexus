#!/usr/bin/env python3
"""Build the current host's Xu ABI bridge. SDL is loaded at runtime, never vendored."""
import argparse
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    parser.add_argument('--sdl-include', type=Path, help='directory containing SDL3/SDL.h')
    parser.add_argument('--cc', help='host clang executable')
    args = parser.parse_args()
    systems = {'Darwin': 'macos', 'Linux': 'linux', 'Windows': 'windows'}
    machines = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}
    try:
        target = systems[platform.system()] + '-' + machines[platform.machine()]
    except KeyError:
        raise SystemExit('supported hosts: macOS, Linux, Windows on arm64 or x64')
    executable = shutil.which(args.xu)
    if not executable:
        raise SystemExit('Xu product SDK not found; set XU or pass --xu')
    if args.sdl_include:
        flags = ['-I' + str(args.sdl_include.resolve())]
    else:
        subprocess.run(['pkg-config', '--atleast-version=3.4.0', 'sdl3'], check=True)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'sdl3'], text=True))
    with tempfile.TemporaryDirectory(prefix='xu-game-native-') as temporary:
        archive = Path(temporary) / 'game_gpu.a'
        package = Path(temporary) / 'game_gpu.xulib'
        command = [executable, 'native', 'compile', '--manifest', str(HERE / 'native.json'),
                   '--target', target, '-o', str(archive)]
        if args.cc:
            command += ['--cc', args.cc]
        subprocess.run(command + ['-O2', '-std=c11', '-Wall', '-Wextra', '-Werror', *flags, str(HERE / 'bridge.c')], check=True)
        subprocess.run([executable, 'native', 'pack', '--manifest', str(HERE / 'native.json'),
                        '--slice', target + '=' + str(archive), '-o', str(package)], check=True)
        destination = HERE / 'game_gpu.xulib'
        staged = destination.with_suffix('.xulib.tmp')
        shutil.copyfile(package, staged)
        staged.replace(destination)
    print('Built GPU bridge for ' + target)


if __name__ == '__main__':
    main()

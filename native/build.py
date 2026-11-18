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
import struct
import hashlib

HERE = Path(__file__).resolve().parent

def existing_slices(package, directory, replace):
    """Keep verified slices for other targets when adding one mobile/host slice."""
    if not package.exists():
        return []
    data = package.read_bytes()
    if data[:7] != b'XULIB\x01\0' or len(data) < 19:
        raise SystemExit('invalid existing native package: ' + str(package))
    pos = 15 + struct.unpack_from('<I', data, 11)[0]
    count, = struct.unpack_from('<I', data, pos)
    pos += 4
    if count > 32:
        raise SystemExit('native package slice count exceeds limit')
    result = []
    for i in range(count):
        length, = struct.unpack_from('<H', data, pos)
        pos += 2
        target = data[pos:pos+length].decode('ascii')
        pos += length
        kind_length = data[pos]
        pos += 1
        kind = data[pos:pos+kind_length]
        pos += kind_length
        offset, size = struct.unpack_from('<QQ', data, pos)
        pos += 16
        digest = data[pos:pos+32]
        pos += 32
        raw = data[offset:offset+size]
        if kind != b'archive' or len(raw) != size or hashlib.sha256(raw).digest() != digest:
            raise SystemExit('invalid native archive slice: ' + target)
        if target != replace:
            archive = directory / f'keep-{i}.a'
            archive.write_bytes(raw)
            result += ['--slice', target + '=' + str(archive)]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', default=os.environ.get('XU', 'xu'))
    parser.add_argument('--sdl-include', type=Path, help='directory containing SDL3/SDL.h')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--only-audio', action='store_true', help='build audio without GPU/shader tools')
    selection.add_argument('--only-image', action='store_true', help='build CPU PNG codec without GPU/audio/shaders')
    parser.add_argument('--cc', help='host clang executable')
    parser.add_argument('--target', choices=('ios-arm64', 'android-arm64'), help='add a Phone slice while preserving host slices')
    args = parser.parse_args()
    systems = {'Darwin': 'macos', 'Linux': 'linux', 'Windows': 'windows'}
    machines = {'arm64': 'arm64', 'ARM64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}
    try:
        target = systems[platform.system()] + '-' + machines[platform.machine()]
    except KeyError:
        raise SystemExit('supported hosts: macOS, Linux, Windows on arm64 or x64')
    target = args.target or target
    executable = shutil.which(args.xu)
    if not executable:
        raise SystemExit('Xu product SDK not found; set XU or pass --xu')
    if args.sdl_include:
        flags = ['-I' + str(args.sdl_include.resolve())]
    else:
        subprocess.run(['pkg-config', '--atleast-version=3.4.0', 'sdl3'], check=True)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'sdl3'], text=True))
    available = [('audio.json','audio.c','nexus_audio'),('image.json','image.c','nexus_image')]
    selected = 'nexus_audio' if args.only_audio else 'nexus_image' if args.only_image else None
    modules = [entry for entry in available if selected is None or entry[2] == selected]
    with tempfile.TemporaryDirectory(prefix='xu-nexus-native-') as temporary:
        for manifest, source, name in modules:
            archive = Path(temporary) / (name + '.a')
            package = Path(temporary) / (name + '.xulib')
            command = [executable, 'native', 'compile', '--manifest', str(HERE / manifest),
                       '--target', target, '-o', str(archive)]
            if args.cc:
                command += ['--cc', args.cc]
            subprocess.run(command + ['-O2', '-std=c11', '-Wall', '-Wextra', '-Werror',
                                      '-I' + temporary, *flags, str(HERE / source)], check=True)
            destination = HERE / (name + '.xulib')
            keep = existing_slices(destination, Path(temporary), target)
            subprocess.run([executable, 'native', 'pack', '--manifest', str(HERE / manifest),
                            *keep, '--slice', target + '=' + str(archive), '-o', str(package)], check=True)
            staged = destination.with_suffix('.xulib.tmp')
            shutil.copyfile(package, staged)
            staged.replace(destination)
            print('Built ' + name + ' bridge for ' + target)


if __name__ == '__main__':
    main()

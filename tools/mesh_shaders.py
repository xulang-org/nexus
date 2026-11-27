"""Prepare explicit 3D and presentation shaders without any nexus native module."""
import argparse
from pathlib import Path
import platform
import shutil
import subprocess
from canvas_shaders import prepare, vulkan_shader_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('metal', 'vulkan', 'd3d12'))
    parser.add_argument('--out-dir', type=Path, default=Path('build/mesh-shaders'))
    args = parser.parse_args()
    backend = args.backend or {'Darwin': 'metal', 'Windows': 'd3d12'}.get(platform.system(), 'vulkan')
    prepare_mesh(backend, args.out_dir)


STAGE_PROFILES = {
    'vert': 'vs_6_0',
    'frag': 'ps_6_0',
    'comp': 'cs_6_0',
}


def discover_shaders(source: Path):
    items = []
    for msl_path in sorted(source.glob('*.msl')):
        stem = msl_path.stem
        if '.' not in stem:
            continue
        stage = stem.rsplit('.', 1)[1]
        if stage in STAGE_PROFILES:
            items.append((stem, stage, STAGE_PROFILES[stage]))
    return items


def expand_includes(raw: bytes, source: Path) -> bytes:
    for include in ('lighting.inc', 'shadow.inc'):
        raw = raw.replace(f'#include "{include}"'.encode(), (source / include).read_bytes())
    return raw


def prepare_mesh(backend, out_dir):
    prepare(backend, out_dir)
    source = Path(__file__).resolve().parents[1] / 'rendering/three_d/shaders'
    if backend == 'd3d12':
        compiler = shutil.which('dxc')
        if not compiler:
            raise SystemExit('d3d12 shaders require DXC')
    elif backend == 'vulkan':
        vulkan = vulkan_shader_command()
    for shader, stage, profile in discover_shaders(source):
        output = out_dir / f'{shader}.bin'
        if backend == 'metal':
            data = expand_includes((source / f'{shader}.msl').read_bytes(), source)
            output.write_bytes(data)
        elif backend == 'd3d12':
            subprocess.run(
                [compiler, '-T', profile, '-E', 'main', '-Fo', str(output), str(source / f'{shader}.hlsl')],
                check=True,
            )
        else:
            subprocess.run([*vulkan, '-o', str(output), str(source / shader)], check=True)
    print(f'Prepared {backend} cross-backend 3D shader artifacts in {out_dir}')


if __name__ == '__main__':
    main()

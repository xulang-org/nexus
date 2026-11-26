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


def prepare_mesh(backend, out_dir):
    prepare(backend, out_dir)
    source = Path(__file__).resolve().parents[1] / 'rendering/three_d/shaders'
    if backend == 'd3d12':
        compiler = shutil.which('dxc')
    elif backend == 'vulkan':
        vulkan = vulkan_shader_command()
    for name in ('mesh', 'shadow'):
        for stage, profile in (('vert', 'vs_6_0'), ('frag', 'ps_6_0')):
            shader = f'{name}.{stage}'
            output = out_dir / f'{shader}.bin'
            if backend == 'metal':
                data = (source / f'{shader}.msl').read_bytes()
                for include in ('lighting.inc', 'shadow.inc'):
                    data = data.replace(f'#include "{include}"'.encode(), (source / include).read_bytes())
                output.write_bytes(data)
            elif backend == 'd3d12':
                subprocess.run(
                    [compiler, '-T', profile, '-E', 'main', '-Fo', str(output), str(source / f'{shader}.hlsl')],
                    check=True,
                )
            else:
                subprocess.run([*vulkan, '-o', str(output), str(source / shader)], check=True)
    if backend == 'metal':
        for comp in source.glob('*.msl'):
            if comp.stem.endswith('.comp') or comp.stem.endswith('.vert') or comp.stem.endswith('.frag'):
                name_key = comp.stem
                if name_key in ('mesh.vert', 'mesh.frag', 'shadow.vert', 'shadow.frag'):
                    continue
                data = comp.read_bytes()
                for include in ('lighting.inc', 'shadow.inc'):
                    data = data.replace(f'#include "{include}"'.encode(), (source / include).read_bytes())
                (out_dir / f'{name_key}.bin').write_bytes(data)
    print(f'Prepared {backend} mesh shader artifacts in {out_dir}')


if __name__ == '__main__':
    main()

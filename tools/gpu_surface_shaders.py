"""Prepare standalone GPU presentation example shaders without the game native bridge."""
import argparse
from pathlib import Path
import platform
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('metal', 'vulkan', 'd3d12'))
    parser.add_argument('--out-dir', type=Path, default=Path('build/gpu-surface-shaders'))
    args = parser.parse_args()
    backend = args.backend or {'Darwin': 'metal', 'Windows': 'd3d12'}.get(platform.system(), 'vulkan')
    source = Path(__file__).resolve().parents[1] / 'examples/gpu_surface/shaders'
    args.out_dir.mkdir(parents=True, exist_ok=True)
    compiler = None
    if backend != 'metal':
        compiler = shutil.which('dxc' if backend == 'd3d12' else 'glslangValidator')
        if not compiler:
            raise SystemExit(f'{backend} shaders require ' + ('DXC' if backend == 'd3d12' else 'glslangValidator'))
    for stage, profile in (('vert', 'vs_6_0'), ('frag', 'ps_6_0')):
        output = args.out_dir / f'triangle.{stage}.bin'
        if backend == 'metal':
            shutil.copyfile(source / f'triangle.{stage}.msl', output)
        elif backend == 'd3d12':
            subprocess.run([compiler, '-T', profile, '-E', 'main', '-Fo', str(output),
                            str(source / f'triangle.{stage}.hlsl')], check=True)
        else:
            subprocess.run([compiler, '-V', '-o', str(output), str(source / f'triangle.{stage}')], check=True)
    print(f'Prepared {backend} shader artifacts in {args.out_dir}')


if __name__ == '__main__':
    main()

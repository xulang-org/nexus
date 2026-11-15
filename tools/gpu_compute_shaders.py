"""Prepare standalone compute shader artifacts without the game native bridge."""
import argparse
from pathlib import Path
import platform
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('metal', 'vulkan', 'd3d12'))
    parser.add_argument('--out-dir', type=Path, default=Path('build/gpu-compute-shaders'))
    args = parser.parse_args()
    backend = args.backend or {'Darwin': 'metal', 'Windows': 'd3d12'}.get(platform.system(), 'vulkan')
    source = Path(__file__).resolve().parents[1] / 'examples/gpu_compute/shaders'
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / 'transform.comp.bin'
    if backend == 'metal':
        shutil.copyfile(source / 'transform.comp.msl', output)
    else:
        compiler = shutil.which('dxc' if backend == 'd3d12' else 'glslangValidator')
        if not compiler:
            raise SystemExit(f'{backend} shaders require ' + ('DXC' if backend == 'd3d12' else 'glslangValidator'))
        if backend == 'd3d12':
            subprocess.run([compiler, '-T', 'cs_6_0', '-E', 'main', '-Fo', str(output),
                            str(source / 'transform.comp.hlsl')], check=True)
        else:
            subprocess.run([compiler, '-V', '-o', str(output), str(source / 'transform.comp')], check=True)
    print(f'Prepared {backend} compute shader artifact in {args.out_dir}')


if __name__ == '__main__':
    main()

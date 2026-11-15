"""Prepare canvas shaders without the game native bridge."""
import argparse
from pathlib import Path
import platform
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('metal', 'vulkan', 'd3d12'))
    parser.add_argument('--out-dir', type=Path, default=Path('build/canvas-shaders'))
    args = parser.parse_args()
    backend = args.backend or {'Darwin': 'metal', 'Windows': 'd3d12'}.get(platform.system(), 'vulkan')
    prepare(backend,args.out_dir)


def prepare(backend, out_dir):
    source = Path(__file__).resolve().parents[1] / 'rendering/two_d/shaders'
    out_dir.mkdir(parents=True, exist_ok=True)
    compiler = None
    if backend != 'metal':
        compiler = shutil.which('dxc' if backend == 'd3d12' else 'glslangValidator')
        if not compiler:
            raise SystemExit(f'{backend} shaders require ' + ('DXC' if backend == 'd3d12' else 'glslangValidator'))
    targets = (
        ('canvas', 'vert', 'vs_6_0'),
        ('canvas', 'frag', 'ps_6_0'),
        ('ui_sdf', 'vert', 'vs_6_0'),
        ('ui_sdf', 'frag', 'ps_6_0'),
        ('ui_text', 'frag', 'ps_6_0'),
    )
    for name, stage, profile in targets:
        output = out_dir / f'{name}.{stage}.bin'
        if backend == 'metal':
            shutil.copyfile(source / f'{name}.{stage}.msl', output)
        elif backend == 'd3d12':
            subprocess.run([compiler, '-T', profile, '-E', 'main', '-Fo', str(output),
                            str(source / f'{name}.{stage}.hlsl')], check=True)
        else:
            subprocess.run([compiler, '-V', '-o', str(output), str(source / f'{name}.{stage}')], check=True)
    (out_dir / 'format').write_text({'metal':'msl','vulkan':'spirv','d3d12':'dxil'}[backend]+'\n')
    print(f'Prepared {backend} shader artifacts in {out_dir}')


if __name__ == '__main__':
    main()

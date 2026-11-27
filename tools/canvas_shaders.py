"""Prepare canvas shaders without the nexus native bridge."""
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


def vulkan_shader_command():
    glslang = shutil.which('glslangValidator')
    if glslang:
        return [glslang, '-V']
    glslc = shutil.which('glslc')
    if glslc:
        return [glslc]
    raise SystemExit('vulkan shaders require glslangValidator or glslc')


def prepare(backend, out_dir):
    source = Path(__file__).resolve().parents[1] / 'rendering/two_d/shaders'
    out_dir.mkdir(parents=True, exist_ok=True)
    if backend == 'd3d12':
        compiler = shutil.which('dxc')
        if not compiler:
            raise SystemExit('d3d12 shaders require DXC')
    elif backend == 'vulkan':
        vulkan = vulkan_shader_command()
    targets = (
        ('canvas', 'vert', 'vs_6_0'),
        ('canvas', 'frag', 'ps_6_0'),
        ('ui_sdf', 'vert', 'vs_6_0'),
        ('ui_sdf', 'frag', 'ps_6_0'),
        ('ui_text', 'frag', 'ps_6_0'),
        ('lighting_2d', 'frag', 'ps_6_0'),
    )
    for name, stage, profile in targets:
        output = out_dir / f'{name}.{stage}.bin'
        if backend == 'metal':
            shutil.copyfile(source / f'{name}.{stage}.msl', output)
        elif backend == 'd3d12':
            subprocess.run([compiler, '-T', profile, '-E', 'main', '-Fo', str(output),
                            str(source / f'{name}.{stage}.hlsl')], check=True)
        else:
            subprocess.run([*vulkan, '-o', str(output), str(source / f'{name}.{stage}')], check=True)
    (out_dir / 'format').write_text({'metal':'msl','vulkan':'spirv','d3d12':'dxil'}[backend]+'\n')
    print(f'Prepared {backend} shader artifacts in {out_dir}')


if __name__ == '__main__':
    main()

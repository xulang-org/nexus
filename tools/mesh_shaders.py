"""Prepare explicit 3D and presentation shaders without any nexus native module."""
import argparse
from pathlib import Path
import platform
import shutil
import subprocess
from canvas_shaders import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('metal','vulkan','d3d12'))
    parser.add_argument('--out-dir',type=Path,default=Path('build/mesh-shaders'))
    args = parser.parse_args()
    backend=args.backend or {'Darwin':'metal','Windows':'d3d12'}.get(platform.system(),'vulkan')
    prepare(backend,args.out_dir)
    source=Path(__file__).resolve().parents[1]/'rendering/three_d/shaders'
    for name in ('mesh','shadow'):
      for stage,profile in (('vert','vs_6_0'),('frag','ps_6_0')):
        output=args.out_dir/f'{name}.{stage}.bin'
        if backend=='metal':
            data=(source/f'{name}.{stage}.msl').read_bytes().replace(b'#include "lighting.inc"',(source/'lighting.inc').read_bytes()).replace(b'#include "shadow.inc"',(source/'shadow.inc').read_bytes())
            output.write_bytes(data)
        else:
            compiler=shutil.which('dxc' if backend=='d3d12' else 'glslangValidator')
            command=([compiler,'-T',profile,'-E','main','-Fo',str(output),str(source/f'{name}.{stage}.hlsl')]
                     if backend=='d3d12' else [compiler,'-V','-o',str(output),str(source/f'{name}.{stage}')])
            subprocess.run(command,check=True)
    print(f'Prepared {backend} mesh shader artifacts in {args.out_dir}')


if __name__=='__main__':
    main()

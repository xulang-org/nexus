"""Keep all CPU light descriptions and scene gathering independent of GPU/SDL."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu light data ') as directory:
    root=Path(directory)
    shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
    for package in ('foundation/math','resources/lighting','scene','integration/lighting'):
        shutil.copytree(ROOT/package,root/package)
    (root/'checks').mkdir()
    sdk=next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (root/'checks/xu.xun').write_text('module: example/light_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    shutil.copyfile(ROOT/'tests/lighting_checks.xu',root/'checks/main.xu')
    for absent in ('native','platform','rendering','assets','formats','script','internal'):
        assert not (root/absent).exists(),absent
    binary=root/'lights'
    env=os.environ | {'XU_NATIVE_CC':'/nonexistent/native-compiler','XU_SDL_LIBRARY':'/nonexistent/SDL','SDL_VIDEODRIVER':'nonexistent'}
    for level in ('--no-opt','--release'):
        subprocess.run([os.environ.get('XU','xu'),'build',str(root/'checks/main.xu'),level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
        subprocess.run([str(binary)],cwd=root,env=env,check=True,timeout=60)

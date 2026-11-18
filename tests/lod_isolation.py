"""Distance LOD is pure policy data, buildable without math vectors, scene or GPU."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu distance lod ') as directory:
    root=Path(directory)
    shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
    shutil.copytree(ROOT/'resources/lod',root/'resources/lod')
    checks=root/'checks';checks.mkdir()
    shutil.copyfile(ROOT/'tests/lod_checks.xu',checks/'main.xu')
    sdk=next(s for s in (ROOT/'xu.xun').read_text().splitlines() if s.startswith('xu:'))
    (checks/'xu.xun').write_text('module: example/lod_policy_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    for absent in ('foundation','scene','rendering','integration','platform','native','assets','audio','script'):
        assert not (root/absent).exists(),absent
    env=os.environ | {'XU_NATIVE_CC':'/nonexistent/compiler','XU_SDL_LIBRARY':'/nonexistent/SDL'}
    for level in ('--no-opt','--release'):
        binary=root/('lod'+level)
        subprocess.run([os.environ.get('XU','xu'),'build',str(checks/'main.xu'),level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
        subprocess.run([str(binary)],cwd=root,env=env,check=True,timeout=30)
print('PASS: --no-opt/--release LOD policy in isolation without vectors/scene/GPU/native dependencies')

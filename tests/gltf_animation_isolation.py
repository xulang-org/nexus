"""Pose, skin and byte decoding without scene, assets, GPU or native sources."""
from pathlib import Path
import os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu glTF animation isolation ') as name:
 root=Path(name);shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
 for package in ('foundation/math','formats/gltf'):shutil.copytree(ROOT/package,root/package)
 shutil.copyfile(ROOT/'tests/gltf_animation_checks.xu',root/'main.xu')
 shutil.copytree(ROOT/'build/gltf-animation-fixtures',root/'build/gltf-animation-fixtures')
 env=os.environ|{'XU_NATIVE_CC':'/nonexistent/compiler','XU_SDL_LIBRARY':'/nonexistent/SDL'}
 for level in ('--no-opt','--release'):
  binary=root/('checks'+level)
  subprocess.run([os.environ.get('XU','xu'),'build','main.xu',level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
  subprocess.run([str(binary)],cwd=root,env=env,check=True,timeout=60)
print('PASS: glTF pose/skin/URI --no-opt/--release isolation without scene/assets/rendering/native sources')

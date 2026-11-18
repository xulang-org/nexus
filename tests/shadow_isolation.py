from pathlib import Path
import os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu shadow data isolation ') as directory:
 root=Path(directory);shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
 for package in ('foundation/math','resources/shadow','resources/lighting'):shutil.copytree(ROOT/package,root/package)
 for source in ('shadow_core_checks.xu','cascade_core_checks.xu'):
  shutil.copyfile(ROOT/'tests'/source,root/'main.xu')
  for level in ('--no-opt','--release'):
   binary=root/('shadow'+level);env=os.environ|{'XU_NATIVE_CC':'/nonexistent/cc','XU_SDL_LIBRARY':'/nonexistent/SDL'}
   subprocess.run([os.environ.get('XU','xu'),'build','main.xu',level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
   subprocess.run([str(binary)],cwd=root,env=env,check=True,timeout=60)
print('PASS: shadow data --no-opt/--release without scene/GPU/rendering/files/native source')

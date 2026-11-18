"""Multi-format file/decoder contracts in a project without scene or GPU sources."""
from pathlib import Path
import os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu model format isolation ') as directory:
 root=Path(directory)
 shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
 for package in ('foundation/math','resources/mesh','formats/gltf','formats/obj','formats/stl','assets/mesh','internal/file_snapshot'):
  shutil.copytree(ROOT/package,root/package)
 checks=root/'checks';checks.mkdir();shutil.copyfile(ROOT/'tests/mesh_format_checks.xu',checks/'main.xu')
 sdk=next(s for s in (ROOT/'xu.xun').read_text().splitlines() if s.startswith('xu:'))
 (checks/'xu.xun').write_text('module: example/mesh_format_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
 for absent in ('scene','rendering','integration','native','platform','audio','script'):
  assert not (root/absent).exists(),absent
 env=os.environ | {'XU_NATIVE_CC':'/nonexistent/compiler','XU_SDL_LIBRARY':'/nonexistent/SDL'}
 for level in ('--no-opt','--release'):
  binary=root/('formats'+level)
  subprocess.run([os.environ.get('XU','xu'),'build',str(checks/'main.xu'),level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
  subprocess.run([str(binary),str(ROOT/'build/mesh-format-fixtures')],cwd=root,env=env,check=True,timeout=60)
print('PASS: --no-opt/--release cross-format import isolation without SceneTree/render/GPU/native source or runtime')

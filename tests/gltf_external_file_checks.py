"""External-image failure paths run before shaders/window/device creation."""
from pathlib import Path
import json,os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'build/gltf-animation-fixtures';binary=ROOT/'build/model-formats'
with tempfile.TemporaryDirectory(prefix='xu external image failures ') as name:
 root=Path(name);model=root/'external.glb';shutil.copyfile(SOURCE/'external.glb',model)
 textures=root/'Textures';textures.mkdir();png=textures/'map.png'
 def rejects():
  run=subprocess.run([str(binary),'--model',str(model),'--view','pbr','--frames','1','--shaders','/nonexistent/shaders'],cwd=ROOT,capture_output=True,text=True,timeout=30)
  assert run.returncode==1 and run.stderr and 'shader' not in run.stderr.lower(),run.stderr
 rejects() # Missing file.
 png.write_bytes(b'not a PNG signature');rejects()
 png.unlink();outside=root/'outside.png';shutil.copyfile(SOURCE/'Textures/map.png',outside);png.symlink_to(outside);rejects()
 png.unlink();textures.rmdir();textures.symlink_to(SOURCE/'Textures',target_is_directory=True);rejects()
print('PASS: missing/invalid external PNG and file/directory symlinks reject before GPU creation')

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-scene-builder-') as temporary:
 target=Path(temporary);project=target/'project';shutil.copytree(root/'examples/scene_scripts',project)
 output=target/'output/world.xuscene'
 command=[sys.executable,str(root/'tools/build_script_scene.py'),'--project',str(project/'project.json'),'--output',str(output),'--tool',str(root/'build/xu-nexus-script')]
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 before=output.read_bytes();scene=json.loads(before)
 resources={r['path']:hashlib.sha256((output.parent/r['path']).read_bytes()).hexdigest() for r in scene['resources']}
 (project/'indicator.xus').write_text('invalid syntax')
 failed=subprocess.run(command,cwd=root,capture_output=True,timeout=30)
 assert failed.returncode and output.read_bytes()==before
 for name,digest in resources.items():assert hashlib.sha256((output.parent/name).read_bytes()).hexdigest()==digest
 assert not list(output.parent.glob('.scene-candidate-*')) and not list(output.parent.glob('world.xuscene.tmp-*'))
 # Contract failures are rejected before staging a new resource generation.
 shutil.copyfile(root/'examples/scene_scripts/indicator.xus',project/'indicator.xus')
 manifest=json.loads((project/'project.json').read_text())
 template=project/manifest['template'];valid=json.loads(template.read_text())
 for label,mutate in [
  ('version',lambda d:d.update(version=2)),
  ('boolean-version',lambda d:d.update(version=True)),
  ('missing-array',lambda d:d.pop('surfaces')),
  ('missing-lights',lambda d:d.pop('lights')),
  ('lights-type',lambda d:d.update(lights={})),
  ('unknown-field',lambda d:d.update(unknown=[])),
  ('array-type',lambda d:d.update(scripts={}))]:
  d=json.loads(json.dumps(valid));mutate(d);template.write_text(json.dumps(d))
  failed=subprocess.run(command,cwd=root,capture_output=True,timeout=30)
  assert failed.returncode and output.read_bytes()==before,label
  assert not list(output.parent.glob('.scene-candidate-*')) and not list(output.parent.glob('world.xuscene.tmp-*'))
  for name,digest in resources.items():assert hashlib.sha256((output.parent/name).read_bytes()).hexdigest()==digest
print('PASS: immutable resource publication; compile and seven current-schema contract failures preserve the previous scene and every artifact')

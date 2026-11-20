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
  ('version',lambda d:d.update(version=5)),
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
 lens=dict(vertical_fov=.9,near=.2,far=100)
 camera_scene=json.loads(json.dumps(valid));camera_scene['version']=2
 camera=next(node for node in camera_scene['nodes'] if node['type']=='Node3D')
 camera['camera']=lens;template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==2 and published['nodes']==camera_scene['nodes']
 camera_scene['version']=3
 camera['camera']=dict(projection='orthographic',vertical_size=6,near=.2,far=100)
 template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==3 and published['nodes']==camera_scene['nodes']
 camera_scene['version']=4
 light=next(item for item in camera_scene['lights'] if item['type']=='directional')
 light['cascades']=dict(count=3,resolution=256,distance=32,split_lambda=.6,blend_fraction=.15,
                        caster_padding=3,stabilization_step=.0625,raster_bias_texels=.00390625)
 template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==4 and published['nodes']==camera_scene['nodes'] and published['lights']==camera_scene['lights']
print('PASS: immutable resource publication, authored cameras and cascade profiles, and failure rollback for compile and schema errors')

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
  ('version',lambda d:d.update(version=9)),
  ('missing-v7-arrays',lambda d:d.update(version=7)),
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
 camera_scene['version']=5
 light.clear()
 light.update(node=next(i for i,n in enumerate(camera_scene['nodes']) if n['type']=='Node3D'), type='point',
              position=[0, 0, 4], radiance=[4, 4, 4], radius=12,
              shadow=dict(near=.125,resolution=256,constant_bias=.00002,slope_bias=.00005))
 template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==5 and published['nodes']==camera_scene['nodes'] and published['lights']==camera_scene['lights']
 camera_scene['version']=6
 surface=camera_scene['surfaces'][0]
 surface['lod']=dict(hysteresis=.125,levels=[dict(distance=12.5,resource=surface['resource'],primitive=surface['primitive'])])
 template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==6 and published['surfaces']==camera_scene['surfaces'] and published['lights']==camera_scene['lights']
 hd_assets=root/'examples/hd2d_scene/assets'
 hd_scene=json.loads((hd_assets/'world.xuscene').read_bytes())
 sprite=dict(hd_scene['sprites_3d'][0],node=camera_scene['nodes'].index(camera))
 atlas=next(ref for ref in hd_scene['resources'] if ref['uid']==sprite['resource'])
 shutil.copyfile(hd_assets/atlas['path'],template.parent/atlas['path'])
 camera_scene.update(version=7,sprites_3d=[sprite],tilemaps_2d=[])
 camera_scene['resources'].append(atlas)
 template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==7 and published['sprites_3d']==[sprite] and published['tilemaps_2d']==[]
 image=next(ref for ref in published['resources'] if ref['uid']==atlas['uid'])
 assert hashlib.sha256((output.parent/image['path']).read_bytes()).hexdigest()==image['sha256']==atlas['sha256']
 iso_assets=root/'examples/isometric_2d/assets'
 iso_scene=json.loads((iso_assets/'world.xuscene').read_bytes())
 solid_layer=iso_scene['tilemaps_2d'][1]
 collision_node=dict(iso_scene['nodes'][solid_layer['node']],parent=0)
 tilemap=dict(solid_layer,node=len(camera_scene['nodes']))
 tileset=iso_scene['resources'][0]
 shutil.copyfile(iso_assets/tileset['path'],template.parent/tileset['path'])
 camera_scene['nodes'].append(collision_node)
 camera_scene['resources'].append(tileset)
 camera_scene.update(version=8,tilemaps_2d=[tilemap])
 template.write_text(json.dumps(camera_scene))
 subprocess.run(command,cwd=root,check=True,capture_output=True,timeout=30)
 published=json.loads(output.read_bytes())
 assert published['version']==8 and published['tilemaps_2d']==[tilemap]
 image=next(ref for ref in published['resources'] if ref['uid']==tileset['uid'])
 assert hashlib.sha256((output.parent/image['path']).read_bytes()).hexdigest()==image['sha256']==tileset['sha256']
print('PASS: immutable resource publication, cameras, shadows, LODs, sprite atlases, collision tilemaps, and failure rollback')

#!/usr/bin/env python3
"""Author current-schema surface scene and independent malformed resource fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct

root = Path(__file__).resolve().parents[1]
out = root / 'build/scene-asset-fixtures'
out.mkdir(parents=True, exist_ok=True)
(out/'deeper').mkdir(exist_ok=True)
(out/'deeper/keep.xuscene').write_text('keep old')
uid = '11001100110011001100110011001100'
uid2 = '22002200220022002200220022002200'
I = [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
def node(parent, name, kind='Node3D', pos=(0,0,0)):
    n = dict(parent=parent, name=name, type=kind, visible=True, process='inherit')
    if kind == 'Node3D': n['transform'] = I.copy(); n['transform'][12:15] = pos
    return n
def reference(path, data, identity=uid):
    return dict(uid=identity, type='glb_model', path=path, sha256=hashlib.sha256(data).hexdigest())
def scene(nodes, refs, surfaces): return dict(format='xu.scene', version=1, nodes=nodes, resources=refs, surfaces=surfaces,audio_buses=[],audio_emitters=[],scripts=[],script_connections=[],lights=[])
def write(name, data): (out / name).write_text(json.dumps(data, ensure_ascii=False, separators=(',',':'))+'\n')
base_bytes = (root / 'build/glb-material-fixtures/base.glb').read_bytes()
(out / 'base.glb').write_bytes(base_bytes)
base = scene([node(-1,'World'),node(0,'Panel')], [reference('base.glb', base_bytes)], [dict(node=1,resource=uid,primitive=0)])
write('base.xuscene', base)
# Same verified bytes at distinct paths/identities share one GPU source model.
(out / 'alias.glb').write_bytes(base_bytes)
alias = copy.deepcopy(base); alias['nodes'].append(node(0,'Second'))
alias['resources'].append(reference('alias.glb',base_bytes,uid2));alias['surfaces'].append(dict(node=2,resource=uid2,primitive=0))
write('sharing.xuscene',alias)
for name, path in [('missing','absent.glb'),('hash','alias.glb')]:
    value=copy.deepcopy(base);value['resources'][0]['path']=path
    if name=='hash':value['resources'][0]['sha256']='0'*64
    write(name+'.xuscene',value)
# Second-source errors must release the first source already uploaded.
for name, source in [('bad-png','broken-png.glb'),('bad-basis','no-normal.glb')]:
    data=(root/'build/glb-material-fixtures'/source).read_bytes();(out/source).write_bytes(data)
    value=copy.deepcopy(alias);value['resources'][1]=reference(source,data,uid2)
    write(name+'.xuscene',value)
value=copy.deepcopy(alias);value['resources'][1]['sha256']='0'*64;write('late-hash.xuscene',value)
value=copy.deepcopy(base);value['surfaces'][0]['primitive']=1;write('actual-primitive.xuscene',value)
# Valid GLB unknown tail chunks count toward the aggregate source-read budget.
large_resources=[]
for i in range(3):
    size=12*1024*1024
    raw=bytearray(base_bytes)+struct.pack('<I4s',size-len(base_bytes)-8,b'TEST')+bytes([i])*(size-len(base_bytes)-8)
    struct.pack_into('<I',raw,8,len(raw))
    name=f'large-{i}.glb';(out/name).write_bytes(raw)
    large_resources.append(reference(name,raw,(str(i+1)+'1')*16))
large=scene([node(-1,'Root')]+[node(0,f'n{i}') for i in range(3)],large_resources,
    [dict(node=i+1,resource=r['uid'],primitive=0) for i,r in enumerate(large_resources)])
write('source-budget.xuscene',large)
original=(root/'examples/glb_materials/assets/panels.glb').read_bytes()
source_assets=root/'examples/scene_assets/assets';source_assets.mkdir(parents=True,exist_ok=True)
if (source_assets/'panels.glb').exists(): assert (source_assets/'panels.glb').read_bytes()==original
else: (source_assets/'panels.glb').write_bytes(original)
nodes=[node(-1,'Gallery')]
for i,name in enumerate(['Factor','Color','MR','MR_AO','Normal','Emission','Five_maps','Back_face']):
    n=node(0,name,pos=((i%4-1.5)*2.1,1.05 if i<4 else -1.05,0))
    if i==7: n['transform'][0]=-1;n['transform'][10]=-1
    nodes.append(n)
nodes.append(node(0,'Camera',pos=(0,0,9.5)))
original_scene=scene(nodes,[reference('panels.glb',original)],[dict(node=i+1,resource=uid,primitive=i) for i in range(8)])
raw=json.dumps(original_scene,ensure_ascii=False,indent=2)+'\n'
path=source_assets/'world.xuscene'
if path.exists():assert path.read_text()==raw
else:path.write_text(raw)
# A fresh-process save/load sample keeps scene and resources in the same folder.
demo=root/'build/scene-assets';demo.mkdir(exist_ok=True)
shutil.copyfile(source_assets/'panels.glb',demo/'panels.glb');shutil.copyfile(path,demo/'world.xuscene')
rejects=[]
def bad(name, mutate):
    value=copy.deepcopy(base);mutate(value);write(name+'.xuscene',value);rejects.append(name+'.xuscene')
def rprop(key,value):return lambda d:d['resources'][0].__setitem__(key,value)
def sprop(key,value):return lambda d:d['surfaces'][0].__setitem__(key,value)
for key in ['resources','surfaces']:
    bad('missing-'+key,lambda d,k=key:d.pop(k))
    for label,value in [('empty',[]),('null',None),('object',{}),('scalar',1)]:bad(key+'-'+label,lambda d,k=key,v=value:d.__setitem__(k,v))
for label,value in [('short','a'),('upper','A'*32),('zero','0'*32),('nonhex','g'*32),('number',1),('null',None)]:bad('uid-'+label,rprop('uid',value))
for label,value in [('short','a'),('upper','A'*64),('nonhex','g'*64),('null',None)]:bad('hash-'+label,rprop('sha256',value))
for label,value in [('empty',''),('absolute','/base.glb'),('drive','C:/base.glb'),('backslash','a\\base.glb'),('parent','../base.glb'),('dot','a/./base.glb'),('empty-segment','a//base.glb'),('trailing','base.glb/'),('control','x\n.glb'),('long','x'*1025)]:bad('path-'+label,rprop('path',value))
bad('kind',rprop('type','wav'));bad('resource-extra',rprop('options',{}));bad('resource-missing',lambda d:d['resources'][0].pop('uid'))
bad('duplicate-uid',lambda d:d['resources'].append(reference('alias.glb',base_bytes)))
bad('duplicate-path',lambda d:d['resources'].append(reference('base.glb',base_bytes,uid2)))
bad('unused-resource',lambda d:d['resources'].append(reference('alias.glb',base_bytes,uid2)))
for label,value in [('negative',-1),('outside',2),('float',1.5),('null',None)]:bad('node-'+label,sprop('node',value))
bad('non-3d-node',lambda d:d['nodes'].__setitem__(1,node(0,'Group','Node')))
bad('unknown-resource',sprop('resource',uid2));bad('surface-null',lambda d:d['surfaces'].__setitem__(0,None))
bad('duplicate-surface',lambda d:d['surfaces'].append(copy.deepcopy(d['surfaces'][0])))
for label,value in [('negative',-1),('outside',1024),('float',.5),('null',None)]:bad('primitive-'+label,sprop('primitive',value))
bad('surface-extra',sprop('material',1));bad('surface-missing',lambda d:d['surfaces'][0].pop('node'))
bad('version-future',lambda d:d.__setitem__('version',5))
bad('unsupported-version',lambda d:d.__setitem__('version',5))
bad('too-many-resources',lambda d:d.__setitem__('resources',d['resources']*33))
bad('too-many-surfaces',lambda d:d.__setitem__('surfaces',d['surfaces']*4097))
(out/'reject-list.txt').write_text('\n'.join(rejects)+'\n')
print(f'Scene resource fixtures: {len(rejects)} strict rejects; original 10-node/8-surface pinned PBR gallery')

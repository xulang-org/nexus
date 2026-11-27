#!/usr/bin/env python3
"""Independent current-schema corpus and deterministic bytecode revision candidates."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[1];out=root/'build/scene-script-fixtures';out.mkdir(exist_ok=True)
tool=root/'build/xu-nexus-script';project=root/'examples/scene_scripts'
u1='55005500550055005500550055005500';u2='66006600660066006600660066006600';u3='77007700770077007700770077007700'
world=json.loads((root/'build/scene-scripts/world.xuscene').read_text())
for r in world['resources']:
 if r['type']=='xu_bytecode':shutil.copyfile(root/'build/scene-scripts'/r['path'],out/('mover.xubc' if r['uid']==u1 else 'indicator.xubc'))
source=(project/'mover.xus').read_text();schema=json.loads((project/'mover.schema.json').read_text())
def compile(name,text,metadata):
 src=out/(name+'.xus');meta=out/(name+'.schema.json');src.write_text(text);meta.write_text(json.dumps(metadata))
 subprocess.run([str(tool),'build',str(src),str(meta),str(out/(name+'.xubc'))],check=True,stdout=subprocess.DEVNULL)
next_source=source.replace('axis * self.speed * delta','axis * self.speed * delta * 2.0').replace('ticks','steps').replace('"moved"','"advanced"')
next_schema=copy.deepcopy(schema);next_schema['fields'][0]['name']='steps';next_schema['signals'][0]['name']='advanced'
compile('next',next_source,next_schema)
drop_source=source.replace('    pub speed f64\n','').replace('self.speed','1.0');drop_schema=copy.deepcopy(schema);drop_schema['fields']=drop_schema['fields'][:2]
compile('drop-field',drop_source,drop_schema)
drop_signal=copy.deepcopy(schema);drop_signal['signals']=[];compile('drop-signal',source.replace('    emit_signal("moved", movement)\n',''),drop_signal)
wrong_class=copy.deepcopy(schema);wrong_class['class']='Other';compile('wrong-class',source.replace('Mover','Other'),wrong_class)
compile('runtime-fail',source.replace('<< movement','<< 1.0 / delta'),schema)
indicator=(project/'indicator.xus').read_text();indicator_schema=json.loads((project/'indicator.schema.json').read_text());indicator_schema['handlers'][0]['name']='on_advanced';compile('indicator-next',indicator.replace('on_moved','on_advanced'),indicator_schema)
raw=(out/'mover.xubc').read_bytes();(out/'alias.xubc').write_bytes(raw);(out/'broken.xubc').write_text('broken');(out/'oversized.xubc').write_bytes(b'x'*131073)
def node(parent,name,kind='Node'):return dict(parent=parent,name=name,type=kind,visible=True,process='inherit')
def ref(name,key):return dict(uid=key,type='xu_bytecode',path=name,sha256=hashlib.sha256((out/name).read_bytes()).hexdigest())
def attachment(index,key,value):return dict(node=index,resource=key,initial=[dict(id=3,value=value)])
base=dict(format='xu.scene',version=1,nodes=[node(-1,'World'),node(0,'Mover'),node(0,'Receiver')],resources=[ref('mover.xubc',u1),ref('indicator.xubc',u2)],surfaces=[],audio_buses=[],audio_emitters=[],scripts=[attachment(1,u1,.9),attachment(2,u2,5)],script_connections=[dict(source=1,signal=1,target=2,handler=1)])
base['lights']=[]
def write(name,value):(out/(name+'.xuscene')).write_text(json.dumps(value,separators=(',',':'))+'\n')
write('base',base)
for name,mutate in [('bad-field',lambda d:d['scripts'][0]['initial'][0].update(id=99)),('bad-signal',lambda d:d['script_connections'][0].update(signal=99)),('bad-handler',lambda d:d['script_connections'][0].update(handler=99)),('hash',lambda d:d['resources'][0].update(sha256='0'*64)),('missing',lambda d:d['resources'][0].update(path='absent.xubc')),('broken',lambda d:d['resources'].__setitem__(0,ref('broken.xubc',u1))),('oversized',lambda d:d['resources'].__setitem__(0,ref('oversized.xubc',u1)))]:
 d=copy.deepcopy(base);mutate(d);write(name,d)
# Two independent VM states share one resource; alias identities can diverge later.
for name,key in [('batch',u1),('aliases',u3)]:
 d=copy.deepcopy(base);d['nodes']=[node(-1,'World'),node(0,'A'),node(0,'B'),node(0,'Receiver')];d['scripts']=[attachment(1,u1,1),attachment(2,key,2),attachment(3,u2,5)];d['script_connections']=[dict(source=i,signal=1,target=3,handler=1) for i in [1,2]]
 if name=='aliases':d['resources'].append(ref('alias.xubc',u3))
 write(name,d)
d=copy.deepcopy(base);d['nodes']=[node(-1,'World')]+[node(0,'s'+str(i)) for i in range(32)];d['scripts']=[attachment(i+1,u1 if i<2 else u2,1) for i in range(32)];d['script_connections']=[dict(source=1,signal=1,target=i,handler=1) for i in range(3,33)]+[dict(source=2,signal=1,target=i,handler=1) for i in [3,4]];write('full',d)
rejects=[]
def bad(name,mutate):
 d=copy.deepcopy(base);mutate(d);write('reject-'+name,d);rejects.append('reject-'+name+'.xuscene')
for key in ['scripts','script_connections']:
 for label,value in [('null',None),('object',{}),('scalar',1)]:bad(key+'-'+label,lambda d,k=key,v=value:d.__setitem__(k,v))
 bad('missing-'+key,lambda d,k=key:d.pop(k))
bad('empty-scripts',lambda d:d.update(scripts=[]));bad('script-limit',lambda d:d.update(scripts=d['scripts']*17));bad('route-limit',lambda d:d.update(script_connections=d['script_connections']*33))
for label,value in [('negative',-1),('high',3),('float',.5),('null',None)]:bad('node-'+label,lambda d,v=value:d['scripts'][0].update(node=v))
bad('duplicate-node',lambda d:d['scripts'][1].update(node=1));bad('unknown-resource',lambda d:d['scripts'][0].update(resource=u3));bad('wrong-kind',lambda d:d['resources'][0].update(type='wav_clip'))
for key in ['node','resource','initial']:bad('missing-script-'+key,lambda d,k=key:d['scripts'][0].pop(k))
bad('script-extra',lambda d:d['scripts'][0].update(class_name='Mover'))
for label,value in [('null',None),('object',{}),('count',[dict(id=i+1,value=0) for i in range(33)])]:bad('initial-'+label,lambda d,v=value:d['scripts'][0].update(initial=v))
for label,value in [('negative',-1),('zero',0),('high',2147483648),('float',1.1),('null',None)]:bad('field-id-'+label,lambda d,v=value:d['scripts'][0]['initial'][0].update(id=v))
for label,value in [('high',1e9+1),('low',-1e9-1),('string','0'),('null',None),('boolean',True)]:bad('field-value-'+label,lambda d,v=value:d['scripts'][0]['initial'][0].update(value=v))
bad('field-duplicate',lambda d:d['scripts'][0]['initial'].append(dict(id=3,value=1)));bad('field-extra',lambda d:d['scripts'][0]['initial'][0].update(name='speed'));bad('field-missing',lambda d:d['scripts'][0]['initial'][0].pop('value'))
for key in ['source','target','signal','handler']:
 bad('route-missing-'+key,lambda d,k=key:d['script_connections'][0].pop(k))
 for label,value in [('negative',-1),('high',2147483648),('null',None),('float',.5)]:bad('route-'+key+'-'+label,lambda d,k=key,v=value:d['script_connections'][0].__setitem__(k,v))
bad('route-nonscript',lambda d:d['script_connections'][0].update(source=0));bad('route-duplicate',lambda d:d['script_connections'].append(copy.deepcopy(d['script_connections'][0])));bad('route-extra',lambda d:d['script_connections'][0].update(deferred=True));bad('version-7-missing-arrays',lambda d:d.update(version=7));bad('unsupported-version',lambda d:d.update(version=10))
(out/'reject-list.txt').write_text('\n'.join(rejects)+'\n')
# Keep a standalone copy for the GPU runner's deterministic mid-frame switch.
shutil.copyfile(out/'next.xubc',root/'build/scene-scripts/next.xubc')
print(f'Scene script fixtures: {len(rejects)} strict rejects; compiled stable-ID rename/removal/identity/failure candidates')

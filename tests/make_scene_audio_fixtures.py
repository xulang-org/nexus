#!/usr/bin/env python3
"""Independent current-schema scene/audio fixtures and original combined demo assets."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct

root=Path(__file__).resolve().parents[1]
out=root/'build/scene-audio-fixtures';out.mkdir(parents=True,exist_ok=True)
uid='33003300330033003300330033003300';uid2='44004400440044004400440044004400'
I=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
def node(parent,name,kind='Node',pos=0):
 d=dict(parent=parent,name=name,type=kind,visible=True,process='inherit')
 if kind=='Node3D': d['transform']=I.copy();d['transform'][12]=pos
 if kind=='Node2D': d['transform']=[1,0,0,1,pos,0]
 return d
def wave(samples=b'\xe8\x03\x18\xfc\xd0\x07\x30\xf8',junk=b''):
 data=b'fmt '+struct.pack('<IHHIIHH',16,1,1,8000,16000,2,16)+b'data'+struct.pack('<I',len(samples))+samples
 if junk:data+=b'JUNK'+struct.pack('<I',len(junk))+junk
 return b'RIFF'+struct.pack('<I',len(data)+4)+b'WAVE'+data
def ref(path,data,key=uid):return dict(uid=key,type='wav_clip',path=path,sha256=hashlib.sha256(data).hexdigest())
def bus(parent,name,volume=1,muted=False,paused=False):return dict(parent=parent,name=name,volume=volume,muted=muted,paused=paused)
def emitter(index=1,key=uid,route=0,**kwargs):
 d=dict(node=index,resource=key,bus=route,volume=1,pan=0,looping=True,autoplay=True,spatial='none',listener=-1,max_distance=0);d.update(kwargs);return d
def write(name,data): (out/(name+'.xuscene')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
raw=wave();(out/'tone.wav').write_bytes(raw);(out/'alias.wav').write_bytes(raw)
base=dict(format='xu.scene',version=1,nodes=[node(-1,'World','Node3D'),node(0,'Sound')],resources=[ref('tone.wav',raw)],surfaces=[],audio_buses=[bus(-1,'Master',.5),bus(0,'Effects',.5)],audio_emitters=[emitter(route=1)])
base['scripts']=[];base['script_connections']=[];base['lights']=[]
write('base',base)
for label,mutation in [('manual',lambda d:d['audio_emitters'][0].update(autoplay=False)),('muted',lambda d:d['audio_buses'][1].update(muted=True)),('bus-paused',lambda d:d['audio_buses'][1].update(paused=True)),('once',lambda d:d['audio_emitters'][0].update(looping=False))]:
 d=copy.deepcopy(base);mutation(d);write(label,d)
for dimension in ['2d','3d']:
 d=copy.deepcopy(base);kind='Node2D' if dimension=='2d' else 'Node3D';d['nodes']=[node(-1,'World','Node3D'),node(0,'Sound',kind,5),node(0,'Listener',kind)];d['audio_buses']=[bus(-1,'Master')];d['audio_emitters']=[emitter(spatial=dimension,listener=2,max_distance=10)];write(dimension,d)
d=copy.deepcopy(base);d['nodes'].append(node(0,'Alias'));d['resources'].append(ref('alias.wav',raw,uid2));d['audio_emitters'].append(emitter(2,uid2,1,autoplay=False));write('sharing',d)
d=copy.deepcopy(base);d['nodes']=[node(-1,'World')]+[node(0,f'e{i}') for i in range(32)];d['audio_emitters']=[emitter(i+1,volume=0) for i in range(32)];d['audio_buses']=[bus(-1,'Master')]+[bus(i-1,f'b{i}') for i in range(1,16)];write('full',d)
for label,path,digest in [('missing','absent.wav',hashlib.sha256(raw).hexdigest()),('hash','tone.wav','0'*64)]:
 d=copy.deepcopy(base);d['resources'][0].update(path=path,sha256=digest);write(label,d)
broken=b'RIFF\x00\x00\x00\x00bad wave';(out/'broken.wav').write_bytes(broken)
d=copy.deepcopy(base);d['nodes'].append(node(0,'Second'));d['resources'].append(ref('broken.wav',broken,uid2));d['audio_emitters'].append(emitter(2,uid2));write('late-bad',d)
# The first clip fits; the second exceeds the aggregate 8M decoded sample bank.
for name,count,value in [('bank-a',4194304,0),('bank-b',4194305,1)]:
 data=wave(struct.pack('<h',value)*count);(out/(name+'.wav')).write_bytes(data)
d=copy.deepcopy(d);d['resources']=[ref('bank-a.wav',(out/'bank-a.wav').read_bytes()),ref('bank-b.wav',(out/'bank-b.wav').read_bytes(),uid2)];write('bank-budget',d)
# Three individually valid WAV files exceed the 64MiB aggregate read cap.
large_refs=[]
for i in range(3):
 data=wave(junk=bytes([i])*(24*1024*1024));name=f'large-{i}.wav';(out/name).write_bytes(data);large_refs.append(ref(name,data,str(i+1)*32))
d=copy.deepcopy(base);d['nodes']=[node(-1,'World')]+[node(0,f's{i}') for i in range(3)];d['resources']=large_refs;d['audio_emitters']=[emitter(i+1,r['uid']) for i,r in enumerate(large_refs)];write('source-budget',d)
# A late invalid listener must not apply an earlier source's pending stop.
d=copy.deepcopy(base);d['nodes']=[node(-1,'World','Node3D'),node(0,'First','Node3D',5),node(0,'Second','Node3D',5),node(0,'Listener','Node3D')];d['audio_buses']=[bus(-1,'Master')];d['audio_emitters']=[emitter(i,spatial='3d',listener=3,max_distance=10) for i in [1,2]];write('spatial-pair',d)
rejects=[]
def bad(name,mutation):
 d=copy.deepcopy(base);mutation(d);write('bad-'+name,d);rejects.append('bad-'+name+'.xuscene')
for key in ['audio_buses','audio_emitters']:
 for label,value in [('empty',[]),('null',None),('object',{}),('scalar',1)]:bad(key+'-'+label,lambda d,k=key,v=value:d.__setitem__(k,v))
 bad('missing-'+key,lambda d,k=key:d.pop(k))
for key,value in [('parent',0),('name','WrongMaster'),('volume',-1),('muted',0),('paused',None)]:bad('master-'+key,lambda d,k=key,v=value:d['audio_buses'][0].__setitem__(k,v))
for label,changes in [('future',dict(parent=2)),('negative',dict(parent=-1)),('same-name',dict(name='Master')),('name-empty',dict(name='')),('name-long',dict(name='x'*64)),('volume-high',dict(volume=4.01)),('volume-null',dict(volume=None)),('unknown',dict(effect='filter'))]:bad('bus-'+label,lambda d,c=changes:d['audio_buses'][1].update(c))
for key,value in [('node',-1),('resource',uid2),('bus',2),('volume',-1),('pan',1.01),('looping',0),('autoplay',None),('spatial','4d'),('listener',0),('max_distance',1)]:bad('emitter-'+key,lambda d,k=key,v=value:d['audio_emitters'][0].__setitem__(k,v))
for label,changes in [('node-high',dict(node=2)),('node-float',dict(node=.5)),('volume-high',dict(volume=4.01)),('pan-low',dict(pan=-1.01)),('spatial-kind',dict(spatial='3d',listener=0,max_distance=10)),('unknown',dict(pitch=1))]:bad('emitter-'+label,lambda d,c=changes:d['audio_emitters'][0].update(c))
for key in ['node','resource','bus','volume','pan','looping','autoplay','spatial','listener','max_distance']:bad('emitter-missing-'+key,lambda d,k=key:d['audio_emitters'][0].pop(k))
bad('duplicate-emitter',lambda d:d['audio_emitters'].append(copy.deepcopy(d['audio_emitters'][0])))
bad('bus-limit',lambda d:d.__setitem__('audio_buses',d['audio_buses']*9));bad('emitter-limit',lambda d:d.__setitem__('audio_emitters',d['audio_emitters']*33))
bad('wrong-source-kind',lambda d:d['resources'][0].update(type='glb_model'))
bad('future-version',lambda d:d.update(version=5));bad('unversioned-audio',lambda d:d.pop('version'))
for label,changes in [('listener-high',dict(listener=2)),('listener-negative',dict(listener=-1)),('range-zero',dict(max_distance=0)),('range-high',dict(max_distance=1000000001)),('pan',dict(pan=.1))]:
 def mutation(d,c=changes):
  d['nodes'][1]=node(0,'Sound','Node3D');d['audio_emitters'][0].update(spatial='3d',listener=0,max_distance=10);d['audio_emitters'][0].update(c)
 bad('spatial-'+label,mutation)
(out/'reject-list.txt').write_text('\n'.join(rejects)+'\n')
# Standalone authored scene and combined scene reuse the project's original chime.
assets=root/'examples/scene_audio/assets';assets.mkdir(parents=True,exist_ok=True)
chime=(root/'examples/audio/assets/chime.wav').read_bytes()
for path,data in [(assets/'chime.wav',chime)]:
 if path.exists():assert path.read_bytes()==data
 else:path.write_bytes(data)
original=copy.deepcopy(base);original['nodes'][0]['name']='AudioRoom';original['resources']=[ref('chime.wav',chime)];original['audio_emitters'][0]['volume']=.4
path=assets/'world.xuscene';text=json.dumps(original,ensure_ascii=False,indent=2)+'\n'
if path.exists():assert path.read_text()==text
else:path.write_text(text)
av=root/'examples/scene_av/assets';av.mkdir(parents=True,exist_ok=True)
combined=json.loads((root/'examples/scene_assets/assets/world.xuscene').read_text());combined['lights']=[dict(node=0,type='directional',direction=[.4,.7,1],radiance=[2.5,2.5,2.5])];combined.update(version=1);combined['nodes'].append(node(0,'Music'));combined['resources'].append(ref('chime.wav',chime));combined['audio_buses']=[bus(-1,'Master',.5)];combined['audio_emitters']=[emitter(10,volume=.3)]
for name,data in [('panels.glb',(root/'examples/scene_assets/assets/panels.glb').read_bytes()),('chime.wav',chime)]:
 path=av/name
 if path.exists():assert path.read_bytes()==data
 else:path.write_bytes(data)
path=av/'world.xuscene';text=json.dumps(combined,ensure_ascii=False,indent=2)+'\n'
if path.exists():assert path.read_text()==text
else:path.write_text(text)
for source,name in [(assets,'scene-audio'),(av,'scene-av')]:
 target=root/'build'/name;target.mkdir(exist_ok=True)
 for path in source.iterdir():
  if path.suffix in ['.xuscene','.wav','.glb']:shutil.copyfile(path,target/path.name)
print(f'Scene audio fixtures: {len(rejects)} strict rejects, known PCM/spatial/bus/voice limits and original audio/AV scenes')

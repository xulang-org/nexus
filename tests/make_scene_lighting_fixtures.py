"""Independently authored light scene corpus for strict decoding and runtime restoration."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/scene-lighting-fixtures'
OUT.mkdir(parents=True,exist_ok=True)
I=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
def node(parent,name,kind='Node3D',x=0,visible=True):
    result=dict(parent=parent,name=name,type=kind,visible=visible,process='inherit')
    if kind=='Node3D':
        result['transform']=I.copy();result['transform'][12]=x
    if kind=='Node2D':result['transform']=[1,0,0,1,0,0]
    return result
base=dict(format='xu.scene',version=1,
          nodes=[node(-1,'World',x=5),node(0,'Pivot',x=3),node(1,'Directional'),
                 node(1,'Point',x=2),node(1,'Spot'),node(0,'Hidden',visible=False),node(0,'HUD','Node2D')],
          resources=[],surfaces=[],audio_buses=[],audio_emitters=[],scripts=[],script_connections=[],lights=[
              dict(node=2,type='directional',direction=[0,0,2],radiance=[.12345678901234567,1,2]),
              dict(node=3,type='point',position=[.125,0,1],radiance=[3,4,5],radius=8.123456789012345),
              dict(node=4,type='spot',position=[0,0,2],direction=[0,0,-3],radiance=[6,7,8],radius=12,
                   inner_cosine=.9751234567890123,outer_cosine=.7001234567890123),
              dict(node=5,type='point',position=[0,0,0],radiance=[64,0,0],radius=.001)])
def write(name,data):
    (OUT/(name+'.xuscene')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
write('base',base)
profile = dict(count=3, resolution=256, distance=42.98765432101234, split_lambda=.71, blend_fraction=.19,
               caster_padding=7.5, stabilization_step=.03125, raster_bias_texels=.0078125)
authored = copy.deepcopy(base)
authored['version'] = 4
authored['lights'][0]['cascades'] = profile
authored['lights'][3] = dict(node=5, type='directional', direction=[1,0,0], radiance=[2,2,2],
                             cascades=dict(profile, count=4))
write('cascades', authored)
point_shadow = dict(near=.12345678901234567, resolution=512, constant_bias=.00002, slope_bias=.00005)
spot_shadow = dict(near=.375, resolution=1024, constant_bias=.00003, slope_bias=.00004)
punctual = copy.deepcopy(authored)
punctual['version'] = 5
punctual['lights'][1]['shadow'] = point_shadow
punctual['lights'][2]['shadow'] = spot_shadow
write('punctual', punctual)
full=copy.deepcopy(base)
full['nodes']=[node(-1,'World')]+[node(0,'Light'+str(i),visible=False) for i in range(256)]
full['lights']=[dict(node=i+1,type='point',position=[0,0,0],radiance=[1,1,1],radius=5) for i in range(256)]
write('full',full)
visible=copy.deepcopy(full);visible['nodes']=visible['nodes'][:18];visible['lights']=visible['lights'][:17]
for n in visible['nodes']:n['visible']=True
write('visible17',visible)
rejects=[]
def bad(name,change):
    data=copy.deepcopy(base);change(data);write('reject-'+name,data);rejects.append('reject-'+name+'.xuscene')
bad('missing',lambda d:d.pop('lights'))
for value in [None,{},0]:bad('array-'+str(value),lambda d,v=value:d.__setitem__('lights',v))
for name,value in [('null',None),('number',1),('list',[])]:bad('item-'+name,lambda d,v=value:d['lights'].__setitem__(0,v))
for key in ['node','type','direction','radiance']:bad('directional-missing-'+key,lambda d,k=key:d['lights'][0].pop(k))
for key in ['node','type','position','radiance','radius']:bad('point-missing-'+key,lambda d,k=key:d['lights'][1].pop(k))
for key in ['node','type','position','direction','radiance','radius','inner_cosine','outer_cosine']:bad('spot-missing-'+key,lambda d,k=key:d['lights'][2].pop(k))
for name,index,change in [
    ('node-negative',0,dict(node=-1)),('node-high',0,dict(node=7)),('node-fraction',0,dict(node=.5)),('node-bool',0,dict(node=True)),
    ('type-unknown',0,dict(type='area')),('type-number',0,dict(type=0)),('node-kind',0,dict(node=6)),
    ('direction-zero',0,dict(direction=[0,0,0])),('direction-shape',0,dict(direction=[1,0])),
    ('direction-value',0,dict(direction=[1,'2',3])),('direction-overflow',0,dict(direction=[0,0,1e309])),
    ('radiance-negative',0,dict(radiance=[-1,0,0])),('radiance-high',0,dict(radiance=[0,64.01,0])),
    ('radiance-shape',0,dict(radiance=[0,0,0,1])),('radiance-nan',0,dict(radiance=[float('nan'),0,0])),
    ('unused-position',0,dict(position=[0,0,0])),('unknown-property',1,dict(shadows=True)),
    ('point-direction',1,dict(direction=[0,0,1])),('position-high',1,dict(position=[1e9+1,0,0])),
    ('radius-zero',1,dict(radius=0)),('radius-small',1,dict(radius=.0009)),('radius-large',1,dict(radius=1000001)),
    ('radius-string',1,dict(radius='8')),('radius-bool',1,dict(radius=True)),
    ('cone-reversed',2,dict(inner_cosine=.6)),('cone-zero',2,dict(outer_cosine=0)),
    ('cone-large',2,dict(inner_cosine=1.1)),('cone-narrow',2,dict(inner_cosine=.7001234567890223)),
    ('cone-string',2,dict(inner_cosine='0.9')),('cone-degrees',2,dict(inner_half_angle=20)),
]:bad(name,lambda d,i=index,c=change:d['lights'][i].update(c))
bad('duplicate-node',lambda d:d['lights'].append(copy.deepcopy(d['lights'][0])))
for label, version, index, value in [
    ('legacy', 3, 0, profile),
    ('point', 4, 1, profile),
    ('spot', 4, 2, profile),
    ('null', 4, 0, None),
    ('extra', 4, 0, dict(profile, atlas_handle=7)),
    ('missing', 4, 0, {k: v for k, v in profile.items() if k != 'distance'}),
    ('count-zero', 4, 0, dict(profile, count=0)),
    ('count-high', 4, 0, dict(profile, count=5)),
    ('count-fraction', 4, 0, dict(profile, count=3.5)),
    ('resolution', 4, 0, dict(profile, resolution=260)),
    ('distance-zero', 4, 0, dict(profile, distance=0)),
    ('lambda', 4, 0, dict(profile, split_lambda=1.1)),
    ('blend', 4, 0, dict(profile, blend_fraction=.31)),
    ('padding', 4, 0, dict(profile, caster_padding=-1)),
    ('step', 4, 0, dict(profile, stabilization_step=0)),
    ('bias', 4, 0, dict(profile, raster_bias_texels=.51)),
]:
    def invalid_cascades(scene, schema=version, light=index, cascades=value):
        scene['version'] = schema
        scene['lights'][light]['cascades'] = cascades
    bad('cascades-' + label, invalid_cascades)
for label, version, index, value in [
    ('legacy', 4, 1, point_shadow),
    ('directional', 5, 0, point_shadow),
    ('null', 5, 1, None),
    ('extra', 5, 1, dict(point_shadow, face_count=6)),
    ('missing', 5, 2, {k: v for k, v in spot_shadow.items() if k != 'near'}),
    ('point-resolution', 5, 1, dict(point_shadow, resolution=1024)),
    ('non-power-of-two', 5, 2, dict(spot_shadow, resolution=300)),
    ('resolution-zero', 5, 2, dict(spot_shadow, resolution=0)),
    ('resolution-fraction', 5, 2, dict(spot_shadow, resolution=128.5)),
    ('near-small', 5, 1, dict(point_shadow, near=.00009)),
    ('near-at-range', 5, 2, dict(spot_shadow, near=12)),
    ('near-almost-range', 5, 2, dict(spot_shadow, near=11.999999)),
    ('bias-negative', 5, 1, dict(point_shadow, constant_bias=-.01)),
    ('bias-too-large', 5, 2, dict(spot_shadow, slope_bias=.05001)),
    ('bias-string', 5, 2, dict(spot_shadow, slope_bias='.01')),
]:
    def invalid_shadow(scene, schema=version, light=index, shadow=value):
        scene['version'] = schema
        scene['lights'][light]['shadow'] = shadow
    bad('shadow-' + label, invalid_shadow)
def invalid_shadow_cone(scene):
    scene['version'] = 5
    scene['lights'][2].update(outer_cosine=.0009, shadow=spot_shadow)
bad('shadow-spot-cone', invalid_shadow_cone)
large=copy.deepcopy(full);large['nodes'].append(node(0,'Overflow'));large['lights'].append(dict(node=257,type='point',position=[0,0,0],radiance=[0,0,0],radius=1));write('reject-count',large);rejects.append('reject-count.xuscene')
# JSON duplicate fields must fail before a last-write-wins dictionary can hide them.
raw=json.dumps(base,separators=(',',':'))
(OUT/'reject-duplicate-field.xuscene').write_text(raw.replace('"inner_cosine":','"node":4,"inner_cosine":'))
rejects.append('reject-duplicate-field.xuscene')
(OUT/'reject-list.txt').write_text('\n'.join(rejects)+'\n')
print('Prepared scene light corpus:',len(rejects),'strict rejects')

import copy, json, math, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/glb-fixtures'
OUT.mkdir(parents=True,exist_ok=True)

def glb(doc, data, extra=b''):
    j=json.dumps(doc,separators=(',',':'),ensure_ascii=True).encode()
    j+=b' '*((-len(j))%4)
    b=data+b'\0'*((-len(data))%4)
    chunks=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b+extra
    return struct.pack('<III',0x46546c67,2,12+len(chunks))+chunks

def base():
    # Four attributes interleaved at byte offsets 0/12/24/32, stride 36.
    p=[(-1.,-1.,0.),(1.,-1.,0.),(0.,1.,0.)]
    data=b''.join(struct.pack('<3f3f2f4B',*v,0,0,1,*uv,255,0,0,255) for v,uv in zip(p,[(0,0),(1,0),(.5,1)]))
    data+=struct.pack('<3H',0,1,2)
    doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(data)}],
      'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':108,'byteStride':36,'target':34962}, {'buffer':0,'byteOffset':108,'byteLength':6,'target':34963}],
      'accessors':[{'bufferView':0,'byteOffset':0,'componentType':5126,'count':3,'type':'VEC3','min':[-1,-1,0],'max':[1,1,0]},
       {'bufferView':0,'byteOffset':12,'componentType':5126,'count':3,'type':'VEC3'},
       {'bufferView':0,'byteOffset':24,'componentType':5126,'count':3,'type':'VEC2'},
       {'bufferView':0,'byteOffset':32,'componentType':5121,'normalized':True,'count':3,'type':'VEC4'},
       {'bufferView':1,'componentType':5123,'count':3,'type':'SCALAR'}],
      'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'TEXCOORD_0':2,'COLOR_0':3},'indices':4}]}],
      'nodes':[{'name':'Root/name','children':[1]},{'name':'Triangle','mesh':0,'translation':[0,0,-2]}, {'name':'Other scene','mesh':0,'translation':[2,0,-2]}],
      'scenes':[{'nodes':[0]},{'nodes':[2]}],'scene':0}
    return doc,data

doc,data=base()
(OUT/'triangle.glb').write_bytes(glb(doc,data))
other=copy.deepcopy(doc); other['asset']['generator']='different source'
(OUT/'other.glb').write_bytes(glb(other,data))
# Original authored tower geometry. This is a model source asset, not executable output.
points=[(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)]
faces=[([4,5,6,7],(0,0,1),(66,210,182,255)),([1,0,3,2],(0,0,-1),(28,115,134,255)),([0,4,7,3],(-1,0,0),(39,145,166,255)),([5,1,2,6],(1,0,0),(238,170,72,255)),([3,7,6,2],(0,1,0),(146,244,210,255)),([0,1,5,4],(0,-1,0),(25,91,111,255))]
vertices=[]; indices=[]
for corners,n,c in faces:
    start=len(vertices)
    for corner,uv in zip(corners,[(0,0),(1,0),(1,1),(0,1)]): vertices.append(struct.pack('<3f3f2f4B',*points[corner],*n,*uv,*c))
    indices.extend([start,start+1,start+2,start,start+2,start+3])
bin_data=b''.join(vertices)+struct.pack('<36H',*indices)
views=[{'buffer':0,'byteOffset':0,'byteLength':864,'byteStride':36,'target':34962}, {'buffer':0,'byteOffset':864,'byteLength':72,'target':34963}]
accessors=[{'bufferView':0,'byteOffset':0,'componentType':5126,'count':24,'type':'VEC3','min':[-.5]*3,'max':[.5]*3}, {'bufferView':0,'byteOffset':12,'componentType':5126,'count':24,'type':'VEC3'}, {'bufferView':0,'byteOffset':24,'componentType':5126,'count':24,'type':'VEC2'}, {'bufferView':0,'byteOffset':32,'componentType':5121,'normalized':True,'count':24,'type':'VEC4'}, {'bufferView':1,'byteOffset':0,'componentType':5123,'count':18,'type':'SCALAR'}, {'bufferView':1,'byteOffset':36,'componentType':5123,'count':18,'type':'SCALAR'}]
floor=[(-5,-1.2,-5),(5,-1.2,5),(5,-1.2,-5),(-5,-1.2,-5),(-5,-1.2,5),(5,-1.2,5)]
floor_bytes=b''.join(struct.pack('<3f3f2f4B',*v,0,1,0,0,0,32,49,69,255) for v in floor)
views.append({'buffer':0,'byteOffset':len(bin_data),'byteLength':len(floor_bytes),'byteStride':36,'target':34962})
bin_data+=floor_bytes
for off,typ,component in [(0,'VEC3',5126),(12,'VEC3',5126),(24,'VEC2',5126),(32,'VEC4',5121)]:
    a={'bufferView':2,'byteOffset':off,'componentType':component,'count':6,'type':typ}
    if off==0: a.update(min=[-5,-1.2,-5],max=[5,-1.2,5])
    if component==5121: a['normalized']=True
    accessors.append(a)
attrs={'POSITION':0,'NORMAL':1,'TEXCOORD_0':2,'COLOR_0':3}
tower={'asset':{'version':'2.0','generator':'Xu Game original static geometry asset'}, 'buffers':[{'byteLength':len(bin_data)}], 'bufferViews':views,'accessors':accessors,'meshes':[{'name':'Colored cube','primitives':[{'attributes':attrs,'indices':4},{'attributes':attrs,'indices':5}]},{'name':'Floor','primitives':[{'attributes':{'POSITION':6,'NORMAL':7,'TEXCOORD_0':8,'COLOR_0':9}}]}], 'nodes':[{'name':'Tower','children':[1,2,3,4,5]}, {'name':'Base','mesh':0,'translation':[0,-.95,0],'scale':[3,.4,3]}, {'name':'Shaft','mesh':0,'translation':[0,.2,0],'scale':[1,1.9,1],'rotation':[0,math.sin(.175),0,math.cos(.175)]}, {'name':'Crown','mesh':0,'translation':[0,1.65,0],'scale':[2,.5,2],'rotation':[0,math.sin(math.pi/8),0,math.cos(math.pi/8)]}, {'name':'Satellite','mesh':0,'matrix':[.65,0,0,0,0,.65,0,0,0,0,.65,0,2,-.5,.7,1],'children':[6]}, {'name':'Floor','mesh':1}, {'name':'Satellite top','mesh':0,'translation':[0,1.2,0],'scale':[.45,.45,.45]}, {'name':'Unused scene','mesh':0}], 'scenes':[{'nodes':[0]},{'nodes':[7]}], 'scene':0}
model_path=ROOT/'examples/glb_preview/assets/tower.glb'
if model_path.exists():
    assert model_path.read_bytes()==glb(tower,bin_data), 'source model and authored reference diverged'
else:
    model_path.write_bytes(glb(tower,bin_data))
print('Wrote original tower.glb:',len(glb(tower,bin_data)),'bytes; expected 11 instances / 62 triangles')
# Valid format variants and independent expected values for the Xu checks.
def write(name,d,b): (OUT/(name+'.glb')).write_bytes(glb(d,b))
d,b=base();d['meshes'][0]['primitives'].append(copy.deepcopy(d['meshes'][0]['primitives'][0]));d['meshes'][0]['primitives'][1]['attributes'].pop('NORMAL');write('mixed-normals',d,b)
for component,fmt in [(5121,'B'),(5123,'H'),(5125,'I')]:
    d,b=base(); b=b[:108]+struct.pack('<3'+fmt,0,1,2); d['bufferViews'][1]['byteLength']=len(b)-108; d['accessors'][4]['componentType']=component; d['buffers'][0]['byteLength']=len(b); write('index-'+str(component),d,b)
d,b=base(); del d['meshes'][0]['primitives'][0]['indices']; write('nonindexed',d,b)
d,b=base(); del d['meshes'][0]['primitives'][0]['attributes']['COLOR_0']; del d['meshes'][0]['primitives'][0]['attributes']['NORMAL']; del d['meshes'][0]['primitives'][0]['attributes']['TEXCOORD_0']; write('positions-only',d,b)
d,b=base(); d['accessors'][3]['type']='VEC3'; write('rgb',d,b)
for name,comp,fmt,vals in [('color16',5123,'4H',(32768,65535,16384,65535)),('colorfloat',5126,'4f',(.5,1.,.25,1.)),('uv16',5123,'2H',(32768,65535)),('uv8',5121,'2B',(128,255))]:
    d,b=base(); start=len(b); start=(start+3)&~3; b+=b'\0'*(start-len(b)); raw=struct.pack('<'+fmt,*vals); stride=(len(raw)+3)&~3; b+=b''.join(raw+b'\0'*(stride-len(raw)) for _ in range(3)); d['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':stride*3,'byteStride':stride}); idx=3 if name.startswith('color') else 2; d['accessors'][idx].update(bufferView=2,byteOffset=0,componentType=comp,normalized=comp!=5126); d['buffers'][0]['byteLength']=len(b); write(name,d,b)
d,b=base(); d['nodes'][0]['translation']=[2,3,4]; d['nodes'][0]['rotation']=[0,0,math.sqrt(.5),math.sqrt(.5)]; d['nodes'][1]['translation']=[1,0,-2]; d['nodes'][1]['scale']=[2,3,-4]; write('trs',d,b)
d,b=base(); d['nodes'][1]={'mesh':0,'matrix':[2,0,0,0,0,3,0,0,0,0,-4,0,1,2,-2,1]}; write('matrix',d,b)
d,b=base(); d['scene']=1; write('scene-one',d,b)
d,b=base(); del d['scene']; write('default-scene',d,b)
d,b=base(); unknown=struct.pack('<II',4,0x12345678)+b'1234'; (OUT/'unknown-chunk.glb').write_bytes(glb(d,b,unknown))
d,b=base(); d['nodes']=[{'children':[i+1]} for i in range(64)]+[{'mesh':0}]; d['scenes']=[{'nodes':[0]}]; write('depth64',d,b)

bad=[]
def reject(name,change,needle):
    d,b=base(); d,b=change(d,b); write('bad-'+name,d,b); bad.append(('bad-'+name+'.glb',needle))
def mutate(fn):
    def apply(d,b): fn(d); return d,b
    return apply
reject('external-buffer',mutate(lambda d:d['buffers'][0].update(uri='file:///tmp/forbidden.bin')),'unsupported property: uri')
reject('materials',mutate(lambda d:d.update(materials=[{'alphaMode':'BLEND'}])),'only supports OPAQUE')
reject('primitive-material',mutate(lambda d:d['meshes'][0]['primitives'][0].update(material=0)),'integer outside limits: material')
reject('animations',mutate(lambda d:d.update(animations=[])),'array outside profile limits')
reject('required-extension',mutate(lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression'])),'unsupported extension')
reject('nested-extension',mutate(lambda d:d['nodes'][2].update(extensions={'not_supported':{}})),'unsupported object extension')
reject('future-version',mutate(lambda d:d['asset'].update(minVersion='2.1')),'asset version 2.0')
reject('view-range',mutate(lambda d:d['bufferViews'][0].update(byteLength=2000)),'integer outside limits')
reject('view-negative',mutate(lambda d:d['bufferViews'][0].update(byteOffset=-4)),'integer outside limits')
reject('stride-small',mutate(lambda d:d['bufferViews'][0].update(byteStride=8)),'alignment or range invalid')
reject('stride-align',mutate(lambda d:d['bufferViews'][0].update(byteStride=14)),'range or stride')
reject('component',mutate(lambda d:d['accessors'][0].update(componentType=5122)),'unsupported accessor component')
reject('offset-align',mutate(lambda d:d['accessors'][0].update(byteOffset=2)),'alignment or range invalid')
reject('count-negative',mutate(lambda d:d['accessors'][0].update(count=-1)),'integer outside limits')
reject('last-element',mutate(lambda d:d['accessors'][0].update(count=4)),'exceeds bufferView')
reject('sparse',mutate(lambda d:d['accessors'][0].update(sparse={})),'unsupported property: sparse')
reject('normalized-float',mutate(lambda d:d['accessors'][0].update(normalized=True)),'invalid normalized')
reject('missing-bounds',mutate(lambda d:d['accessors'][0].pop('max')),'requires bounded float VEC3 and min/max')
reject('bounds-values',mutate(lambda d:d['accessors'][0].update(max=[.5,1,0])),'min/max do not match')
reject('bounds-reversed',mutate(lambda d:d['accessors'][0].update(min=[2,-1,0])),'reversed accessor bounds')
reject('attribute-count',mutate(lambda d:d['accessors'][1].update(count=2)),'incompatible vertex attribute')
reject('color-normalized',mutate(lambda d:d['accessors'][3].update(normalized=False)),'unsupported color encoding')
reject('unknown-attribute',mutate(lambda d:d['meshes'][0]['primitives'][0]['attributes'].update(COLOR_1=3)),'unsupported property: COLOR_1')
reject('mode',mutate(lambda d:d['meshes'][0]['primitives'][0].update(mode=5)),'only TRIANGLES')
reject('topology-count',mutate(lambda d:d['accessors'][4].update(count=2)),'TRIANGLES index count')
reject('cycle',mutate(lambda d:d['nodes'][1].update(children=[0])),'cyclic node hierarchy')
reject('multiple-parent',mutate(lambda d:d['nodes'][2].update(children=[1])),'multiple parents or duplicate edge')
reject('child-range',mutate(lambda d:d['nodes'][0].update(children=[3])),'invalid child')
reject('duplicate-child',mutate(lambda d:d['nodes'][0].update(children=[1,1])),'duplicate edge')
reject('scene-root',mutate(lambda d:d['scenes'][0].update(nodes=[1])),'invalid or duplicate scene root')
reject('scene-index',mutate(lambda d:d.update(scene=2)),'integer outside limits')
reject('node-mesh',mutate(lambda d:d['nodes'][1].update(mesh=3)),'integer outside limits')
reject('quaternion',mutate(lambda d:d['nodes'][1].update(rotation=[0,0,0,0])),'quaternion must be unit length')
reject('matrix-trs',mutate(lambda d:d['nodes'][1].update(matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])),'matrix and TRS cannot coexist')
reject('projective',mutate(lambda d:d['nodes'][0].update(matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,2])),'finite affine')
reject('shear',mutate(lambda d:d['nodes'][0].update(matrix=[1,0,0,0,1,1,0,0,0,0,1,0,0,0,0,1])),'sheared node matrix')
reject('buffer-short',mutate(lambda d:d['buffers'][0].update(byteLength=100)),'invalid embedded buffer length')
for label,off,bits,needle in [('nan-position',0,0x7fc00000,'non-finite input'),('inf-position',0,0x7f800000,'non-finite input'),('huge-position',0,0x7f7fffff,'outside engine scalar limits'),('normal-length',20,0,'NORMAL must be unit length'),('alpha',35,128,'requires opaque vertex alpha')]:
    def apply(d,b,off=off,bits=bits,label=label):
        x=bytearray(b)
        if label=='alpha': x[off]=bits
        else: struct.pack_into('<I',x,off,bits)
        return d,bytes(x)
    reject(label,apply,needle)
reject('index-range',lambda d,b:(d,b[:112]+struct.pack('<H',3)),'outside vertex array')
reject('restart',lambda d,b:(d,b[:112]+struct.pack('<H',65535)),'primitive restart')
def deep(d,b): d['nodes']=[{'children':[i+1]} for i in range(65)]+[{'mesh':0}];d['scenes']=[{'nodes':[0]}];return d,b
reject('depth65',deep,'exceeds depth 64')
d,b=base(); original=glb(d,b)
def reject_raw(name,raw,needle): (OUT/('bad-'+name+'.glb')).write_bytes(raw);bad.append(('bad-'+name+'.glb',needle))
reject_raw('truncated',original[:-1],'invalid magic/version/length')
x=bytearray(original);struct.pack_into('<I',x,0,0);reject_raw('magic',x,'invalid magic/version/length')
x=bytearray(original);struct.pack_into('<I',x,4,1);reject_raw('version',x,'invalid magic/version/length')
x=bytearray(original);struct.pack_into('<I',x,12,3);reject_raw('chunk-align',x,'unaligned or truncated chunk')
x=bytearray(original);struct.pack_into('<I',x,12,0xfffffffc);reject_raw('chunk-range',x,'unaligned or truncated chunk')
x=bytearray(original);x[-1]=1;reject_raw('bin-padding',x,'BIN padding must be zero')
reject_raw('duplicate-bin',glb(d,b,struct.pack('<II',4,0x004e4942)+b'0000'),'invalid BIN chunk')
reject_raw('duplicate-json',glb(d,b,struct.pack('<II',4,0x4e4f534a)+b'{}  '),'invalid JSON chunk')
j=b'{"asset":{},"asset":{}}';j+=b' '*((-len(j))%4); chunks=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',4,0x004e4942)+b'0000';reject_raw('json-duplicate',struct.pack('<III',0x46546c67,2,len(chunks)+12)+chunks,'nexus GLB JSON:')
# Authored tangent stream, distinct from geometry-only fixtures above.
def with_tangents():
    d,b=base(); start=(len(b)+3)&~3; b+=b'\0'*(start-len(b))
    b+=struct.pack('<4f',1,0,0,1)*3
    d['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':48,'byteStride':16,'target':34962})
    d['accessors'].append({'bufferView':2,'componentType':5126,'count':3,'type':'VEC4'})
    d['meshes'][0]['primitives'][0]['attributes']['TANGENT']=5
    d['buffers'][0]['byteLength']=len(b)
    return d,b
d,b=with_tangents();write('tangents',d,b)
d,b=with_tangents();b=b[:-48]+struct.pack('<4f',.6,0,.8,1)*3;write('tangents-exporter-basis',d,b)
d,b=with_tangents(); mirrored=bytearray(b)
for i,v in enumerate([0,0,1]): struct.pack_into('<f',mirrored,i*36+28,1-v)
b=bytes(mirrored);b=b[:-48]+struct.pack('<4f',1,0,0,-1)*3;write('tangents-mirrored',d,b)
d,b=with_tangents();d['meshes'][0]['primitives'].append(copy.deepcopy(d['meshes'][0]['primitives'][0]));d['meshes'][0]['primitives'][1]['attributes'].pop('TANGENT');write('mixed-tangents',d,b)
for label,field in [('tangent-no-normal','NORMAL'),('tangent-no-uv','TEXCOORD_0')]:
    d,b=with_tangents();d['meshes'][0]['primitives'][0]['attributes'].pop(field);write('bad-'+label,d,b);bad.append(('bad-'+label+'.glb','TANGENT profile requires'))
for label,values in [('tangent-zero',(0,0,0,1)),('tangent-length',(2,0,0,1)),('tangent-parallel',(0,0,1,1)),('tangent-sign',(1,0,0,0))]:
    d,b=with_tangents();b=b[:-48]+struct.pack('<4f',*values)*3;write('bad-'+label,d,b);bad.append(('bad-'+label+'.glb','TANGENT must be unit'))
d,b=with_tangents();b=b[:-16]+struct.pack('<4f',1,0,0,-1);write('bad-tangent-mixed',d,b);bad.append(('bad-tangent-mixed.glb','mixed tangent handedness'))
d,b=with_tangents();d['accessors'][5]['componentType']=5123;d['accessors'][5]['normalized']=True;write('bad-tangent-encoding',d,b);bad.append(('bad-tangent-encoding.glb','TANGENT requires float VEC4'))
d,b=with_tangents();d['accessors'][5]['count']=2;write('bad-tangent-count',d,b);bad.append(('bad-tangent-count.glb','incompatible vertex attribute'))
d,b=with_tangents();b=b[:-48]+struct.pack('<I',0x7fc00000)+b[-44:];write('bad-tangent-nan',d,b);bad.append(('bad-tangent-nan.glb','non-finite input'))
(OUT/'reject-list.txt').write_text(''.join(name+'|'+needle+'\n' for name,needle in bad))
print('Generated',len(bad),'rejection cases and valid index/color/UV/TRS/matrix/scene variants')
d,b=base(); d['extras']={'extensions':{'arbitrary_metadata':[1,2,3]}}; write('extras-metadata',d,b)
import hashlib
(OUT/'triangle.sha256').write_text(hashlib.sha256((OUT/'triangle.glb').read_bytes()).hexdigest())

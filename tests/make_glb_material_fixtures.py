"""Original GLB material assets and strict/failure fixtures, all deterministic."""
import copy
import json
import math
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/glb-material-fixtures'
OUT.mkdir(parents=True, exist_ok=True)

def png(w, h, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    if isinstance(pixels, tuple):
        rows = (b'\0' + bytes(pixels) * w) * h
    else:
        rows = b''.join(b'\0' + bytes(pixels[y*w*4:(y+1)*w*4]) for y in range(h))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')

def glb(doc, data):
    doc = copy.deepcopy(doc)
    doc['buffers'][0]['byteLength'] = len(data)
    j = json.dumps(doc, separators=(',', ':'), allow_nan=False).encode()
    j += b' ' * (-len(j) % 4)
    b = data + b'\0' * (-len(data) % 4)
    chunks = struct.pack('<II', len(j), 0x4e4f534a) + j + struct.pack('<II', len(b), 0x004e4942) + b
    return struct.pack('<III', 0x46546c67, 2, 12 + len(chunks)) + chunks

def base(materials=None, image_data=(), samplers=None, textures=None, z=0.5):
    points = [(-.8,-.8,z),(.8,-.8,z),(.8,.8,z),(-.8,.8,z)]
    uvs = [(0,1),(1,1),(1,0),(0,0)]
    data = b''.join(struct.pack('<3f3f2f4f', *p, 0,0,1, *uv, 1,0,0,-1) for p,uv in zip(points, uvs)) + struct.pack('<6H',0,1,2,0,2,3)
    doc = {'asset':{'version':'2.0','generator':'Xu Game original material reference'}, 'buffers':[{'byteLength':len(data)}],
        'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':192,'byteStride':48,'target':34962},{'buffer':0,'byteOffset':192,'byteLength':12,'target':34963}],
        'accessors':[{'bufferView':0,'byteOffset':0,'componentType':5126,'count':4,'type':'VEC3','min':[-.8,-.8,z],'max':[.8,.8,z]},
                     {'bufferView':0,'byteOffset':12,'componentType':5126,'count':4,'type':'VEC3'},
                     {'bufferView':0,'byteOffset':24,'componentType':5126,'count':4,'type':'VEC2'},
                     {'bufferView':0,'byteOffset':32,'componentType':5126,'count':4,'type':'VEC4'},
                     {'bufferView':1,'componentType':5123,'count':6,'type':'SCALAR'}],
        'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'TEXCOORD_0':2,'TANGENT':3},'indices':4}]}],
        'nodes':[{'name':'Panel','mesh':0}], 'scenes':[{'nodes':[0]}], 'scene':0}
    if materials is not None:
        doc['materials']=copy.deepcopy(materials)
        doc['meshes'][0]['primitives'][0]['material']=0
    if image_data:
        doc['images']=[]
        for raw in image_data:
            offset=(len(data)+3)&~3;data+=b'\0'*(offset-len(data));view=len(doc['bufferViews'])
            doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(raw)})
            doc['images'].append({'bufferView':view,'mimeType':'image/png'})
            data+=raw
        doc['samplers']=copy.deepcopy(samplers or [{'magFilter':9728,'minFilter':9728,'wrapS':33071,'wrapT':33071}])
        doc['textures']=copy.deepcopy(textures or [{'source':i,'sampler':0} for i in range(len(image_data))])
    return doc,data

def write(name, d, b): (OUT/(name+'.glb')).write_bytes(glb(d,b))
def mat(**values):
    pbr={'metallicFactor':0.0,'roughnessFactor':1.0}
    pbr.update(values)
    return {'pbrMetallicRoughness':pbr}

WHITE=png(1,1,(255,255,255,0));GRAY=png(1,1,(128,128,128,0));MR=png(1,1,(0,255,0,255));AO=png(1,1,(128,0,255,0));NORMAL=png(1,1,(128,128,255,255));EMISSION=png(1,1,(0,128,255,0))
valid={
 'base':base([mat(baseColorTexture={'index':0})],[GRAY]),
 'mr':base([mat(metallicRoughnessTexture={'index':0})],[MR]),
 'ao':base([dict(mat(),occlusionTexture={'index':0})],[AO]),
 'independent':base([dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1}),occlusionTexture={'index':2})],[WHITE,MR,AO]),
 'all':base([dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1}),occlusionTexture={'index':2},normalTexture={'index':3},emissiveTexture={'index':4},emissiveFactor=[.25,.25,.25])],[WHITE,MR,AO,NORMAL,EMISSION]),
 'default':base(), 'empty-pbr':base([{}]),
 'sharing':base([dict(mat(baseColorTexture={'index':0}),emissiveTexture={'index':1},emissiveFactor=[.25,.25,.25],occlusionTexture={'index':2})],[GRAY],textures=[{'source':0,'sampler':0}]*3),
 'samplers':base([dict(mat(baseColorTexture={'index':0}),emissiveTexture={'index':1},emissiveFactor=[.25,.25,.25])],[GRAY],samplers=[{'magFilter':9728,'minFilter':9728},{'magFilter':9729,'minFilter':9729}],textures=[{'source':0,'sampler':0},{'source':0,'sampler':1}]),
 'double':base([dict(mat(),doubleSided=True)]),
}
for name,(d,b) in valid.items(): write(name,d,b)
d,b=copy.deepcopy(valid['base']);d['meshes'][0]['primitives'].append(copy.deepcopy(d['meshes'][0]['primitives'][0]));write('two',d,b)
# Cases exercised by staging, not pure JSON/geometry parsing.
d,b=valid['all']; d=copy.deepcopy(d);d['meshes'][0]['primitives'][0]['attributes'].pop('TANGENT');write('no-tangent',d,b)
d,b=valid['base'];d=copy.deepcopy(d);attrs=d['meshes'][0]['primitives'][0]['attributes'];attrs.pop('NORMAL');attrs.pop('TANGENT');write('no-normal',d,b)
d,b=valid['base'];d=copy.deepcopy(d);attrs=d['meshes'][0]['primitives'][0]['attributes'];attrs.pop('TEXCOORD_0');attrs.pop('TANGENT');write('no-uv',d,b)
broken=GRAY[:33]+b'broken IDAT payload'
d,b=base([dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1}))],[WHITE,broken]);write('broken-png',d,b)
large=png(2048,2048,(255,255,255,255))
samplers=[{'minFilter':9987,'wrapS':10497,'wrapT':10497},{'minFilter':9987,'wrapS':33071,'wrapT':10497},{'minFilter':9987,'wrapS':10497,'wrapT':33071},{'minFilter':9984,'wrapS':10497,'wrapT':10497}]
d,b=base([dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1}),normalTexture={'index':2},occlusionTexture={'index':3})],[large],samplers=samplers,textures=[{'source':0,'sampler':i} for i in range(4)]);write('gpu-budget',d,b)
d,b=base([dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1}),occlusionTexture={'index':2})],[large]*3);write('decode-budget',d,b)
# Pure-format rejection cases; every unsupported value has a specific diagnostic.
bad=[]
def reject(name, mutation, needle):
    d,b=copy.deepcopy(valid['all']);d,b=mutation(d,b);write('bad-'+name,d,b);bad.append(('bad-'+name+'.glb',needle))
def change(fn):
    def edit(d,b): fn(d);return d,b
    return edit
reject('alpha',change(lambda d:d['materials'][0].update(alphaMode='MASK')),'only supports OPAQUE')
reject('blend',change(lambda d:d['materials'][0].update(alphaMode='BLEND')),'only supports OPAQUE')
reject('base-factor',change(lambda d:d['materials'][0]['pbrMetallicRoughness'].update(baseColorFactor=[2,1,1,1])),'baseColorFactor')
reject('base-shape',change(lambda d:d['materials'][0]['pbrMetallicRoughness'].update(baseColorFactor=[1,1,1])),'array outside')
reject('metallic',change(lambda d:d['materials'][0]['pbrMetallicRoughness'].update(metallicFactor=-.1)),'material number')
reject('roughness',change(lambda d:d['materials'][0]['pbrMetallicRoughness'].update(roughnessFactor=1.1)),'material number')
reject('emission',change(lambda d:d['materials'][0].update(emissiveFactor=[0,0,2])),'emissiveFactor')
reject('normal-scale',change(lambda d:d['materials'][0]['normalTexture'].update(scale=9)),'material number')
reject('ao-strength',change(lambda d:d['materials'][0]['occlusionTexture'].update(strength=-1)),'material number')
reject('double-type',change(lambda d:d['materials'][0].update(doubleSided=1)),'not a bool')
reject('uv-set',change(lambda d:d['materials'][0]['normalTexture'].update(texCoord=1)),'only supports TEXCOORD_0')
reject('texture-index',change(lambda d:d['materials'][0]['normalTexture'].update(index=99)),'integer outside')
reject('missing-index',change(lambda d:d['materials'][0]['normalTexture'].pop('index')),'requires index')
reject('empty-key',change(lambda d:d['materials'][0]['pbrMetallicRoughness']['baseColorTexture'].update({'':1})),'unsupported property')
reject('material-index',change(lambda d:d['meshes'][0]['primitives'][0].update(material=100)),'integer outside')
reject('mime',change(lambda d:d['images'][0].update(mimeType='image/webp')),'requires image/png or image/jpeg')
reject('uri',change(lambda d:d['images'][0].update(uri='https://invalid.example/image.png')),'external image URI')
reject('image-view',change(lambda d:d['images'][0].update(bufferView=100)),'integer outside')
reject('image-stride',change(lambda d:d['bufferViews'][2].update(byteStride=4)),'image bufferView')
reject('image-target',change(lambda d:d['bufferViews'][2].update(target=34962)),'image bufferView')
reject('image-vertex-overlap',change(lambda d:(d['bufferViews'][0].pop('byteStride'),d['bufferViews'][0].pop('target'),d['images'][0].update(bufferView=0))),'incompatible vertex attribute')
reject('source',change(lambda d:d['textures'][0].update(source=100)),'integer outside')
reject('missing-source',change(lambda d:d['textures'][0].pop('source')),'requires an embedded image')
reject('sampler-index',change(lambda d:d['textures'][0].update(sampler=100)),'integer outside')
reject('min-filter',change(lambda d:d['samplers'][0].update(minFilter=10000)),'unsupported sampler')
reject('mag-filter',change(lambda d:d['samplers'][0].update(magFilter=1)),'integer outside')
reject('mirror',change(lambda d:d['samplers'][0].update(wrapS=33648)),'unsupported sampler')
reject('extension',change(lambda d:d['materials'][0].update(extensions={'KHR_materials_unlit':{}})),'unsupported object extension')
reject('many-materials',change(lambda d:d.update(materials=[{}]*129)),'array outside')
reject('many-images',change(lambda d:d.update(images=[d['images'][0]]*33)),'array outside')
reject('name-type',change(lambda d:d['materials'][0].update(name=7)),'json:')
reject('alpha-cutoff',change(lambda d:d['materials'][0].update(alphaCutoff=-.1)),'alphaCutoff')
# Repeated overlapping image records must not multiply the encoded-data budget.
d,b=base([mat()],[b'\x89PNG\r\n\x1a\n'+b'x'*(3000000-8)]);d['images']*=3;write('bad-image-copy-budget',d,b);bad.append(('bad-image-copy-budget.glb','embedded image byte budget'))
(OUT/'reject-list.txt').write_text(''.join(name+'|'+needle+'\n' for name,needle in bad))
# Original demonstration: eight named materials, embedded PNGs, shared geometry.
def panel_pixels(kind):
    values=[]
    for y in range(64):
        for x in range(64):
            u=(x%16+.5)/16*2*math.pi;v=(y%16+.5)/16*2*math.pi
            seam=x%16<2 or y%16<2;tile=(x//16+y//16)%2
            if kind==0: rgb=(30,130,185) if tile==0 else (200,110,40);rgb=(12,24,34) if seam else rgb
            elif kind==1: rgb=(0,70,230) if tile==0 else (0,220,20)
            elif kind==2: rgb=(45,255,0) if seam else (255,0,255)
            elif kind==3:
                rgb=(0,0,0)
                if 5<=x%16<=11 and 7<=y%16<=8:rgb=(0,180,255) if tile==0 else (255,120,20)
            else:
                n=(-.65*math.sin(u)*(1-math.cos(v)),-.65*math.sin(v)*(1-math.cos(u)),1)
                length=math.sqrt(sum(a*a for a in n));rgb=tuple(round((a/length*.5+.5)*255) for a in n)
            values.extend((*rgb,255))
    return values
imgs=[png(64,64,panel_pixels(i)) for i in range(5)]
mats=[mat(baseColorFactor=[.6,.15,.04,1]),mat(baseColorTexture={'index':0}),mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1},metallicFactor=1),
      dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1},metallicFactor=1),occlusionTexture={'index':2}),
      dict(mat(baseColorTexture={'index':0}),normalTexture={'index':4,'scale':1.5}),
      dict(mat(baseColorFactor=[0,0,0,1]),emissiveTexture={'index':3},emissiveFactor=[1,1,1]),
      dict(mat(baseColorTexture={'index':0},metallicRoughnessTexture={'index':1},metallicFactor=1),occlusionTexture={'index':2},normalTexture={'index':4},emissiveTexture={'index':3},emissiveFactor=[.6,.6,.6]),
      dict(mat(baseColorFactor=[.03,.4,.6,1]),doubleSided=True)]
for i,m in enumerate(mats):m['name']=['Factor','Color','MR','MR+AO','Normal','Emission','Five maps','Back face'][i]
d,b=base(mats,imgs,samplers=[{}],z=0)
primitive=copy.deepcopy(d['meshes'][0]['primitives'][0]);d['meshes']=[];d['nodes']=[{'name':'Material panels','children':list(range(1,9))}]
for i,m in enumerate(mats):
    p=copy.deepcopy(primitive);p['material']=i;d['meshes'].append({'primitives':[p]})
    node={'name':m['name'],'mesh':i,'translation':[(i%4-1.5)*2.1,(.5-i//4)*2.1,0]}
    if i==7:node['rotation']=[0,1,0,0]
    d['nodes'].append(node)
asset=ROOT/'examples/glb_materials/assets/panels.glb';asset.parent.mkdir(parents=True,exist_ok=True)
raw=glb(d,b)
if asset.exists():assert asset.read_bytes()==raw,'original source asset differs from authored reference'
else:asset.write_bytes(raw)
print(f'GLB material fixtures: {len(bad)} strict rejects; source panels.glb {len(raw)} bytes, 8 surfaces / 16 triangles / 5 embedded images')

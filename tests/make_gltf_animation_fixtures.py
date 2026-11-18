"""Analytic LINEAR/STEP/cubic and skin fixtures, plus hostile/invalid resources."""
from pathlib import Path
import copy,json,struct,zlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/gltf-animation-fixtures';OUT.mkdir(parents=True,exist_ok=True)
data=bytearray();views=[];accessors=[]
def accessor(values,kind,components=5126,bounds=False,target=0):
 while len(data)%4:data.append(0)
 code={5126:'f',5123:'H',5121:'B'}[components];offset=len(data)
 for row in values:data.extend(struct.pack('<'+code*len(row),*row))
 view={'buffer':0,'byteOffset':offset,'byteLength':len(data)-offset}
 if target:view['target']=target
 views.append(view);a={'bufferView':len(views)-1,'componentType':components,'count':len(values),'type':kind}
 if bounds:a.update(min=list(map(min,zip(*values))),max=list(map(max,zip(*values))))
 accessors.append(a);return len(accessors)-1
p=accessor([[-.4,-.4,0],[.4,-.4,0],[0,.4,0]],'VEC3',bounds=True,target=34962)
n=accessor([[0,0,1]]*3,'VEC3',target=34962)
uv=accessor([[0,0],[1,0],[.5,1]],'VEC2',target=34962)
j=accessor([[0,0,0,0]]*3,'VEC4',5121,target=34962)
w=accessor([[1,0,0,0]]*3,'VEC4',target=34962)
ibm=accessor([[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]],'MAT4')
times=accessor([[0],[1]],'SCALAR',bounds=True)
linear=accessor([[0,0,0],[2,0,0]],'VEC3')
cubic=accessor([[0,0,0],[0,0,0],[0,0,0],[0,0,0],[2,0,0],[0,0,0]],'VEC3')
rotation=accessor([[0,0,0,1],[0,0,1,0]],'VEC4')
antipodal=accessor([[0,0,0,1],[0,0,0,-1]],'VEC4')
doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(data)}],'bufferViews':views,'accessors':accessors,
 'meshes':[{'primitives':[{'attributes':{'POSITION':p,'NORMAL':n,'TEXCOORD_0':uv,'JOINTS_0':j,'WEIGHTS_0':w}}]}],
 'nodes':[{'children':[1,2]},{'name':'joint'},{'mesh':0,'skin':0}], 'scenes':[{'nodes':[0]}],'scene':0,
 'skins':[{'joints':[1],'inverseBindMatrices':ibm}],'animations':[]}
for name,mode,out,path in [('linear','LINEAR',linear,'translation'),('step','STEP',linear,'translation'),('cubic','CUBICSPLINE',cubic,'translation'),('rotation','LINEAR',rotation,'rotation'),('antipodal','LINEAR',antipodal,'rotation')]:
 doc['animations'].append({'name':name,'samplers':[{'input':times,'output':out,'interpolation':mode}],'channels':[{'sampler':0,'target':{'node':1,'path':path}}]})
def write(name,d=doc,b=data):
 js=json.dumps(d,separators=(',',':')).encode();js+=b' '*((-len(js))%4);binary=bytes(b);binary+=b'\0'*((-len(binary))%4)
 (OUT/name).write_bytes(struct.pack('<III',0x46546c67,2,28+len(js)+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary)
write('analytic.glb');rejects=[]
def bad(name,change=None,patch=None):
 d=copy.deepcopy(doc);b=bytearray(data)
 if change:change(d)
 if patch:patch(b)
 write('reject-'+name+'.glb',d,b);rejects.append('reject-'+name+'.glb')
bad('time-order',patch=lambda b:struct.pack_into('<f',b,views[times]['byteOffset']+4,0))
bad('negative-time',patch=lambda b:struct.pack_into('<f',b,views[times]['byteOffset'],-1))
bad('nonfinite-key',patch=lambda b:struct.pack_into('<f',b,views[linear]['byteOffset'],float('nan')))
bad('joint-index',patch=lambda b:struct.pack_into('<B',b,views[j]['byteOffset'],1))
bad('weight-total',patch=lambda b:struct.pack_into('<f',b,views[w]['byteOffset'],0))
bad('weight-negative',patch=lambda b:struct.pack_into('<f',b,views[w]['byteOffset'],-1))
bad('weight-missing',change=lambda d:d['meshes'][0]['primitives'][0]['attributes'].pop('WEIGHTS_0'))
bad('skin-joints',change=lambda d:d['skins'][0].update(joints=[1,1]))
bad('skin-node',change=lambda d:d['nodes'][2].update(skin=1))
bad('skin-matrix',patch=lambda b:struct.pack_into('<f',b,views[ibm]['byteOffset']+60,2))
bad('skin-singular',patch=lambda b:struct.pack_into('<f',b,views[ibm]['byteOffset'],0))
bad('channel-duplicate',change=lambda d:d['animations'][0]['channels'].append(copy.deepcopy(d['animations'][0]['channels'][0])))
bad('channel-node',change=lambda d:d['animations'][0]['channels'][0]['target'].update(node=100))
bad('channel-morph',change=lambda d:d['animations'][0]['channels'][0]['target'].update(path='weights'))
bad('sampler-count',change=lambda d:d['accessors'][linear].update(count=1))
bad('sampler-mode',change=lambda d:d['animations'][0]['samplers'][0].update(interpolation='bad'))
bad('rotation-unit',patch=lambda b:struct.pack_into('<f',b,views[rotation]['byteOffset']+12,2))
bad('matrix-target',change=lambda d:d['nodes'][1].update(matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]))
bad('unknown-required',change=lambda d:d.update(extensionsRequired=['UNKNOWN']))
for i,uri in enumerate(('../escape.png','/absolute.png','https://host/x.png','Textures/%2e%2e/x.png','Textures/./x.png','Textures//x.png','Textures\\x.png','image.webp')):
 bad('image-uri-'+str(i),change=lambda d,u=uri:d.update(images=[{'uri':u}]))
external=copy.deepcopy(doc);external['images']=[{'uri':'Textures/map.png'}];write('external.glb',external)
def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0\xff'))+chunk(b'IEND',b'')
(OUT/'Textures').mkdir(exist_ok=True);(OUT/'Textures/map.png').write_bytes(png)
(OUT/'reject-list.txt').write_text('\n'.join(rejects)+'\n')
print('Prepared analytic skin and LINEAR/STEP/cubic/shortest-quaternion animation fixtures;',len(rejects),'rejects')

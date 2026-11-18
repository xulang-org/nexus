"""Original cross-format solids, independent writers and malformed import corpus."""
from pathlib import Path
import json,math,struct
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/mesh-format-fixtures';OUT.mkdir(parents=True,exist_ok=True)
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def sub(a,b):return [x-y for x,y in zip(a,b)]
def normal(p):
 n=cross(sub(p[1],p[0]),sub(p[2],p[0]));length=math.sqrt(sum(x*x for x in n));return [x/length for x in n]
def obj(vertices,faces):
 return '# Xu original model\r\no mesh\r\ng geometry\r\ns off\r\n'+''.join('v '+' '.join(map(str,v))+'\r\n' for v in vertices)+''.join('f '+' '.join(str(i+1) for i in f)+'\r\n' for f in faces)
def triangles(faces):return [(f[0],f[i],f[i+1]) for f in faces for i in range(1,len(f)-1)]
def stla(vertices,faces):
 out='solid Xu original\n'
 for f in triangles(faces):
  p=[vertices[i] for i in f]
  out+='facet normal 0 0 0\n outer loop\n'+''.join(' vertex '+' '.join(map(str,v))+'\n' for v in p)+' endloop\nendfacet\n'
 return out+'endsolid Xu original\n'
def stlb(vertices,faces,solid=False):
 ts=triangles(faces);header=b'solid opaque binary header' if solid else b'Xu original binary STL'
 out=header.ljust(80,b' ')+struct.pack('<I',len(ts))
 for f in ts:
  p=[vertices[i] for i in f]
  out+=struct.pack('<12fH',*normal(p),*(x for v in p for x in v),0)
 return out
def glb(vertices,faces):
 index=[i for f in triangles(faces) for i in f]
 positions=b''.join(struct.pack('<3f',*v) for v in vertices)
 data=positions+struct.pack('<'+'H'*len(index),*index)
 doc=dict(asset={'version':'2.0','generator':'Xu original cross-format fixture'},buffers=[{'byteLength':len(data)}],
  bufferViews=[{'buffer':0,'byteOffset':0,'byteLength':len(positions)},{'buffer':0,'byteOffset':len(positions),'byteLength':len(index)*2}],
  accessors=[{'bufferView':0,'componentType':5126,'count':len(vertices),'type':'VEC3','min':list(map(min,zip(*vertices))),'max':list(map(max,zip(*vertices)))},
             {'bufferView':1,'componentType':5123,'count':len(index),'type':'SCALAR'}],
  meshes=[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],nodes=[{'mesh':0}],scenes=[{'nodes':[0]}],scene=0)
 js=json.dumps(doc,separators=(',',':')).encode();js+=b' '*((-len(js))%4);data+=b'\0'*((-len(data))%4)
 return struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(data))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(data),0x004e4942)+data
models={
 'triangle':([[-1,-1,0],[1,-1,0],[0,1,0]],[[0,1,2]]),
 'cube':([[-.75,-.75,-.75],[.75,-.75,-.75],[.75,.75,-.75],[-.75,.75,-.75],[-.75,-.75,.75],[.75,-.75,.75],[.75,.75,.75],[-.75,.75,.75]],
         [[4,5,6,7],[1,0,3,2],[0,4,7,3],[5,1,2,6],[3,7,6,2],[0,1,5,4]]),
 'tetrahedron':([[.25,1.125,-.125],[-1,-.75,.75],[1,-.75,.75],[0,-.75,-1]],[[0,1,2],[0,2,3],[0,3,1],[1,3,2]])}
for name,(vertices,faces) in models.items():
 (OUT/(name+'.obj')).write_bytes(obj(vertices,faces).encode())
 (OUT/(name+'.ascii.stl')).write_text(stla(vertices,faces))
 (OUT/(name+'.binary.stl')).write_bytes(stlb(vertices,faces))
 (OUT/(name+'.solid-header.stl')).write_bytes(stlb(vertices,faces,True))
 (OUT/(name+'.glb')).write_bytes(glb(vertices,faces))
base='v -1 -1 0\nv 1 -1 0\nv 0 1 0\n'
(OUT/'negative.obj').write_text(base+'vt 0\nvt 1 0 0\nvt .5 1\nvn 0 0 2\ns 1\nf -3/-3/-1 -2/-2/-1 -1/-1/-1\n')
(OUT/'normal-only.obj').write_text(base+'vn 0 0 3\nf 1//1 2//1 3//1\n')
(OUT/'uv-only.obj').write_text(base+'vt 0 0\nvt 1 0\nvt .5 1\nf 1/1 2/2 3/3\n')
(OUT/'seam.obj').write_text('v -1 -1 0\nv 1 -1 0\nv 1 1 0\nv -1 1 0\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nvt .5 .5\nf 1/1 2/2 3/3\nf 1/5 3/3 4/4\n')
(OUT/'uppercase.OBJ').write_text(base+'f 1 2 3\n')
rejects=[]
def bad(name,data):
 path=OUT/name;path.write_bytes(data.encode() if isinstance(data,str) else data);rejects.append(name)
for name,text in {
 'zero-index':base+'f 0 2 3\n','negative-index':base+'f -4 -2 -1\n','min-index':base+'f -9223372036854775808 2 3\n',
 'forward':'f 1 2 3\n'+base,'huge-index':base+'f 9223372036854775808 2 3\n',
 'arity':base+'f 1 2\n','corner':base+'f 1/ 2/ 3/\n','empty-normal':base+'f 1// 2// 3//\n',
 'mixed':base+'vt 0 0\nf 1/1 2 3\n','smooth-missing':base+'s 1\nf 1 2 3\n',
 'zero-normal':base+'vn 0 0 0\nf 1//1 2//1 3//1\n','weight':'v 0 0 0 2\n'+base+'f 2 3 4\n',
 'nonfinite':'v nan 0 0\n'+base+'f 2 3 4\n','large':'v 1000000001 0 0\n'+base+'f 2 3 4\n',
 'uv3d':base+'vt 0 0 1\nf 1/1 2/1 3/1\n','colors':'v 0 0 0 1 0 0\n'+base+'f 2 3 4\n',
 'ngon':'v 0 0 0\nv 2 0 0\nv 3 1 0\nv 1 3 0\nv -1 1 0\nf 1 2 3 4 5\n',
 'concave':'v 0 0 0\nv 2 0 0\nv .5 .5 0\nv 0 2 0\nf 1 2 3 4\n',
 'crossed':'v 0 0 0\nv 2 2 0\nv 0 2 0\nv 2 0 0\nf 1 2 3 4\n',
 'nonplanar':'v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 1\nf 1 2 3 4\n',
 'degenerate':'v 0 0 0\nv 1 0 0\nv 2 0 0\nf 1 2 3\n',
 'empty':'# no geometry\n','line-limit':'#'+'x'*65536+'\n'+base+'f 1 2 3\n',
 'material':base+'mtllib missing.mtl\nf 1 2 3\n','usemtl':base+'usemtl material\nf 1 2 3\n',
 'command':base+'csh echo should-not-run\nf 1 2 3\n','include':base+'call external.obj\nf 1 2 3\n',
 'continuation':base+'f 1 2 \\\n3\n'}.items():bad('reject-'+name+'.obj',text)
bad('reject-nul.obj',(base+'f 1 2 3\n').encode()+b'\0');bad('reject-utf8.obj',b'\xff'+base.encode())
a=stla(*models['triangle']);b=stlb(*models['triangle'])
for name,data in {
 'truncated':a.replace('endfacet\n',''),'no-loop':a.replace('outer loop','outer other'),'extra-vertex':a.replace(' endloop',' vertex 0 0 0\n endloop'),
 'name':a.replace('endsolid Xu original','endsolid wrong'),'trailing':a+'solid second\nendsolid second\n',
 'nan':a.replace('normal 0 0 0','normal NaN 0 0'),'degenerate':a.replace('vertex 1 -1 0','vertex -1 -1 0'),
 'empty':'solid nothing\nendsolid nothing\n'}.items():bad('reject-ascii-'+name+'.stl',data)
bad('reject-binary-truncated.stl',b[:-1]);bad('reject-binary-count.stl',b[:80]+struct.pack('<I',2)+b[84:]);bad('reject-binary-attribute.stl',b[:-2]+b'\x01\0')
bad('reject-binary-nan.stl',b[:84]+struct.pack('<f',float('nan'))+b[88:])
bad('reject-binary-large.stl',b[:96]+struct.pack('<f',1e10)+b[100:])
# Dispatch rejects these before opening or invoking any external application.
for ext in ('fbx','ply','dae','blend','gltf'):(OUT/('unsupported.'+ext)).write_text('unsupported input')
(OUT/'reject-list.txt').write_text('\n'.join(rejects)+'\n')
(OUT/'manifest.json').write_text(json.dumps({'models':{name:{'triangles':len(triangles(faces)),'bounds':[list(map(min,zip(*v))),list(map(max,zip(*v)))]} for name,(v,faces) in models.items()},'rejects':len(rejects)},indent=2)+'\n')
# Product demo input is an original, self-contained OBJ without sidecars.
asset=ROOT/'examples/model_formats/assets/cube.obj';asset.parent.mkdir(parents=True,exist_ok=True);asset.write_text(obj(*models['cube']))
print('Prepared 3 original solids in GLB/OBJ/ASCII-STL/binary-STL plus solid-header variants;',len(rejects),'rejects')

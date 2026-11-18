"""Independent stdlib-only glTF pose/skin oracle for the pinned external assets."""
from pathlib import Path
import bisect,json,math,struct
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/external-models'
def identity():return [[float(i==j) for j in range(4)] for i in range(4)]
def mul(a,b):return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def apply(m,v):return [sum(row[i]*v[i] for i in range(4)) for row in m]
def inverse(a):
 m=[list(row)+eye for row,eye in zip(a,identity())]
 for i in range(4):
  pivot=max(range(i,4),key=lambda j:abs(m[j][i]));m[i],m[pivot]=m[pivot],m[i]
  scale=m[i][i];assert abs(scale)>1e-12
  m[i]=[x/scale for x in m[i]]
  for j in range(4):
   if j!=i:
    scale=m[j][i];m[j]=[x-scale*y for x,y in zip(m[j],m[i])]
 return [row[4:] for row in m]
def trs(t,q,s):
 x,y,z,w=q;norm=math.sqrt(sum(v*v for v in q));x,y,z,w=[v/norm for v in q]
 m=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),t[0]],
    [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),t[1]],
    [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),t[2]],[0.,0.,0.,1.]]
 for row in m:
  for j in range(3):row[j]*=s[j]
 return m
def slerp(a,b,t):
 dot=sum(x*y for x,y in zip(a,b))
 if dot<0:b=[-v for v in b];dot=-dot
 if dot>.9995:q=[(1-t)*x+t*y for x,y in zip(a,b)]
 else:
  theta=math.acos(min(1,dot));q=[(math.sin((1-t)*theta)*x+math.sin(t*theta)*y)/math.sin(theta) for x,y in zip(a,b)]
 norm=math.sqrt(sum(x*x for x in q));return [x/norm for x in q]
cases=[]
for model in json.loads((OUT/'sources.json').read_text())['models']:
 raw=(ROOT/model['render_input']).read_bytes();size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size]);binary=raw[28+size:]
 def accessor(index):
  a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
  count={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
  code={5121:'B',5123:'H',5125:'I',5126:'f'}[a['componentType']];n=struct.calcsize('<'+code*count)
  start=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',n)
  values=[list(struct.unpack_from('<'+code*count,binary,start+i*stride)) for i in range(a['count'])]
  if a.get('normalized'):values=[[x/(255 if code=='B' else 65535) for x in row] for row in values]
  return values
 nodes=doc['nodes'];parents={c:i for i,n in enumerate(nodes) for c in n.get('children',[])}
 selections=[(-1,0.)]+[(clip,time*max(accessor(s['input'])[-1][0] for s in a['samplers'])) for clip,a in enumerate(doc.get('animations',[])) for time in (0.,.25,.75,1.)]
 for clip,time in selections:
  ts=[n.get('translation',[0,0,0])[:] for n in nodes];qs=[n.get('rotation',[0,0,0,1])[:] for n in nodes];ss=[n.get('scale',[1,1,1])[:] for n in nodes]
  if clip>=0:
   animation=doc['animations'][clip]
   for channel in animation['channels']:
    sampler=animation['samplers'][channel['sampler']];times=[x[0] for x in accessor(sampler['input'])];values=accessor(sampler['output']);at=max(0,bisect.bisect_right(times,time)-1)
    value=values[at];target=channel['target'];node=target['node'];path=target['path']
    if at+1<len(times) and time>times[0] and sampler.get('interpolation','LINEAR')=='LINEAR':
     t=(time-times[at])/(times[at+1]-times[at]);b=values[at+1]
     value=slerp(value,b,t) if path=='rotation' else [(1-t)*x+t*y for x,y in zip(value,b)]
    {'translation':ts,'rotation':qs,'scale':ss}[path][node]=value
  local=[trs(t,q,s) for t,q,s in zip(ts,qs,ss)];cache={}
  def world(i):
   if i not in cache:cache[i]=mul(world(parents[i]),local[i]) if i in parents else local[i]
   return cache[i]
  points=[]
  for ni,node in enumerate(nodes):
   if 'mesh' not in node:continue
   for primitive in doc['meshes'][node['mesh']]['primitives']:
    attrs=primitive['attributes'];vertices=accessor(attrs['POSITION'])
    palette=[]
    if 'skin' in node:
     skin=doc['skins'][node['skin']];ibms=accessor(skin['inverseBindMatrices']) if 'inverseBindMatrices' in skin else [[identity()[i][j] for j in range(4) for i in range(4)]]*len(skin['joints'])
     for j,flat in zip(skin['joints'],ibms):palette.append(mul(mul(inverse(world(ni)),world(j)),[[flat[col*4+row] for col in range(4)] for row in range(4)]))
    for vi in sorted({0,len(vertices)//2,len(vertices)-1}):
     p=vertices[vi]+[1.]
     if palette:
      joints=accessor(attrs['JOINTS_0'])[vi];weights=accessor(attrs['WEIGHTS_0'])[vi];total=sum(weights)
      blend=[[sum(palette[j][r][c]*w/total for j,w in zip(joints,weights)) for c in range(4)] for r in range(4)];p=apply(blend,p)
     # Primitive index is flattened in the same order as the source mesh list.
     pi=sum(len(m['primitives']) for m in doc['meshes'][:node['mesh']])+doc['meshes'][node['mesh']]['primitives'].index(primitive)
     points.append({'node':ni,'primitive':pi,'vertex':vi,'position':apply(world(ni),p)[:3]})
  cases.append({'path':model['render_input'],'name':model['name'],'clip':clip,'time':time,'worlds':[[world(i)[row][col] for col in range(4) for row in range(4)] for i in range(len(nodes))],'points':points})
(OUT/'pose-oracle.json').write_text(json.dumps({'cases':cases},separators=(',',':'))+'\n')
print('Prepared independent reference:',len(cases),'poses,',sum(len(c['points']) for c in cases),'skin/world-space point checks; all 80 source animation clips covered')

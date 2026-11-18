from pathlib import Path
import hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/detail-models'
def unpack(path):
 raw=path.read_bytes();n=struct.unpack_from('<I',raw,12)[0];return json.loads(raw[20:20+n]),raw[28+n:]
def write(name,doc,data):
 js=json.dumps(doc,separators=(',',':')).encode();js+=b' '*((-len(js))%4);data+=b'\0'*((-len(data))%4)
 (OUT/name).write_bytes(struct.pack('<III',0x46546c67,2,28+len(js)+len(data))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(data),0x004e4942)+data)
doc,data=unpack(OUT/'head-prepared.glb')
doc['materials'][0]['normalTexture']['scale']=0
write('head-no-normal.glb',doc,data)
doc,data=unpack(OUT/'head-prepared.glb')
data=bytearray(data)
for image in doc['images']:
 while len(data)%4:data.append(0)
 raw=(OUT/image.pop('uri')).read_bytes();at=len(data);data.extend(raw)
 doc['bufferViews'].append({'buffer':0,'byteOffset':at,'byteLength':len(raw)})
 image['bufferView']=len(doc['bufferViews'])-1
doc['buffers'][0]['byteLength']=len(data)
write('head-embedded-jpeg.glb',doc,bytes(data))
results=[]
for name,model,scale,studio in [('baseline','head-prepared.glb',1,False),('detail','head-prepared.glb',2,True),('no-normal','head-no-normal.glb',2,True),('embedded','head-embedded-jpeg.glb',2,True)]:
 capture=OUT/('head-'+name+'.png');capture.unlink(missing_ok=True)
 run=subprocess.run([str(ROOT/'build/model-formats'),'--model',str(OUT/model),'--backend','metal','--view','pbr','--studio',str(studio).lower(),'--distance','3.2','--fov','40','--yaw','0.15','--pitch','0','--render-scale',str(scale),'--frames','1','--capture',str(capture)],cwd=ROOT,capture_output=True,text=True,timeout=60)
 assert run.returncode==0 and 'triangles=17684 frames=1' in run.stdout,run.stdout+run.stderr
 raw=capture.read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack_from('>II',raw,16)==(800,600)
 results.append({'mode':name,'capture':str(capture.relative_to(ROOT)),'sha256':hashlib.sha256(raw).hexdigest()})
assert (OUT/'head-detail.png').read_bytes()==(OUT/'head-embedded.png').read_bytes(),'Embedded and external JPEG must produce identical pixels'
assert (OUT/'head-detail.png').read_bytes()!=(OUT/'head-no-normal.png').read_bytes(),'Normal map must affect real GPU output'
assert (OUT/'head-detail.png').read_bytes()!=(OUT/'head-baseline.png').read_bytes()
(OUT/'render-results.json').write_text(json.dumps({'triangles':17684,'vertices':53052,'texture_size':[1024,1024],'results':results},indent=2)+'\n')
print('PASS: detailed scan/JPEG/MikkTSpace PBR on Metal, studio + 2x SSAA, normal-map control, identical embedded/external JPEG pixels')

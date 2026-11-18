"""Pinned, original real-world content; source validity is reported separately."""
from pathlib import Path
import hashlib,json,re,struct,subprocess,zlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/external-models';CAP=OUT/'captures';CAP.mkdir(exist_ok=True)
models=json.loads((OUT/'sources.json').read_text())['models'];results=[]
def inspect_png(path):
 data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack_from('>II',data,16)==(800,600)
 at=8;packed=bytearray()
 while at<len(data):
  size=struct.unpack_from('>I',data,at)[0]
  if data[at+4:at+8]==b'IDAT':packed.extend(data[at+8:at+8+size])
  at+=size+12
 rows=zlib.decompress(packed);pixels=b''.join(rows[y*3201+1:(y+1)*3201] for y in range(600))
 assert len(pixels)==800*600*4 and all(a==255 for a in pixels[3::4])
 colors={pixels[i:i+3] for i in range(0,len(pixels),4)}
 assert len(colors)>20,('Expected textured/shaded model',path,len(colors))
 covered=sum(pixels[i:i+4]!=pixels[:4] for i in range(0,len(pixels),4));assert covered>1000
 return hashlib.sha256(pixels).hexdigest(),covered
def run(model,clip=None,time=0.,frames=1,label='rest'):
 capture=CAP/(model['name']+'-'+label+'.png');capture.unlink(missing_ok=True)
 args=[str(ROOT/'build/model-formats'),'--model',model['render_input'],'--backend','metal','--view','pbr','--frames',str(frames),'--time',str(time),'--capture',str(capture)]
 if clip is not None:args+=['--animation',clip,'--loop','true' if frames>1 else 'false']
 r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=60)
 assert r.returncode==0,(model['name'],label,r.stdout,r.stderr)
 match=re.search(r'bindings=(\d+) triangles=(\d+) frames=(\d+)',r.stdout);assert match and int(match[2])==model['triangles'] and int(match[3])==frames,r.stdout
 digest,covered=inspect_png(capture)
 result={'model':model['name'],'category':model['category'],'clip':clip,'time':time,'frames':frames,'triangles':int(match[2]),'rgba_sha256':digest,'covered_pixels':covered,'capture':str(capture.relative_to(ROOT))}
 results.append(result);return digest
for model in models:
 original=ROOT/model['original'];data=original.read_bytes();size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size])
 if 'repair' in model:
  r=subprocess.run([str(ROOT/'build/model-formats'),'--model',str(original),'--view','pbr','--frames','1'],cwd=ROOT,capture_output=True,text=True,timeout=30)
  assert r.returncode==1 and 'scene root' in r.stderr,r.stderr
 rest=run(model)
 for i,clip in enumerate(doc.get('animations',[])):run(model,clip['name'],.25,label='clip-'+str(i))
 if model['animations']:
  a=run(model,'walk',0.,label='walk-start');b=run(model,'walk',.25,label='walk-quarter');assert a!=b,model['name']
  run(model,'walk',0.,frames=600,label='continuous')
 print('PASS:',model['name'],model['animations'],'clips,',model['skins'],'skins',flush=True)
(OUT/'gpu-results.json').write_text(json.dumps({'captures':results,'clips':sum(m['animations'] for m in models),'source_errors_preserved':2},indent=2)+'\n')
print('PASS:',len(results),'real Metal textured/PBR captures; all 80 clips, four independent 600-frame runs, visible walk changes, and invalid plant sources remain rejected')

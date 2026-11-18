"""Explicit online fetch; verify pinned CC0 archives and retain untouched sources."""
from pathlib import Path
import hashlib,json,re,struct,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/external-models';OUT.mkdir(parents=True,exist_ok=True)
PACKS={
 'mini-characters':('add348e98ab9e23d9973c4740ef2c5cceb229c742106aca2d56b30a8f1241bb7',['character-male-a','character-female-a'],'person'),
 'cube-pets':('b3bdc99a2ec92c687b875718c5d01e9231d2711ed0e2845f295b474bb42a1283',['animal-cat','animal-fox'],'animal'),
 'nature-kit':('fa7974a0d342bfe63c38664ba9f8ec1a4aab8ea25f099bdc56870e33588c4d9d',['tree_oak','flower_redA'],'plant')}
records=[]
for pack,(digest,names,category) in PACKS.items():
 archive=OUT/(pack+'.zip');page='https://kenney.nl/assets/'+pack
 if not archive.exists():
  html=urllib.request.urlopen(page,timeout=30).read().decode()
  ident=re.search("data-download-id='([^']+)'",html).group(1)
  request=urllib.request.Request('https://kenney.nl/download-link/'+ident,headers={'Referer':page,'User-Agent':'Mozilla/5.0'})
  link=json.load(urllib.request.urlopen(request,timeout=30))['url']
  request=urllib.request.Request(link,headers={'Referer':page,'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(request,timeout=40) as response:data=response.read(64*1024*1024+1)
  assert len(data)<=64*1024*1024,'Archive byte budget'
  archive.write_bytes(data)
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest,('Upstream archive changed; review before repinning',pack)
 with zipfile.ZipFile(archive) as z:
  original=OUT/'original'/pack;original.mkdir(parents=True,exist_ok=True)
  license_bytes=z.read('License.txt');assert b'CC0' in license_bytes
  (original/'License.txt').write_bytes(license_bytes)
  for name in names:
   member=next(p for p in z.namelist() if p.endswith('/'+name+'.glb'))
   raw=z.read(member);path=original/(name+'.glb');path.write_bytes(raw)
   size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size])
   for image in doc.get('images',[]):
    if 'uri' not in image:continue
    uri=image['uri'];parts=Path(uri).parts
    assert not Path(uri).is_absolute() and all(p not in ('.','..') for p in parts)
    target=original/uri;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(z.read(str(Path(member).parent/uri)))
   record={'name':name,'category':category,'creator':'Kenney','license':'CC0-1.0','source':page,
     'archive_sha256':digest,'member':member,'original':str(path.relative_to(ROOT)),
     'original_sha256':hashlib.sha256(raw).hexdigest(),'animations':len(doc.get('animations',[])),
     'skins':len(doc.get('skins',[])),'render_input':str(path.relative_to(ROOT)),
     'triangles':sum((doc['accessors'][p['indices']]['count'] if 'indices' in p else doc['accessors'][p['attributes']['POSITION']]['count'])//3 for node in doc['nodes'] if 'mesh' in node for p in doc['meshes'][node['mesh']]['primitives'])}
   if category=='plant':
    # These original exports list child 1 as a scene root while tmpParent 0
    # still owns it (Khronos SCENE_NON_ROOT_NODE). Keep the source rejected;
    # promote the existing identity parent as root in an explicitly named copy.
    assert doc['scenes'][doc.get('scene',0)]['nodes']==[1] and doc['nodes'][0]['children']==[1]
    assert doc['nodes'][0].get('translation',[0,0,0])==[0,0,0]
    assert doc['nodes'][0].get('rotation',[0,0,0,1])==[0,0,0,1]
    assert doc['nodes'][0].get('scale',[1,1,1])==[1,1,1]
    doc['scenes'][doc.get('scene',0)]['nodes']=[0]
    text=json.dumps(doc,separators=(',',':')).encode();text+=b' '*((-len(text))%4)
    tail=raw[20+size:]
    fixed=struct.pack('<III',0x46546c67,2,20+len(text)+len(tail))+struct.pack('<II',len(text),0x4e4f534a)+text+tail
    repaired=OUT/'repaired'/pack/(name+'.scene-root-fixed.glb');repaired.parent.mkdir(parents=True,exist_ok=True);repaired.write_bytes(fixed)
    record.update(render_input=str(repaired.relative_to(ROOT)),repair='Promote existing identity tmpParent 0 to scene root; geometry/material/BIN unchanged',repaired_sha256=hashlib.sha256(fixed).hexdigest())
   records.append(record)
(OUT/'sources.json').write_text(json.dumps({'models':records},indent=2)+'\n')
(OUT/'ATTRIBUTION.md').write_text('# External test models\n\nAll six models by Kenney, CC0-1.0. Original archive licenses retained alongside models.\n\n'+''.join('- '+r['name']+': '+r['source']+'\n' for r in records)+'\nPlant originals have SCENE_NON_ROOT_NODE; rendering uses separately named scene-root-fixed copies.\n')
print('Prepared six licensed external GLBs; untouched sources retained, two explicitly repaired plant copies')

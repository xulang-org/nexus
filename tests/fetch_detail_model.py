"""Pinned CC-BY scan and original JPEG maps; explicit online test fixture."""
from pathlib import Path
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/detail-models';OUT.mkdir(parents=True,exist_ok=True)
COMMIT='253fa7ad003181df28015efdb541c2916895a816'
FILES={'LeePerrySmith.glb':'402b8a8ac9f03232e6d64b5962929703a069daf99d3c49ac8eb0e48bedc9c576',
 'LeePerrySmith_License.txt':'7cf4da43a6ae6d32f7f7d063fe129a19468af6f4fe7c53b937f83959709fcb50',
 'Map-COL.jpg':'e976d73b31407f8d0967412bf468019ed26a5d5a32cf5811aabff7e816458a65',
 'Infinite-Level_02_Tangent_SmoothUV.jpg':'36925e51ad9b324b94e8faf4692da1b4132809f2762bb8d5bd549ffd215d4ca6'}
records=[]
for name,digest in FILES.items():
 path=OUT/name;url='https://raw.githubusercontent.com/mrdoob/three.js/'+COMMIT+'/examples/models/gltf/LeePerrySmith/'+name
 if not path.exists():
  with urllib.request.urlopen(url,timeout=30) as response:data=response.read(4194305)
  assert len(data)<=4194304;path.write_bytes(data)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
 records.append({'file':name,'url':url,'sha256':digest})
(OUT/'sources.json').write_text(json.dumps({'author':'Lee Perry-Smith / Infinite Realities','license':'CC-BY-3.0','upstream':'https://threejs.org/examples/webgl_materials_normalmap.html','files':records,
 'prepared_asset':'head-prepared.glb','preparation':'Unindex source triangles, normalize source normals, explicitly flip UV V to match upstream TextureLoader behavior, generate offline glTF MikkTSpace tangents with mikktspace 1.1.1, attach original JPEG color/normal maps to a metallic=0 roughness=0.6 PBR material. This is an explicit derived test asset, not an unchanged original GLB.'},indent=2)+'\n')
print('Verified pinned Lee Perry-Smith scan, license and two original 1K JPEG maps')

"""The same geometry through five import paths must produce identical GPU pixels."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'build/mesh-format-fixtures'
BINARY=Path(os.environ.get('XU_MODEL_DEMO',str(ROOT/'build/model-formats'))).resolve()
OUT=ROOT/'build/model-format-captures'
OUT.mkdir(parents=True,exist_ok=True)
manifest=json.loads((FIXTURES/'manifest.json').read_text())

def png_pixels(path):
    data=path.read_bytes()
    assert data[:8]==b'\x89PNG\r\n\x1a\n'
    assert struct.unpack_from('>II',data,16)==(800,600)
    assert data[24:29]==bytes([8,6,0,0,0]),'Expected RGBA8 PNG'
    packed=bytearray();at=8
    while at<len(data):
        size=struct.unpack_from('>I',data,at)[0]
        tag=data[at+4:at+8];body=data[at+8:at+8+size]
        assert zlib.crc32(tag+body)==struct.unpack_from('>I',data,at+8+size)[0]
        if tag==b'IDAT':packed.extend(body)
        at+=size+12
    rows=zlib.decompress(packed)
    assert len(rows)==600*(800*4+1)
    pixels=bytearray()
    for y in range(600):
        row=rows[y*(800*4+1):(y+1)*(800*4+1)]
        assert row[0]==0,'Capture encoder uses unfiltered scanlines'
        pixels.extend(row[1:])
    assert all(a==255 for a in pixels[3::4]),'Opaque preview expected'
    background=pixels[:4]
    covered=sum(pixels[i:i+4]!=background for i in range(0,len(pixels),4))
    assert 1000<covered<400000,covered
    return bytes(pixels),covered

results=[]
for name,model in manifest['models'].items():
    reference=None
    for suffix in ('.glb','.obj','.ascii.stl','.binary.stl','.solid-header.stl'):
        source=FIXTURES/(name+suffix);capture=OUT/(name+suffix+'.png')
        capture.unlink(missing_ok=True)
        run=subprocess.run([str(BINARY),'--model',str(source),'--frames','1','--capture',str(capture)],
                           cwd=ROOT,capture_output=True,text=True,timeout=60)
        assert run.returncode==0,run.stdout+run.stderr
        expected='Model format='+source.suffix+' bindings=1 triangles='+str(model['triangles'])+' frames=1'
        assert expected in run.stdout,run.stdout+run.stderr
        pixels,covered=png_pixels(capture)
        if reference is None:reference=pixels
        assert pixels==reference,(name,suffix,'Cross-format GPU pixel mismatch')
        results.append({'file':source.name,'triangles':model['triangles'],'covered_pixels':covered,
                        'rgba_sha256':hashlib.sha256(pixels).hexdigest()})
assert len({entry['rgba_sha256'] for entry in results})==len(manifest['models'])

# A failed import must return before shader/window/device creation. Invalid
# backend/shader paths make accidental continuation observable even on no GPU.
rejects=(FIXTURES/'reject-list.txt').read_text().splitlines()
rejects+=['unsupported.'+ext for ext in ('fbx','ply','dae','blend','gltf')]
rejects+=['missing.obj']
for name in rejects:
    capture=OUT/'rejected.png';capture.unlink(missing_ok=True)
    env=os.environ | {'XU_SDL_LIBRARY':'/nonexistent/model-format-SDL'}
    run=subprocess.run([str(BINARY),'--model',str(FIXTURES/name),'--shaders','/nonexistent/shaders',
                        '--frames','1','--capture',str(capture)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
    assert run.returncode==1 and run.stderr and 'Model format=' not in run.stdout,(name,run.stdout,run.stderr)
    assert 'shader' not in run.stderr.lower() and not capture.exists(),(name,run.stderr)
(OUT/'results.json').write_text(json.dumps({'captures':results,'rejected_before_device':len(rejects)},indent=2)+'\n')
print('PASS: 15 real GPU captures; triangle/cube/tetrahedron match pixel-for-pixel across GLB/OBJ/ASCII STL/binary STL/solid-header binary STL; '+str(len(rejects))+' invalid, missing or unsupported inputs fail before device creation')

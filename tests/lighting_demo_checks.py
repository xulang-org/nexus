"""Exercise all public source-mode switches and bounded GPU screenshot output."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import struct
import zlib

ROOT=Path(__file__).resolve().parents[1]
binary=Path(os.environ.get('XU_LIGHTING_DEMO',str(ROOT/'build/lighting'))).resolve()
digests=set()
for mode in ('none','directional','point','spot','all'):
    output=ROOT/'build'/('lighting-mode-'+mode+'.png')
    result=subprocess.run([str(binary),'--mode',mode,'--frames','1','--capture',str(output)],cwd=ROOT,
                          capture_output=True,text=True,check=True,timeout=60)
    assert 'Finished 1 light frames' in result.stdout,result.stdout+result.stderr
    raw=output.read_bytes()
    assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    offset=8;chunks=[];payload=bytearray();width=height=0
    while offset<len(raw):
        size=struct.unpack_from('>I',raw,offset)[0]
        kind=raw[offset+4:offset+8]
        data=raw[offset+8:offset+8+size]
        checksum=struct.unpack_from('>I',raw,offset+8+size)[0]
        assert zlib.crc32(kind+data)&0xffffffff==checksum
        chunks.append(kind)
        if kind==b'IHDR':
            width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data)
            assert (width,height)==(1100,720) and (depth,color,compression,filtering,interlace)==(8,6,0,0,0)
        if kind==b'IDAT':payload.extend(data)
        offset += size+12
    assert chunks==[b'IHDR',b'IDAT',b'IEND'] and offset==len(raw)
    pixels=zlib.decompress(payload)
    stride=width*4+1
    assert len(pixels)==stride*height
    for y in range(height):
        row=pixels[y*stride:(y+1)*stride]
        assert row[0]==0 and all(alpha==255 for alpha in row[4::4])
    digests.add(hashlib.sha256(pixels).digest())
assert len(digests)==5,'Each light mode must produce a distinct rendered image'
invalid=subprocess.run([str(binary),'--mode','invalid','--frames','1'],cwd=ROOT,capture_output=True,text=True,timeout=30)
assert invalid.returncode==1 and 'mode must be' in invalid.stderr,invalid.stdout+invalid.stderr
print('PASS: five distinct Metal light-mode screenshots, opaque PNG dimensions, bounded runs and invalid-mode rejection')

# A new GPU process must reproduce the saved authored lights and local poses.
# The saved spot-only mode keeps hidden directional/point sources in the file.
saved=ROOT/'build/lighting-persisted.xuscene'
before=ROOT/'build/lighting-persisted-before.png'
after=ROOT/'build/lighting-persisted-after.png'
subprocess.run([str(binary),'--mode','spot','--frames','3','--capture',str(before),'--save-scene',str(saved)],
               cwd=ROOT,check=True,capture_output=True,text=True,timeout=60)
data=json.loads(saved.read_text())
assert len(data['lights'])==4 and not data['resources']
assert [n['name'] for n in data['nodes']]==['Sources','Directional','Points','RedPoint','BluePoint','Spot']
assert data['nodes'][1]['visible'] is False and data['nodes'][2]['visible'] is False
subprocess.run([str(binary),'--scene',str(saved),'--frames','1','--capture',str(after)],
               cwd=ROOT,check=True,capture_output=True,text=True,timeout=60)
assert before.read_bytes()==after.read_bytes(),'Saved local light state must reproduce exactly in a new Metal process'
assert not list(saved.parent.glob(saved.name+'.tmp-*'))
print('PASS: scene file save/exit/fresh-process Metal restore reproduces PNG bytes exactly and preserves hidden local light attachments')

many=ROOT/'build/lighting-many.png'
many_scene=ROOT/'build/lighting-many.xuscene'
run=subprocess.run([str(binary),'--extra-lights','252','--frames','1','--capture',str(many),'--save-scene',str(many_scene)],
                   cwd=ROOT,check=True,capture_output=True,text=True,timeout=60)
assert many.read_bytes()==(ROOT/'build/lighting-mode-all.png').read_bytes()
match=re.search(r'Lighting submissions: draws=(\d+) candidates=(\d+) selected=(\d+) culled=(\d+)',run.stdout)
assert match,run.stdout
draws,candidates,selected,culled=map(int,match.groups())
assert draws==18 and candidates==18*256 and 0<selected<=18*4 and culled==candidates-selected
assert len(json.loads(many_scene.read_text())['lights'])==256
reloaded=ROOT/'build/lighting-many-reloaded.png'
subprocess.run([str(binary),'--scene',str(many_scene),'--frames','1','--capture',str(reloaded)],
               cwd=ROOT,check=True,capture_output=True,text=True,timeout=60)
assert reloaded.read_bytes()==many.read_bytes()
failed=subprocess.run([str(binary),'--extra-lights','253','--frames','1'],cwd=ROOT,capture_output=True,text=True,timeout=30)
assert failed.returncode==1 and '256-source scene budget' in failed.stderr
print('PASS: 256-light demo tests 4608 candidates, selects at most 72 source records, reproduces baseline PNG exactly, saves/restores all lights and rejects excess budget')

culled_image=ROOT/'build/lighting-distant.png'
culled=subprocess.run([str(binary),'--extra-lights','252','--distant-meshes','128','--frames','1','--capture',str(culled_image)],
                      cwd=ROOT,check=True,capture_output=True,text=True,timeout=60)
assert culled_image.read_bytes()==many.read_bytes()
assert 'Scene visibility: submitted=18 culled=128' in culled.stdout,culled.stdout
assert 'Lighting submissions: draws=18 candidates=4608' in culled.stdout,culled.stdout
print('PASS: 128 distant shared-mesh instances are culled with identical PNG bytes and no additional material/light submissions')

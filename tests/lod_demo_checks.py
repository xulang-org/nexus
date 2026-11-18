"""Real Metal distance LOD and fixed-high comparison with bounded native runs."""
from pathlib import Path
import os
import re
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[1]
binary=Path(os.environ.get('XU_LOD_DEMO',str(ROOT/'build/lod'))).resolve()
results=[]
for mode,distance,levels,triangles,saved,coarse in [
    ('lod',6,(15,0,0),33120,0,0),
    ('lod',18,(0,15,0),3360,29760,15),
    ('lod',36,(0,0,15),720,32400,15),
    ('high',36,(0,0,0),33120,0,0),
]:
    output=ROOT/'build'/('lod-'+mode+'-'+str(distance)+'.png')
    run=subprocess.run([str(binary),'--mode',mode,'--distance',str(distance),'--frames','3','--capture',str(output)],
                       cwd=ROOT,capture_output=True,text=True,check=True,timeout=60)
    assert 'Finished 3 LOD frames' in run.stdout,run.stdout+run.stderr
    match=re.search(r'LOD result: levels=(\d+),(\d+),(\d+) submitted=(\d+) triangles=(\d+) saved=(\d+) coarse=(\d+) culled=(\d+) mode=(\w+)',run.stdout)
    assert match,run.stdout
    assert tuple(map(int,match.groups()[:8]))==(*levels,15,triangles,saved,coarse,0),run.stdout
    assert match[9]==mode
    data=output.read_bytes()
    assert data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack_from('>II',data,16)==(1100,720)
    offset=8;packed=bytearray()
    while offset<len(data):
        size=struct.unpack_from('>I',data,offset)[0]
        if data[offset+4:offset+8]==b'IDAT':packed.extend(data[offset+8:offset+8+size])
        offset+=size+12
    pixels=zlib.decompress(packed)
    assert len(pixels)==(1100*4+1)*720
    colors=set()
    for y in range(720):
        row=pixels[y*(1100*4+1)+1:(y+1)*(1100*4+1)]
        assert all(alpha==255 for alpha in row[3::4])
        colors.update(row[x:x+3] for x in range(0,len(row),4))
    assert len(colors)>10,'Expected nonblank GPU material output'
    results.append((mode,distance,triangles,saved))
for args in [('--mode','bad'),('--distance','2'),('--distance','61'),('--distance','NaN')]:
    failed=subprocess.run([str(binary),*args,'--frames','1'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert failed.returncode==1 and failed.stderr,args
print('PASS: real LOD demo selects 15 high/medium/low meshes at near/middle/far distances; 33120/3360/720 submitted triangles, fixed-high baseline, opaque nonblank PNGs and invalid CLI rejection')

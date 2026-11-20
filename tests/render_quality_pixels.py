"""Compare the real GPU resolve with an independent four-sample box reference."""
from pathlib import Path
import struct,zlib,json
ROOT=Path(__file__).resolve().parents[1]
def pixels(name):
 raw=(ROOT/'build'/name).read_bytes();w,h=struct.unpack_from('>II',raw,16);at=8;packed=bytearray()
 while at<len(raw):
  size=struct.unpack_from('>I',raw,at)[0]
  if raw[at+4:at+8]==b'IDAT':packed.extend(raw[at+8:at+8+size])
  at+=size+12
 rows=zlib.decompress(packed);assert all(rows[y*(w*4+1)]==0 for y in range(h))
 return w,h,b''.join(rows[y*(w*4+1)+1:(y+1)*(w*4+1)] for y in range(h))
w,h,low=pixels('quality-1x.png');aw,ah,aa=pixels('quality-2x.png');hw,hh,hi=pixels('quality-reference.png')
assert (w,h)==(aw,ah)==(64,48) and (hw,hh)==(128,96)
delta=0
for y in range(h):
 for x in range(w):
  for c in range(4):
   expected=sum(hi[((2*y+dy)*hw+2*x+dx)*4+c] for dy in range(2) for dx in range(2))/4
   delta=max(delta,abs(aa[(y*w+x)*4+c]-expected))
assert delta<=1,delta
assert set(low[0::4])<={0,255} and any(0<v<255 for v in aa[0::4])
assert all(a==255 for a in aa[3::4])
assert pixels('quality-resized.png')[:2]==pixels('quality-restored.png')[:2]==(80,60)
report = ROOT / 'build/detail-models/quality-results.json'
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(json.dumps({'max_box_filter_error':delta,'output':[w,h],'high_reference':[hw,hh],'opaque':True,'partial_coverage_pixels':sum(0<v<255 for v in aa[0::4])},indent=2)+'\n')
print('PASS: GPU 2x output matches independent 128x96 four-sample reference within one code value; smooth edge coverage, opaque alpha and resize dimensions')

"""Independent directional projection + 3x3 PCF coverage and BRDF-color check."""
from pathlib import Path
import json,math,struct,zlib
ROOT=Path(__file__).resolve().parents[1]
def read(name):
 raw=(ROOT/'build'/('shadow-'+name+'.png')).read_bytes();w,h=struct.unpack_from('>II',raw,16);at=8;packed=bytearray()
 while at<len(raw):
  n=struct.unpack_from('>I',raw,at)[0]
  if raw[at+4:at+8]==b'IDAT':packed.extend(raw[at+8:at+8+n])
  at+=n+12
 rows=zlib.decompress(packed)
 assert all(rows[y*(w*4+1)]==0 for y in range(h))
 return w,h,b''.join(rows[y*(w*4+1)+1:(y+1)*(w*4+1)] for y in range(h))
def decode(v):
 s=v/255.;mapped=s/12.92 if s<=.04045 else ((s+.055)/1.055)**2.4
 return mapped/(1-mapped)
def encode(v):
 mapped=v/(1+v);s=mapped*12.92 if mapped<=.0031308 else 1.055*mapped**(1/2.4)-.055
 return round(s*255)
w,h,lit=read('lit');_,_,shadowed=read('occluded');assert (w,h)==(64,64)
partial=full=0;maximum=0
for y in range(h):
 for x in range(w):
  wx=(2*(x+.5)/w-1)*4*math.tan(.4);wy=(1-2*(y+.5)/h)*4*math.tan(.4)
  u=(wx/2*.5+.5)*128;v=(.5-wy/2*.5)*128
  blocked=0
  for dy in (-1,0,1):
   for dx in (-1,0,1):
    sx=((math.floor(u)+dx+.5)/128-.5)*4;sy=(.5-(math.floor(v)+dy+.5)/128)*4
    blocked+=(-.5<sx<.5 and -.5<sy<.5)
  visibility=1-blocked/9
  partial+=0<blocked<9;full+=blocked==9
  at=(y*w+x)*4
  for c in range(3):
   expected=encode(.048+(decode(lit[at+c])-.048)*visibility)
   maximum=max(maximum,abs(expected-shadowed[at+c]))
  assert shadowed[at+3]==255
assert maximum<=2,(maximum,partial,full)
assert partial>20 and full>100,(partial,full)
assert read('plane-control')[2]==read('plane-self')[2]
result={'pixel_reference':'Independent orthographic tap coverage, inverse sRGB/Reinhard and direct-only visibility','max_color_error':maximum,'partial_pcf_pixels':partial,'fully_occluded_pixels':full,'sloped_plane_acne_pixels':0}
(ROOT/'build/shadow-pixels.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: independent 3x3 PCF/direct-light pixel reference,',partial,'partial-edge pixels,',full,'occluded pixels, maximum error',maximum,'codes; zero sloped-plane acne')

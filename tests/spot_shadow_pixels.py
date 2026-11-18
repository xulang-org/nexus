"""Independent spot projection geometry, PCF tap coverage and direct-only color."""
from pathlib import Path
import json, math, struct, zlib
ROOT = Path(__file__).resolve().parents[1]
def read(name):
    raw=(ROOT/'build'/('spot-shadow-'+name+'.png')).read_bytes()
    w,h=struct.unpack_from('>II',raw,16);at=8;packed=bytearray()
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
focal=1/math.tan(.52)
partial=full=maximum=0
for y in range(h):
    for x in range(w):
        wx=(2*(x+.5)/w-1)*4*math.tan(.4)
        wy=(1-2*(y+.5)/h)*4*math.tan(.4)
        u=(wx*focal/4*.5+.5)*128;v=(.5-wy*focal/4*.5)*128
        blocked=0
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                # Cast from source z=4 through this texel to caster plane z=1.
                sx=(2*(math.floor(u)+dx+.5)/128-1)*3/focal
                sy=(1-2*(math.floor(v)+dy+.5)/128)*3/focal
                blocked+=(-.5<sx<.5 and -.5<sy<.5)
        visibility=1-blocked/9
        partial+=0<blocked<9;full+=blocked==9
        at=(y*w+x)*4
        for c in range(3):
            expected=encode(.048+(decode(lit[at+c])-.048)*visibility)
            maximum=max(maximum,abs(expected-shadowed[at+c]))
        assert shadowed[at+3]==255
assert partial>20 and full>100,(partial,full)
assert maximum<=2,(maximum,partial,full)
assert read('plane-control')[2]==read('plane-self')[2]
assert read('empty')[2]==lit
result={'reference':'Independent perspective rays/3x3 tap coverage and inverse sRGB/Reinhard direct-only attenuation',
        'max_color_error':maximum,'partial_pcf_pixels':partial,'fully_occluded_pixels':full,'sloped_plane_acne_pixels':0}
(ROOT/'build/spot-shadow-pixels.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: perspective spot PCF pixel reference,',partial,'partial-edge pixels,',full,'occluded pixels, maximum error',maximum,'codes; zero sloped-plane acne')

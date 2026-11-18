"""Independent room/ray-box oracle for six-face point PCF, edges and corners."""
from pathlib import Path
import itertools, json, math, struct, zlib
ROOT=Path(__file__).resolve().parents[1]
FORWARD=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
RIGHT=[(0,0,1),(0,0,-1),(1,0,0),(-1,0,0),(-1,0,0),(1,0,0)]
UP=[(0,1,0),(0,1,0),(0,0,1),(0,0,1),(0,1,0),(0,1,0)]
BOXES=[(p,.25) for p in [(1.5,.12,-.07),(-1.4,-.15,.08),(.06,1.6,-.09),(-.12,-1.45,.16),(.1,-.08,1.3),(-.14,.09,-1.55)]]
for pair in range(3):
    for a,b in itertools.product((-1,1),repeat=2):
        p=[a*1.1,b*1.1,.15] if pair==0 else ([a*1.1,.15,b*1.1] if pair==1 else [.15,a*1.1,b*1.1])
        BOXES.append((p,.12))
BOXES.extend((p,.1) for p in itertools.product((-1,1),repeat=3))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def unit(a):
    length=math.sqrt(dot(a,a));return tuple(x/length for x in a)
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def face_of(d):
    a=tuple(abs(x) for x in d)
    if a[0]>=a[1] and a[0]>=a[2]:return 0 if d[0]>=0 else 1
    if a[1]>=a[2]:return 2 if d[1]>=0 else 3
    return 4 if d[2]>=0 else 5
def uv_of(d,face):
    z=dot(d,FORWARD[face]);return (.5+.5*dot(d,RIGHT[face])/z,.5-.5*dot(d,UP[face])/z)
def ray_of(uv,face):
    return tuple(FORWARD[face][i]+(2*uv[0]-1)*RIGHT[face][i]+(1-2*uv[1])*UP[face][i] for i in range(3))
def box_hit(ray,center,half):
    lower=-math.inf;upper=math.inf
    for d,c in zip(ray,center):
        if abs(d)<1e-15:
            if abs(c)>half:return math.inf
        else:
            a=(c-half)/d;b=(c+half)/d
            lower=max(lower,min(a,b));upper=min(upper,max(a,b))
            if lower>upper:return math.inf
    return lower if lower>0 and upper>=lower else math.inf
CACHE={}
def closest(face,ix,iy,origin):
    key=(face,ix,iy,origin)
    if key not in CACHE:
        ray=ray_of(((ix+.5)/128,(iy+.5)/128),face)
        CACHE[key]=(ray,min(box_hit(ray,tuple(p[i]-origin[i] for i in range(3)),h) for p,h in BOXES))
    return CACHE[key]
def read(name):
    raw=(ROOT/'build'/('point-shadow-'+name+'.png')).read_bytes()
    w,h=struct.unpack_from('>II',raw,16);at=8;packed=bytearray()
    while at<len(raw):
        n=struct.unpack_from('>I',raw,at)[0]
        if raw[at+4:at+8]==b'IDAT':packed.extend(raw[at+8:at+8+n])
        at+=n+12
    rows=zlib.decompress(packed);assert all(rows[y*(w*4+1)]==0 for y in range(h))
    return w,h,b''.join(rows[y*(w*4+1)+1:(y+1)*(w*4+1)] for y in range(h))
def decode(v):
    s=v/255.;mapped=s/12.92 if s<=.04045 else ((s+.055)/1.055)**2.4
    return mapped/(1-mapped)
def encode(v):
    mapped=v/(1+v);s=mapped*12.92 if mapped<=.0031308 else 1.055*mapped**(1/2.4)-.055
    return round(s*255)
partial=full=maximum=cross_taps=seam_shadow=corner_pixels=checked=0
per_face=[];worst=[]
for label,camera,origin in [(str(c),c,(0,0,0)) for c in range(6)]+[('moved',0,(.25,.1,-.2))]:
    w,h,lit=read(f'{label}-lit');_,_,shadowed=read(f'{label}-occluded');assert (w,h)==(64,64)
    f=unit(tuple(FORWARD[camera][i]+RIGHT[camera][i]*.03+UP[camera][i]*.017 for i in range(3)))
    back=tuple(-v for v in f);right=unit(cross(UP[camera],back));up=cross(back,right)
    affected=0
    for y in range(h):
        for x in range(w):
            px=(2*(x+.5)/w-1)*math.tan(.81);py=(1-2*(y+.5)/h)*math.tan(.81)
            ray=tuple(f[i]+right[i]*px+up[i]*py for i in range(3))
            distance=3/max(abs(v) for v in ray)
            p=tuple(v*distance for v in ray)
            wall=face_of(p);delta=tuple(p[i]-origin[i] for i in range(3))
            face=face_of(delta);uv=uv_of(delta,face)
            normal=tuple(-v for v in FORWARD[wall]);plane=dot(normal,delta)
            toward=unit(tuple(-v for v in delta))
            bias=.00002+.00005*(1-max(0,dot(normal,toward)))
            blocked=0;tap_faces=set();occluded_weight=weight_sum=0.0
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    tx=math.floor(uv[0]*128)+dx+.5;ty=math.floor(uv[1]*128)+dy+.5
                    weight=max(0,1.5-abs(tx-uv[0]*128))*max(0,1.5-abs(ty-uv[1]*128))
                    weight_sum+=weight
                    if weight<=0:continue
                    tap_ray=ray_of((tx/128,ty/128),face);adjacent=face_of(tap_ray);at=uv_of(tap_ray,adjacent)
                    ix=max(0,min(127,math.floor(at[0]*128)));iy=max(0,min(127,math.floor(at[1]*128)))
                    sample_ray,hit=closest(adjacent,ix,iy,origin);tap_faces.add(adjacent);cross_taps+=adjacent!=face
                    denominator=dot(normal,sample_ray)
                    if abs(denominator)<=.000001:continue
                    t=plane/denominator
                    if t<=0:continue
                    reference=(.1*10/9.9)/t-.1/9.9
                    if not 0<=reference<=1:continue
                    stored=(.1*10/9.9)/hit-.1/9.9 if hit<math.inf else 0
                    if reference+bias<stored:
                        blocked+=1;occluded_weight+=weight
            partial+=0<blocked<9;full+=blocked==9;affected+=blocked>0
            seam_shadow+=blocked>0 and len(tap_faces)>1;corner_pixels+=len(tap_faces)>=3;checked+=1
            visibility=1-occluded_weight/weight_sum;at=(y*w+x)*4
            error=max(abs(encode(.048+(decode(lit[at+c])-.048)*visibility)-shadowed[at+c]) for c in range(3))
            maximum=max(maximum,error)
            if error>2 and len(worst)<12:worst.append((camera,x,y,error,blocked,face))
            assert shadowed[at+3]==255
    assert read(f'{label}-empty')[2]==lit
    assert affected>30,(camera,affected)
    per_face.append(affected)
assert maximum<=2,(maximum,worst)
assert partial>100 and full>100 and cross_taps>200 and seam_shadow>20 and corner_pixels>0
assert read('plane-control')[2]==read('plane-self')[2]
_,_,left=read('jitter-left');_,_,right=read('jitter-right')
jitter_delta=max(abs(a-b) for a,b in zip(left,right))
assert jitter_delta<=2,jitter_delta
result={'reference' :'Independent camera rays, room walls, 26 AABBs, cube-face tap reprojection, continuous 3x3 tent weights and sRGB/Reinhard direct attenuation',
        'checked_pixels':checked,'max_color_error':maximum,'partial_pcf_pixels':partial,'fully_occluded_pixels':full,
        'cross_face_taps':cross_taps,'shadow_pixels_with_cross_face_taps':seam_shadow,'three_face_corner_pixels':corner_pixels,
        'affected_pixels_per_view':per_face,'tiny_camera_jitter_max_code_delta':jitter_delta,'sloped_plane_acne_pixels':0}
(ROOT/'build/point-shadow-pixels.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: independent six-face point ray-box/PCF pixels, max error',maximum,'codes;',checked,'pixels,',cross_taps,'cross-face taps,',corner_pixels,'corner pixels; zero sloped-plane acne')

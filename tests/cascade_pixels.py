"""Independent tilted-plane rays, closed-form cascade spheres, PCF and blend."""
from pathlib import Path
import json,math,struct,zlib
ROOT=Path(__file__).resolve().parents[1]
CENTERS=[(1,.2),(.3,-.3),(-1,.5),(-3.4,-.7001),(-5,.6),(-8.0004,-.9),(-11.1969,.2525)]
def read(name):
    raw=(ROOT/'build'/('cascade-'+name+'.png')).read_bytes();w,h=struct.unpack_from('>II',raw,16);at=8;data=bytearray()
    while at<len(raw):
        n=struct.unpack_from('>I',raw,at)[0]
        if raw[at+4:at+8]==b'IDAT':data.extend(raw[at+8:at+8+n])
        at+=n+12
    rows=zlib.decompress(data);assert all(rows[y*(w*4+1)]==0 for y in range(h))
    return w,h,b''.join(rows[y*(w*4+1)+1:(y+1)*(w*4+1)] for y in range(h))
def decode(v):
    s=v/255;f=s/12.92 if s<=.04045 else ((s+.055)/1.055)**2.4
    return f/(1-f)
def encode(v):
    f=v/(1+v);s=f*12.92 if f<=.0031308 else 1.055*f**(1/2.4)-.055
    return round(s*255)
def slices(count,eye,blend):
    split=[1]+[.6*30**(i/count)+.4*(1+29*i/count) for i in range(1,count)]+[30]
    result=[]
    for i in range(count):
        start,end=split[i:i+2];fit=start if i==0 else start-(start-split[i-1])*blend
        middle=(fit+end)/2
        # Far corners maximize distance from the axial midpoint of this frustum.
        radius=math.sqrt(2*(end*math.tan(.4))**2+((end-fit)/2)**2)
        radius=max(.0625,math.ceil(radius/.0625-1e-7)*.0625)
        extent=radius*128/122;depth=2*(radius+5)
        texel=2*extent/128;center=round(eye/texel)*texel
        result.append((start,end,end-(end-start)*blend,middle,extent,depth,center))
    return result
def stored(layer,ix,iy):
    _,_,_,middle,extent,depth,center=layer
    x=(2*(ix+.5)/128-1)*extent+center;y=(1-2*(iy+.5)/128)*extent
    z=0
    for i,(cx,cy) in enumerate(CENTERS):
        half=1.8 if i==6 else .6
        if cx-half<x<cx+half and cy-2.5<y<cy+2.5:
            depth_value=.5+(-1+2*cx+middle)/depth
            if 0<depth_value<=1:z=max(z,depth_value)
    return z
def visibility(layers,index,p,cache):
    layer=layers[index];_,_,_,middle,extent,depth,center=layer
    uv=((p[0]-center)/extent*.5+.5,.5-p[1]/extent*.5)
    z=.5+(p[2]+middle)/depth
    if not 0<=uv[0]<=1 or not 0<=uv[1]<=1 or not 0<=z<=1:return 1
    occluded=total=0
    bias=.0003*layers[0][5]/depth + (4*extent/depth)/128/256
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            ix=math.floor(uv[0]*128)+dx;iy=math.floor(uv[1]*128)+dy
            tx=ix+.5;ty=iy+.5
            weight=max(0,1.5-abs(tx-uv[0]*128))*max(0,1.5-abs(ty-uv[1]*128))
            total+=weight
            if not 0<=ix<128 or not 0<=iy<128:continue
            key=(index,ix,iy)
            if key not in cache:cache[key]=stored(layer,ix,iy)
            sample_x=(2*tx/128-1)*extent+center
            reference=.5+(-6+2*sample_x+middle)/depth
            if reference+bias<cache[key]:occluded+=weight
    return 1-occluded/total
# Keep analytic fixture edges away from hardware subpixel coverage ties.
# This guard is checked from geometry alone, before any GPU output is compared.
margin=min(abs((edge/(2*layer[4]/128))%1-.5)
           for n,b in [(2,.2),(3,.2),(4,.2),(4,0)] for layer in slices(n,0,b)
           for i,(cx,cy) in enumerate(CENTERS)
           for edge in [cx-(1.8 if i==6 else .6),cx+(1.8 if i==6 else .6),cy-2.5,cy+2.5])
assert margin>.01,margin
maximum=checked=blend_pixels=fade_pixels=outside=partial=0;cases=[];worst=[]
for label,count,eye,blend in [('2',2,0,.2),('3',3,0,.2),('4',4,0,.2),('moved',4,.25,.2),('hard',4,0,0)]:
    w,h,lit=read(label+'-lit');_,_,shadow=read(label+'-shadow');assert (w,h)==(128,96)
    layers=slices(count,eye,blend);cache={};selected=[0]*count;affected=0;case_max=0
    for y in range(h):
        for x in range(w):
            rx=(2*(x+.5)/w-1)*math.tan(.4);ry=(1-2*(y+.5)/h)*math.tan(.4)
            distance=(6-2*eye)/(1+2*rx);p=(eye+rx*distance,ry*distance,-distance)
            if distance<1 or distance>30:v=1;outside+=1
            else:
                index=next(i for i,layer in enumerate(layers) if distance<=layer[1]);selected[index]+=1
                v=visibility(layers,index,p,cache)
                start,end,band,*_=layers[index]
                if end>band and distance>band:
                    next_v=visibility(layers,index+1,p,cache) if index+1<count else 1
                    alpha=(distance-band)/(end-band);alpha=alpha*alpha*(3-2*alpha)
                    v=v+(next_v-v)*alpha
                    if index+1<count:blend_pixels+=1
                    else:fade_pixels+=1
            partial+=0<v<1;affected+=v<.999999;checked+=1
            at=(y*w+x)*4
            error=max(abs(encode(.048+(decode(lit[at+c])-.048)*v)-shadow[at+c]) for c in range(3))
            case_max=max(case_max,error);maximum=max(maximum,error)
            if error>2 and len(worst)<10:worst.append((label,x,y,error,distance,v))
            assert shadow[at+3]==255
    assert all(n>0 for n in selected) and affected>100,(label,selected,affected)
    cases.append({'case':label,'cascade_pixels':selected,'max_color_error':case_max,'shadowed_pixels':affected})
assert maximum<=2,(maximum,worst)
assert blend_pixels>100 and fade_pixels>100 and outside>100
assert read('plane-self')[2]==read('plane-control')[2]==read('empty')[2]
result={'reference':'Independent camera-plane intersections, analytic frustum spheres/texel grid, physical caster rectangles, tent PCF, smoothstep cascade blend and far fade',
        'minimum_caster_edge_margin_texels':margin,'checked_pixels':checked,'max_color_error':maximum,'blend_pixels':blend_pixels,'far_fade_pixels':fade_pixels,'beyond_distance_pixels':outside,
        'partially_shadowed_pixels':partial,'sloped_plane_acne_pixels':0,'cases':cases}
(ROOT/'build/cascade-pixels.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: independent cascade PCF/blend pixels,',checked,'pixels,',blend_pixels,'blend,',fade_pixels,'far fade, maximum error',maximum,'codes; zero sloped-plane acne')

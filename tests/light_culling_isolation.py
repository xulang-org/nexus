"""Independent cone witness oracle and CPU bounds/selection without scene or GPU sources."""
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
rng=random.Random(5349)
def unit(v):
    length=math.sqrt(sum(x*x for x in v))
    return [x/length for x in v]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
with tempfile.TemporaryDirectory(prefix='xu light culling ') as temporary:
    root=Path(temporary)
    shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
    for package in ('foundation/math','resources/mesh','resources/lighting'):
        shutil.copytree(ROOT/package,root/package)
    rows=bytearray()
    for _ in range(512):
        origin=[rng.uniform(-1e6,1e6) for _ in range(3)]
        axis=unit([rng.uniform(-1,1) for _ in range(3)])
        u=unit(cross(axis,[0,0,1] if abs(axis[2])<.9 else [0,1,0]))
        v=cross(axis,u)
        radius=10**rng.uniform(-3,6)
        outer=rng.uniform(.01,1.4);inner=outer*.5
        angle=rng.uniform(0,outer*.95);phase=rng.uniform(0,math.tau);distance=radius*rng.uniform(.01,.95)
        direction=[axis[i]*math.cos(angle)+math.sin(angle)*(u[i]*math.cos(phase)+v[i]*math.sin(phase)) for i in range(3)]
        witness=[origin[i]+direction[i]*distance for i in range(3)]
        delta=[witness[i]-origin[i] for i in range(3)]
        actual=math.sqrt(sum(x*x for x in delta))
        assert actual<radius and sum(delta[i]*axis[i] for i in range(3))/actual>math.cos(outer)
        half=[radius*rng.uniform(.001,.2) for _ in range(3)]
        center=[witness[i]+half[i]*rng.uniform(-.9,.9) for i in range(3)]
        low=[center[i]-half[i] for i in range(3)];high=[center[i]+half[i] for i in range(3)]
        assert all(low[i]<=witness[i]<=high[i] for i in range(3))
        rows.extend(struct.pack('<15d',*origin,*axis,radius,math.cos(inner),math.cos(outer),*low,*high))
    oracle=root/'known contributors.bin';oracle.write_bytes(rows)
    checks=root/'checks';checks.mkdir()
    shutil.copyfile(ROOT/'tests/light_culling_checks.xu',checks/'main.xu')
    sdk=next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (checks/'xu.xun').write_text('module: example/light_culling_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    env=os.environ | {'XU_NATIVE_CC':'/nonexistent/compiler','XU_SDL_LIBRARY':'/nonexistent/SDL'}
    for absent in ('scene','integration','rendering','platform','native','assets','audio','script'):
        assert not (root/absent).exists(),absent
    for level in ('--no-opt','--release'):
        binary=root/('culling'+level)
        subprocess.run([os.environ.get('XU','xu'),'build',str(checks/'main.xu'),level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
        subprocess.run([str(binary),str(oracle)],cwd=root,env=env,check=True,timeout=30)
print('PASS: --no-opt/--release isolated culling and independent Python cone witnesses; no scene/native/GPU dependencies')

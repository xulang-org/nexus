"""Homogeneous clip witnesses from independent Python arithmetic; pure math only."""
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
rng=random.Random(6087)
with tempfile.TemporaryDirectory(prefix='xu clip volume ') as directory:
    root=Path(directory)
    shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
    shutil.copytree(ROOT/'foundation/math',root/'foundation/math')
    packet=bytearray()
    for _ in range(512):
        p=[rng.uniform(-100,100) for _ in range(3)]
        w=10**rng.uniform(-2,5)
        target=[rng.uniform(-.8,.8)*w,rng.uniform(-.8,.8)*w,rng.uniform(.1,.9)*w,w]
        rows=[]
        for t in target:
            row=[rng.uniform(-1e4,1e4) for _ in range(3)]
            row.append(t-sum(row[i]*p[i] for i in range(3)))
            rows.append(row)
        clip=[sum(row[i]*p[i] for i in range(3))+row[3] for row in rows]
        assert clip[3]>0 and abs(clip[0])<clip[3] and abs(clip[1])<clip[3] and 0<clip[2]<clip[3]
        half=[rng.uniform(0,5) for _ in range(3)]
        low=[p[i]-half[i] for i in range(3)];high=[p[i]+half[i] for i in range(3)]
        columns=[rows[r][c] for c in range(4) for r in range(4)]
        packet.extend(struct.pack('<22d',*low,*high,*columns))
    oracle=root/'visible witnesses.bin';oracle.write_bytes(packet)
    checks=root/'checks';checks.mkdir()
    shutil.copyfile(ROOT/'tests/frustum_checks.xu',checks/'main.xu')
    sdk=next(s for s in (ROOT/'xu.xun').read_text().splitlines() if s.startswith('xu:'))
    (checks/'xu.xun').write_text('module: example/clip_math_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    for absent in ('scene','resources','rendering','integration','native','platform'):
        assert not (root/absent).exists(),absent
    env=os.environ | {'XU_NATIVE_CC':'/nonexistent/compiler','XU_SDL_LIBRARY':'/nonexistent/SDL'}
    for level in ('--no-opt','--release'):
        binary=root/('clip'+level)
        subprocess.run([os.environ.get('XU','xu'),'build',str(checks/'main.xu'),level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
        subprocess.run([str(binary),str(oracle)],cwd=root,env=env,check=True,timeout=30)
print('PASS: --no-opt/--release clip-volume isolation with only foundation/math, no scene/resources/GPU/native dependencies')

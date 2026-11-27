"""Strict light scene data, runtime composition and fresh-process persistence without devices."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu light persistence ') as directory:
    root=Path(directory)
    shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
    for package in ('foundation/math', 'resources/camera','resources/lighting','resources/shadow','resources/scene','resources/lod',
                    'resources/persistence','resources/sprite3d','resources/tilemap','formats/scene',
                    'internal/file_snapshot','scene','integration/lighting','integration/scene','integration/scene_lighting'):
        shutil.copytree(ROOT/package,root/package)
    shutil.copytree(ROOT/'build/scene-lighting-fixtures',root/'build/scene-lighting-fixtures')
    combined=root/'examples/scene_av/assets/world.xuscene'
    combined.parent.mkdir(parents=True)
    shutil.copyfile(ROOT/'examples/scene_av/assets/world.xuscene',combined)
    for absent in ('native','platform','rendering','assets','audio','script'):
        assert not (root/absent).exists(),absent
    sdk=next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    checks=root/'checks';checks.mkdir()
    (checks/'xu.xun').write_text('module: example/light_persistence_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    env=os.environ | {'XU_NATIVE_CC':'/nonexistent/native-compiler','XU_SDL_LIBRARY':'/nonexistent/SDL',
                      'XU_NEXUS_SDL_AUDIO_LIBRARY':'/nonexistent/audio','SDL_VIDEODRIVER':'nonexistent'}
    for level in ('--no-opt','--release'):
        for source,name in (('scene_lighting_checks.xu','checks'),('scene_lighting_process_cli.xu','process')):
            shutil.copyfile(ROOT/'tests'/source,checks/'main.xu')
            binary=root/(name+level)
            subprocess.run([os.environ.get('XU','xu'),'build',str(checks/'main.xu'),level,'-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
            if name=='checks':
                subprocess.run([str(binary)],cwd=root,env=env,check=True,timeout=60)
                continue
            for profile, version in (('cascades', 4), ('punctual', 5)):
                saved = root / f'saved {profile} scene {level}.xuscene'
                original = root / 'build/scene-lighting-fixtures' / f'{profile}.xuscene'
                for operation,path in (('write',original),('read',saved)):
                    result=subprocess.run([str(binary),operation,str(path),str(saved)],cwd=root,env=env,check=True,
                                          capture_output=True,text=True,timeout=30)
                    assert result.stdout.strip()==('saved' if operation=='write' else 'loaded'),result.stdout+result.stderr
                data=json.loads(saved.read_text())
                authored=json.loads(original.read_text())
                assert data['version']==version
                for before, after in zip(authored['lights'], data['lights'], strict=True):
                    assert after.get('cascades') == before.get('cascades')
                    assert after.get('shadow') == before.get('shadow')
                assert len(data['lights'])==4 and data['lights'][1]['position'][0]==.75
                assert data['lights'][1]['radiance']==[9,8,7] and data['nodes'][3]['transform'][12]==4
                assert data['nodes'][0]['transform'][12]==5 and data['nodes'][5]['visible'] is False
                assert all(set(item).isdisjoint({'id','handle','world_transform'}) for item in data['lights'])
                assert not list(root.glob('*.tmp-*'))
print('PASS: --no-opt/--release isolated light scene checks and save/exit/fresh-process restoration; no native/GPU/SDL/audio/script dependencies')

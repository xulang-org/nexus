"""Exercise 3D and 2D composition without nexus native archives or scene source."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu standard 3D ') as directory:
    root=Path(directory)
    shutil.copyfile(ROOT/'xu.xun',root/'xu.xun')
    for package in ('foundation/math','platform/present','resources/mesh','resources/canvas','resources/lighting','resources/lighting2d','resources/shadow','rendering/three_d','rendering/two_d',
                    'assets/shaders/three_d','assets/shaders/two_d','internal/file_snapshot','build/mesh-shaders'):
        shutil.copytree(ROOT/package,root/package)
    (root/'checks').mkdir()
    sdk=next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (root/'checks/xu.xun').write_text('module: example/three_d_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    shutil.copyfile(ROOT/'tests/renderer3d_isolation.xu',root/'checks/main.xu')
    for absent in ('native','scene','integration','platform/sdl_gpu','platform/sdl_image','platform/sdl_audio'):
        assert not (root/absent).exists(),absent
    binary=root/'renderer'
    env=os.environ | {'XU_NEXUS_SDL_LIBRARY':'/nonexistent/nexus-native-must-not-load','XU_NEXUS_SDL_AUDIO_LIBRARY':'/nonexistent/audio-must-not-load'}
    subprocess.run([os.environ.get('XU','xu'),'build',str(root/'checks/main.xu'),'--release','-o',str(binary)],cwd=root,env=env,check=True,timeout=60)
    subprocess.run([str(binary)],cwd=root,env=env,check=True,timeout=60)

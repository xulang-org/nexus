"""Run CPU mesh processing with only its declared data/math dependencies."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-nexus-mesh-') as directory:
    target = Path(directory)
    shutil.copyfile(ROOT/'xu.xun', target/'xu.xun')
    for package in ('foundation/math', 'resources/mesh'):
        shutil.copytree(ROOT/package, target/package)
    (target/'checks').mkdir()
    sdk = next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (target/'checks/xu.xun').write_text('module: example/mesh_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    shutil.copyfile(ROOT/'tests/mesh_data_checks.xu', target/'checks/main.xu')
    for absent in ('native', 'platform', 'rendering', 'scene', 'assets', 'formats', 'script', 'internal'):
        assert not (target/absent).exists(), absent
    binary = target/'mesh-checks'
    subprocess.run([os.environ.get('XU', 'xu'), 'build', str(target/'checks/main.xu'), '-o', str(binary)], cwd=target, check=True, timeout=60)
    env = os.environ | {'XU_NEXUS_SDL_LIBRARY': '/nonexistent/mesh-no-sdl', 'SDL_VIDEODRIVER': 'nonexistent'}
    subprocess.run([str(binary)], cwd=target, env=env, check=True, timeout=60)
print('PASS: mesh construction/tangents without rendering/platform/scene source, native archives or SDL')

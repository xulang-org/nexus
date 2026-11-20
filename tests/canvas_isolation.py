"""Build scene canvas recording with no GPU service, native modules or shaders."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-nexus-canvas-') as directory:
    target = Path(directory)
    shutil.copyfile(ROOT/'xu.xun', target/'xu.xun')
    for package in ('foundation/math', 'resources/camera', 'resources/canvas', 'scene', 'integration/rendering/two_d'):
        shutil.copytree(ROOT/package, target/package)
    (target/'checks').mkdir()
    sdk = next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (target/'checks/xu.xun').write_text('module: example/canvas_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    shutil.copyfile(ROOT/'tests/canvas_checks.xu', target/'checks/main.xu')
    for absent in ('native', 'platform', 'rendering', 'assets', 'formats', 'script', 'internal'):
        assert not (target/absent).exists(), absent
    binary = target/'canvas-checks'
    subprocess.run([os.environ.get('XU', 'xu'), 'build', str(target/'checks/main.xu'), '-o', str(binary)], cwd=target, check=True, timeout=60)
    env = os.environ | {'XU_SDL_LIBRARY': '/nonexistent/canvas-no-sdl', 'XU_NEXUS_SDL_LIBRARY': '/nonexistent/canvas-no-sdl', 'SDL_VIDEODRIVER': 'nonexistent'}
    subprocess.run([str(binary)], cwd=target, env=env, check=True, timeout=60)

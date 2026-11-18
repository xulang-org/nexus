"""Run window presentation using only the selected standard SDK and offline shaders."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-stdlib-surface-') as directory:
    project = Path(directory)
    for name in ('main.xu', 'xu.xun'):
        shutil.copy2(ROOT / 'examples/gpu_surface' / name, project / name)
    shaders = project / 'shaders with spaces'
    shutil.copytree(ROOT / 'build/gpu-surface-shaders', shaders)
    env = dict(os.environ, XU_NEXUS_SDL_LIBRARY='/nonexistent/nexus-runtime')
    compiler = env.get('XU', 'xu')
    binary = project / 'GPU surface'
    subprocess.run([compiler, 'build', 'main.xu', '-o', str(binary)], cwd=project, env=env, check=True, timeout=60)
    result = subprocess.run([str(binary), '--shaders', str(shaders), '--frames', '30'], cwd=project, env=env,
                            text=True, capture_output=True, check=True, timeout=60)
    assert int(result.stdout.splitlines()[-1]) > 0, result.stdout + result.stderr
    assert 'Presented standard GPU window with zero live window/surface/frame resources' in result.stdout, result.stdout + result.stderr
print('PASS: isolated standard GPU surface consumer, shaders with spaces, no nexus source or native archive')

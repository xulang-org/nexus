"""Run buffer compute using only the selected standard SDK and offline shaders."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-stdlib-compute-') as directory:
    project = Path(directory)
    for name in ('main.xu', 'xu.xun'):
        shutil.copy2(ROOT / 'examples/gpu_compute' / name, project / name)
    shaders = project / 'shaders with spaces'
    shutil.copytree(ROOT / 'build/gpu-compute-shaders', shaders)
    env = dict(os.environ, XU_NEXUS_SDL_LIBRARY='/nonexistent/nexus-runtime')
    compiler = env.get('XU', 'xu')
    binary = project / 'GPU compute'
    subprocess.run([compiler, 'build', 'main.xu', '-o', str(binary)], cwd=project, env=env, check=True, timeout=60)
    result = subprocess.run([str(binary), '--shaders', str(shaders)], cwd=project, env=env,
                            text=True, capture_output=True, check=True, timeout=60)
    assert 'Verified 1027 exact GPU values through two dependent compute passes and zero live resources' in result.stdout, result.stdout + result.stderr
print('PASS: isolated standard GPU compute consumer, shaders with spaces, no nexus source or native archive')

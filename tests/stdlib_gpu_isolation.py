"""Run the standard GPU consumer without nexus source or native archives."""
from pathlib import Path
import os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-stdlib-gpu-isolation-') as directory:
    project=Path(directory)
    for name in ('main.xu','xu.xun'):
        shutil.copy2(ROOT/'examples/gpu_transfer'/name,project/name)
    env=dict(os.environ,XU_NEXUS_SDL_LIBRARY='/nonexistent/nexus-runtime')
    compiler=env.get('XU','xu')
    binary=project/'gpu-transfer'
    subprocess.run([compiler,'build','main.xu','-o',str(binary)],cwd=project,env=env,check=True,timeout=60)
    result=subprocess.run([str(binary)],cwd=project,env=env,text=True,capture_output=True,check=True,timeout=60)
    assert 'Verified 4096 bytes' in result.stdout,result.stdout+result.stderr
print('PASS: independent standard GPU consumer without nexus source, native archives, window or shader tools')

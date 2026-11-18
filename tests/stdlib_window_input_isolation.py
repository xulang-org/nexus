"""Exercise pure action mapping and a standard GPU/input app without nexus native code."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-window-input-') as directory:
    project=Path(directory)
    nexus=project/'nexus data with spaces'
    for name in ('foundation/math','input','integration/input'):
        shutil.copytree(ROOT/name,nexus/name)
    (nexus/'xu.xun').write_text('module: "github.com/xulang-org/nexus"\nversion: !ver 0.1.1-dev.2\nxu: !ver 0.12.3\n')
    consumer=project/'consumer';consumer.mkdir()
    (consumer/'xu.xun').write_text('module: example/input_isolation\nversion: !ver 0.1.0\nxu: !ver 0.12.3\nrequire:\n  "github.com/xulang-org/nexus": file:../nexus data with spaces\n')
    shutil.copy2(ROOT/'tests/window_input_checks.xu',consumer/'main.xu')
    compiler=os.environ.get('XU','xu')
    pure=dict(os.environ,XU_NATIVE_CC='/nonexistent/native-compiler',XU_NEXUS_SDL_LIBRARY='/nonexistent/nexus-native',XU_SDL_LIBRARY='/nonexistent/SDL',SDL_VIDEODRIVER='nonexistent')
    binary=consumer/'pure input'
    for level in ('--no-opt','--release'):
        subprocess.run([compiler,'build','main.xu',level,'-o',str(binary)],cwd=consumer,env=pure,check=True,timeout=60)
        result=subprocess.run([str(binary)],cwd=consumer,env=pure,capture_output=True,text=True,check=True,timeout=60)
        assert 'PASS: portable physical-key actions' in result.stdout,result.stdout+result.stderr
    shutil.copy2(ROOT/'examples/window_input/main.xu',consumer/'main.xu')
    env=dict(os.environ,XU_NEXUS_SDL_LIBRARY='/nonexistent/nexus-native')
    binary=consumer/'window input'
    subprocess.run([compiler,'build','main.xu','--release','-o',str(binary)],cwd=consumer,env=env,check=True,timeout=60)
    result=subprocess.run([str(binary),'--frames','20'],cwd=consumer,env=env,capture_output=True,text=True,check=True,timeout=60)
    assert 'Finished standard window/input actions and GPU clear frames with zero live resources' in result.stdout,result.stdout+result.stderr
    assert int(result.stdout.splitlines()[-2])>0,result.stdout
print('PASS: pure window event/action mapping without C/SDL; standard window/GPU consumer with CPU-only nexus sources, no native archive, scenes or shader tools')

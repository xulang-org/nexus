import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-scene-script-') as temporary:
 target=Path(temporary);shutil.copyfile(root/'xu.xun',target/'xu.xun')
 for package in ['scene','foundation/math', 'resources/camera','resources/scene','resources/lighting','resources/shadow','formats/scene','internal/file_snapshot','integration/scene','integration/scene_script','script/bytecode','script/vm','script/host']:
  shutil.copytree(root/package,target/package)
 check=target/'checks';check.mkdir();shutil.copyfile(root/'tests/scene_script_process_cli.xu',check/'main.xu')
 (check/'xu.xun').write_text('module: example/script_scene_isolation\nversion: !ver 0.1.0\nxu: !ver 0.12.3\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
 scenes=target/'scenes';scenes.mkdir()
 for name in ['base.xuscene','mover.xubc','indicator.xubc']:shutil.copyfile(root/'build/scene-script-fixtures'/name,scenes/name)
 binary=target/'script-scene'
 subprocess.run([os.environ.get('XU','xu'),'build',str(check/'main.xu'),'-o',str(binary)],cwd=target,check=True,timeout=60)
 env=dict(os.environ,XU_NEXUS_SDL_LIBRARY='/nonexistent',XU_NEXUS_SDL_AUDIO_LIBRARY='/nonexistent')
 for operation in ['write','read']:
  source=scenes/('base.xuscene' if operation=='write' else 'saved.xuscene')
  result=subprocess.run([str(binary),operation,str(source),str(scenes/'saved.xuscene')],cwd=target,env=env,check=True,text=True,capture_output=True,timeout=20)
  assert result.stdout.strip()==('saved' if operation=='write' else 'loaded'),result.stdout
 assert not (target/'script/compiler').exists() and not (target/'rendering').exists() and not (target/'audio').exists()
print('PASS: script scene save/exit/fresh-process startup with no compiler/GPU/audio sources or SDL runtime; no native archives')

#!/usr/bin/env python3
"""Audio scene restart in fresh processes, no SDL runtime or GPU source code."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-scene-audio-') as temporary:
 target=Path(temporary);shutil.copyfile(root/'xu.xun',target/'xu.xun')
 for package in ['scene','foundation/math', 'resources/camera','resources/scene','resources/lod','resources/lighting','resources/shadow',
                 'resources/sprite3d','resources/tilemap','resources/audio','formats/scene','formats/wav','internal/file_snapshot','integration/scene','integration/scene_audio','integration/audio','audio','platform/sdl_audio']:
  shutil.copytree(root/package,target/package)
 (target/'native').mkdir()
 shutil.copyfile(root/'native/nexus_audio.xulib',target/'native/nexus_audio.xulib')
 checks=target/'checks';checks.mkdir();shutil.copyfile(root/'tests/scene_audio_process_cli.xu',checks/'main.xu')
 sdk=next(line for line in (root/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
 (checks/'xu.xun').write_text('module: example/audio_scene_isolation\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
 scenes=target/'scenes';scenes.mkdir()
 for source,destination in [('base.xuscene','world.xuscene'),('tone.wav','tone.wav')]:shutil.copyfile(root/'build/scene-audio-fixtures'/source,scenes/destination)
 binary=target/'audio-scene-cli'
 subprocess.run([os.environ.get('XU','xu'),'build',str(checks/'main.xu'),'-o',str(binary)],cwd=target,check=True,timeout=60)
 environment=dict(os.environ,XU_NEXUS_SDL_LIBRARY='/nonexistent/no-gpu',XU_NEXUS_SDL_AUDIO_LIBRARY='/nonexistent/no-audio')
 for operation in ['write','read']:
  result=subprocess.run([str(binary),operation,str(scenes/'world.xuscene'),str(scenes/'saved.xuscene')],cwd=target,env=environment,check=True,capture_output=True,text=True,timeout=20)
  assert result.stdout.strip()==('saved' if operation=='write' else 'loaded'),result.stdout
 assert not (target/'rendering').exists() and not (target/'integration/scene_render').exists() and not (target/'assets').exists()
 assert not list(scenes.glob('*.tmp-*'))
print('PASS: audio scene save/exit/fresh-process restart restores exact PCM and authored buses without SDL runtime, GPU source or shader packages; only the audio device archive is linked')

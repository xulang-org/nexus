#!/usr/bin/env python3
"""Node persistence in fresh processes without SDL initialization or rendering packages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-nexus-scene-isolation-') as directory:
    target = Path(directory)
    shutil.copyfile(root / 'xu.xun', target / 'xu.xun')
    for package in ['scene', 'foundation/math', 'resources/camera', 'resources/scene','resources/lod','resources/lighting','resources/shadow',
                    'resources/persistence', 'resources/sprite3d', 'resources/tilemap', 'formats/scene', 'internal/file_snapshot', 'integration/scene']:
        shutil.copytree(root / package, target / package)
    check = target / 'checks'
    check.mkdir()
    shutil.copyfile(root / 'tests/scene_process_cli.xu', check / 'main.xu')
    sdk = next(line for line in (root / 'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (check / 'xu.xun').write_text('module: example/scene_isolation\nversion: !ver 0.1.0\n' + sdk + '\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    binary = target / 'scene-cli'
    subprocess.run([os.environ.get('XU','xu'), 'build', str(check / 'main.xu'), '-o', str(binary)], cwd=target, check=True, timeout=60)
    assert not (target / 'rendering').exists() and not (target / 'platform').exists()
    environment = dict(os.environ, XU_NEXUS_SDL_LIBRARY='/nonexistent/scene-no-sdl', SDL_VIDEODRIVER='nonexistent')
    path = target / 'persisted.xuscene'
    for operation in ['write', 'read']:
        result = subprocess.run([str(binary), operation, str(path)], cwd=target, env=environment, check=True, capture_output=True, text=True, timeout=20)
        assert result.stdout.strip() == ('saved' if operation == 'write' else 'loaded'), result.stdout
    assert not list(target.glob('*.tmp-*'))
print('PASS: save/exit/fresh-process load with a mixed tree, exact pose and camera lens; no GPU/SDL initialization or native archives')
# The main suite exercises close/rename failures as well as successful overwrites.
assert not list((root / 'build/scene-fixtures').glob('*.tmp-*'))

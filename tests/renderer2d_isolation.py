import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-nexus-render-isolation-') as temporary:
    target = Path(temporary)
    shutil.copyfile(ROOT / 'xu.xun', target / 'xu.xun')
    for name in ('foundation', 'platform/present', 'rendering/two_d', 'resources/canvas',
                 'internal/file_snapshot', 'assets/shaders/two_d', 'build/canvas-shaders'):
        shutil.copytree(ROOT / name, target / name)
    (target / 'checks').mkdir()
    sdk = next(line for line in (ROOT / 'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (target / 'checks/xu.xun').write_text('module: example/renderer_isolation\nversion: !ver 0.1.0\n' + sdk + '\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    main = target / 'checks/main.xu'
    shutil.copyfile(ROOT / 'tests/canvas_gpu_checks.xu', main)
    assert not list(target.glob('*.xu'))
    assert not (target / 'gpu').exists() and not (target / 'integration/rendering').exists() and not (target / 'script').exists()
    assert not (target / 'rendering/three_d').exists()
    assert not (target / 'native/game_gpu.xulib').exists()
    assert not (target / 'platform/sdl_gpu').exists()
    binary = target / 'render-isolation'
    environment = os.environ.copy()
    environment['XU_NEXUS_SDL_LIBRARY'] = '/nonexistent/old-nexus-gpu-must-not-load'
    environment['XU_NEXUS_SDL_AUDIO_LIBRARY'] = '/nonexistent/audio-must-not-load'
    assert not (target / 'native').exists()
    assert not (target / 'platform/sdl_gpu').exists()
    assert not (target / 'platform/sdl_image').exists()
    assert not (target / 'platform/sdl_audio').exists()
    subprocess.run([os.environ.get('XU', 'xu'), 'build', str(main), '-o', str(binary)], cwd=target, check=True, timeout=60)
    subprocess.run([str(binary)], cwd=target, env=environment, check=True, timeout=30)
    # Add only the optional CPU PNG adapter; the GPU renderer above does not need it.
    for name in ('platform/sdl_image', 'resources/image', 'assets/image', 'integration/image_render/two_d'):
        shutil.copytree(ROOT / name, target / name)
    (target / 'native').mkdir()
    shutil.copyfile(ROOT / 'native/nexus_image.xulib', target / 'native/nexus_image.xulib')
    shutil.copyfile(ROOT / 'tests/renderer2d_isolation.xu', main)
    subprocess.run([os.environ.get('XU', 'xu'), 'build', str(main), '-o', str(binary)], cwd=target, check=True, timeout=60)
    subprocess.run([str(binary), str(ROOT / 'build/png-fixtures/rgba.png')], cwd=target,
                   env=environment, check=True, timeout=20)

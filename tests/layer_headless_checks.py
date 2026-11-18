import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# The SDK excludes directories named build from module source discovery.
with tempfile.TemporaryDirectory(prefix='xu-nexus-headless-') as temporary:
    target = Path(temporary)
    # Real root manifest unchanged; no native archive, scene, render or frontend.
    shutil.copyfile(ROOT / 'xu.xun', target / 'xu.xun')
    for name in ('foundation', 'formats', 'resources', 'internal'):
        shutil.copytree(ROOT / name, target / name)
    for name in ('bytecode', 'vm'):
        shutil.copytree(ROOT / 'script' / name, target / 'script' / name)
    check = target / 'checks/main.xu'
    check.parent.mkdir()
    (check.parent / 'xu.xun').write_text('module: example/layer_isolation\nversion: !ver 0.1.0\nxu: !ver 0.12.3\nrequire:\n  "github.com/xulang-org/nexus": file:..\n')
    shutil.copyfile(ROOT / 'tests/layer_headless_checks.xu', check)
    assert not (target / 'native').exists()
    tool = os.environ.get('XU', 'xu')
    binary = target / 'headless'
    subprocess.run([tool, 'build', str(check), '-o', str(binary)], cwd=target, check=True, timeout=60)
    environment = os.environ.copy()
    environment['XU_NEXUS_SDL_LIBRARY'] = '/nonexistent/layer-test-no-sdl'
    subprocess.run([str(binary), str(ROOT / 'build/glb-fixtures/triangle.glb'), str(ROOT / 'examples/glb_materials/assets/panels.glb'), str(ROOT / 'examples/scene_assets/assets/world.xuscene'), str(ROOT / 'examples/scene_av/assets/world.xuscene'), str(ROOT / 'build/scene-scripts/world.xuscene')], cwd=target,
                   env=environment, check=True, timeout=10)

import copy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('game_layers', ROOT / 'tools/check_layers.py')
layers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = layers
spec.loader.exec_module(layers)
policy = json.loads((ROOT / 'architecture.json').read_text())
units = layers.read_units(ROOT)
assert not layers.audit(units, policy)[0]


def changed(path, dependency=None, package=None):
    assert any(unit.path == path for unit in units), path
    result = []
    for unit in units:
        if unit.path == path:
            if dependency is not None:
                unit = replace(unit, imports=unit.imports + (dependency,))
            if package is not None:
                unit = replace(unit, package=package)
        result.append(unit)
    return result


def rejects(modified, needle, rules=policy):
    errors, _ = layers.audit(modified, rules)
    assert any(needle in error for error in errors), errors


module = policy['module']
rejects(changed('foundation/math/math3d.xu', module), 'forbidden dependency')
rejects(changed('formats/gltf/glb.xu', module + '/gpu'), 'forbidden dependency')
rejects(changed('rendering/three_d/device3d.xu', 'game_gpu_native'), 'forbidden external import')
rejects(changed('rendering/three_d/device3d.xu', module), 'forbidden dependency')
rejects(changed('rendering/three_d/device3d.xu', module + '/assets'), 'forbidden dependency')
rejects(changed('integration/rendering/three_d/scene3d.xu', 'game_gpu_native'), 'forbidden external import')
rejects(changed('rendering/two_d/renderer2d.xu', module), 'forbidden dependency')
rejects(changed('rendering/two_d/renderer2d.xu', module + '/assets/image'), 'forbidden dependency')
rejects(changed('assets/image/mod.xu', module + '/rendering'), 'forbidden dependency')
rejects(changed('resources/image/mod.xu', module + '/platform/sdl_gpu'), 'forbidden dependency')
rejects(changed('scene/scene_tree.xu', module + '/platform/sdl_gpu'), 'forbidden dependency')
rejects(changed('integration/image_render/two_d/mod.xu', module), 'forbidden dependency')
rejects(changed('audio/mixer/mod.xu', module), 'forbidden dependency')
rejects(changed('audio/mixer/stream.xu', 'os'), 'forbidden external import')
rejects(changed('audio/mixer/seek.xu', module + '/assets/audio'), 'forbidden dependency')
rejects(changed('integration/audio_stream/seek.xu', module + '/audio'), 'forbidden dependency')
rejects(changed('formats/wav/layout.xu', module + '/assets/audio'), 'forbidden dependency')
rejects(changed('integration/audio_stream/mod.xu', module), 'forbidden dependency')
rejects(changed('audio/mixer/mod.xu', module + '/platform/sdl_audio'), 'forbidden dependency')
rejects(changed('formats/wav/mod.xu', module + '/audio'), 'forbidden dependency')
rejects(changed('audio/mod.xu', 'nexus_audio_native'), 'native audio import must stay')
rejects(changed('resources/audio/mod.xu', 'nexus_audio_native'), 'native audio import must stay')
rejects(changed('script/host/mod.xu', 'os'), 'forbidden external import')
rejects(changed('script/vm/mod.xu', module + '/script/compiler'), 'cannot import script compiler')
rejects(changed('foundation/math/math3d.xu', package=module), 'package declaration')
rejects(units + [layers.Unit('unplanned/mod.xu', module + '/unplanned', ())], 'no architecture policy')
rejects(units + [layers.Unit('new_system.xu', module, ())], 'no architecture policy')
rejects(units + [layers.Unit('gpu/new_system.xu', module + '/gpu', ())], 'no architecture policy')
# Relaxing a package allowlist must not silently permit an upward layer edge.
layer_policy = copy.deepcopy(policy)
layer_policy['packages']['rendering/three_d']['local'].append('scene')
rejects(changed('rendering/three_d/device3d.xu', module + '/scene'), 'forbidden layer dependency', layer_policy)
rejects(units + [layers.Unit('runtime/example.xu', module + '/runtime', ())], 'reserved root')
cycle_policy = copy.deepcopy(policy)
cycle_policy['packages']['formats/gltf']['local'].append('assets/gltf')
rejects(changed('formats/gltf/glb.xu', module + '/assets/gltf'), 'dependency cycle', cycle_policy)
frontend_policy = copy.deepcopy(policy)
frontend_policy['packages']['foundation/math']['external'].append('xu/ast')
rejects(changed('foundation/math/math3d.xu', 'xu/ast'), 'Xu frontend import belongs to toolchain', frontend_policy)
print('PASS: layer gate rejects reverse dependencies, renderer/format coupling, native/frontend leaks, runtime file/compiler imports, wrong declarations, unplanned packages and cycles')

import tempfile
rejects(changed('resources/scene/mod.xu', module), 'forbidden dependency')
rejects(changed('formats/scene/decode.xu', module + '/integration/scene'), 'forbidden dependency')
rejects(changed('formats/scene/decode.xu', 'os'), 'forbidden external import')
with tempfile.TemporaryDirectory(prefix='xu-nexus-scene-values-') as temporary:
    root = Path(temporary)
    (root / 'resources/scene').mkdir(parents=True)
    original = (ROOT / 'resources/scene/mod.xu').read_text()
    (root / 'resources/scene/mod.xu').write_text(original)
    (root / 'scene').mkdir()
    (root / 'scene/scene_tree.xu').write_text((ROOT / 'scene/scene_tree.xu').read_text())
    (root / 'audio/mixer').mkdir(parents=True)
    (root / 'audio/mixer/mod.xu').write_text((ROOT / 'audio/mixer/mod.xu').read_text())
    (root / 'resources/scene/audio.xu').write_text((ROOT / 'resources/scene/audio.xu').read_text())
    for source in ['resources/scene/scripts.xu', 'script/host/scene_scripts.xu', 'script/host/signals.xu', 'script/bytecode/mod.xu']:
        (root / source).parent.mkdir(parents=True, exist_ok=True)
        (root / source).write_text((ROOT / source).read_text())
    assert not layers.scene_constants(root)
    (root / 'resources/scene/mod.xu').write_text(original.replace('pub const NODE_3D = 3', 'pub const NODE_3D = 4'))
    assert layers.scene_constants(root) == ['scene data/runtime constant differs: NODE_3D']
print('PASS: scene data/codec stay independent of runtime and files; node/process constants reject drift')

rejects(changed('resources/scene/surfaces.xu', module + '/integration/scene_render'), 'forbidden dependency')
rejects(changed('formats/scene/surfaces.xu', module + '/rendering'), 'forbidden dependency')
rejects(changed('integration/scene/nodes.xu', module + '/rendering'), 'forbidden dependency')
print('PASS: persistent surface data/codec and node adapters do not import GPU restoration')

rejects(changed('resources/scene/audio.xu', module + '/audio/mixer'), 'forbidden dependency')
rejects(changed('formats/scene/audio.xu', module + '/integration/scene_audio'), 'forbidden dependency')
rejects(changed('integration/scene_audio/mod.xu', module + '/rendering'), 'forbidden dependency')
print('PASS: audio scene data/codec do not import runtime services, and audio restoration stays independent of rendering')

rejects(changed('resources/scene/scripts.xu', module + '/script/host'), 'forbidden dependency')
rejects(changed('formats/scene/scripts.xu', module + '/script/compiler'), 'forbidden dependency')
rejects(changed('integration/scene_script/mod.xu', module + '/script/compiler'), 'forbidden dependency')
rejects(changed('integration/scene_script/mod.xu', module + '/rendering'), 'forbidden dependency')
print('PASS: script scene descriptions stay data-only; runtime restoration has no compiler or renderer dependency')

rejects(changed('resources/mesh/tangents.xu', module + '/rendering'), 'forbidden dependency')
rejects(changed('resources/mesh/mod.xu', module + '/platform/sdl_gpu'), 'forbidden dependency')
print('PASS: CPU mesh data and generation cannot import rendering or platform services')

for source in ('formats/obj/mod.xu','formats/stl/mod.xu'):
    rejects(changed(source, 'os'), 'forbidden external import')
    rejects(changed(source, 'gpu'), 'forbidden external import')
    rejects(changed(source, module + '/scene'), 'forbidden dependency')
rejects(changed('assets/mesh/mod.xu', module + '/rendering/three_d'), 'forbidden dependency')
rejects(changed('resources/mesh/faces.xu', module + '/formats/obj'), 'forbidden dependency')
print('PASS: OBJ/STL decode without files, GPU or scene; file dispatch and CPU face normals stay below rendering')

for source in ('formats/gltf/animation_data.xu','formats/gltf/skin_data.xu','formats/gltf/skin_pose.xu','formats/gltf/external_images.xu'):
    rejects(changed(source, 'os'), 'forbidden external import')
    rejects(changed(source, 'gpu'), 'forbidden external import')
    rejects(changed(source, module + '/scene'), 'forbidden dependency')
print('PASS: glTF animation sampling, skin palette and image URI descriptions remain pure CPU format data')

rejects(changed('examples/gpu_surface/main.xu', module + '/rendering'), 'forbidden dependency')
rejects(changed('examples/gpu_surface/main.xu', 'game_gpu_native'), 'forbidden external import')
print('PASS: standalone window/surface consumer cannot import engine rendering or native bridge')

rejects(changed('rendering/two_d/renderer2d.xu', module + '/platform/sdl_gpu'), 'forbidden dependency')
rejects(changed('rendering/two_d/renderer2d.xu', module + '/rendering/three_d'), 'forbidden dependency')
rejects(changed('resources/canvas/mod.xu', 'gpu'), 'forbidden external import')
rejects(changed('resources/canvas/mod.xu', module + '/rendering/two_d'), 'forbidden dependency')
rejects(changed('integration/rendering/two_d/canvas2d.xu', module + '/rendering/two_d'), 'forbidden dependency')
rejects(changed('assets/image/mod.xu', 'nexus_image_native'), 'native image import must stay')
rejects(changed('platform/sdl_image/mod.xu', 'gpu'), 'forbidden external import')
print('PASS: canvas data/scene recording stay CPU-only; 2D/3D standard GPU and CPU PNG boundaries stay separate')

rejects(changed('rendering/three_d/device3d.xu', module + '/platform/sdl_gpu'), 'forbidden dependency')

rejects(changed('resources/lighting/mod.xu', 'gpu'), 'forbidden external import')
rejects(changed('resources/lighting/mod.xu', module + '/scene'), 'forbidden dependency')
rejects(changed('resources/lighting/culling.xu', module + '/rendering/three_d'), 'forbidden dependency')
rejects(changed('resources/lighting/culling.xu', module + '/resources/mesh'), 'forbidden dependency')
rejects(changed('resources/mesh/bounds.xu', 'gpu'), 'forbidden external import')
rejects(changed('foundation/math/aabb3.xu', module + '/resources/lighting'), 'forbidden dependency')
rejects(changed('foundation/math/clip3.xu', module + '/scene'), 'forbidden dependency')
rejects(changed('foundation/math/clip3.xu', 'gpu'), 'forbidden external import')
rejects(changed('resources/lod/mod.xu', module + '/rendering/three_d'), 'forbidden dependency')
rejects(changed('resources/lod/mod.xu', module + '/scene'), 'forbidden dependency')
rejects(changed('resources/lod/mod.xu', 'gpu'), 'forbidden external import')
rejects(changed('integration/lighting/mod.xu', module + '/rendering/three_d'), 'forbidden dependency')
rejects(changed('integration/lighting/mod.xu', 'window'), 'forbidden external import')
print('PASS: CPU lighting descriptions and scene gathering remain independent of GPU, window and renderer services')

rejects(changed('resources/scene/lighting.xu', module + '/integration/lighting'), 'forbidden dependency')
rejects(changed('formats/scene/lighting.xu', module + '/scene'), 'forbidden dependency')
rejects(changed('formats/scene/lighting.xu', 'os'), 'forbidden external import')
rejects(changed('integration/scene_lighting/mod.xu', module + '/rendering/three_d'), 'forbidden dependency')
rejects(changed('integration/scene_lighting/mod.xu', module + '/script/host'), 'forbidden dependency')
rejects(changed('integration/scene_lighting/mod.xu', 'gpu'), 'forbidden external import')
print('PASS: persistent light descriptions/codec stay data-only; restoration remains independent of GPU, renderer, audio and script services')

with tempfile.TemporaryDirectory(prefix='xu-nexus-light-capacity-') as temporary:
    root = Path(temporary)
    for source in ('resources/lighting/mod.xu','rendering/three_d/shaders/lighting.inc'):
        target=root/source
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text((ROOT/source).read_text())
    assert not layers.lighting_constants(root)
    shader=root/'rendering/three_d/shaders/lighting.inc'
    shader.write_text(shader.read_text().replace('#define XU_MAX_LIGHTS 16','#define XU_MAX_LIGHTS 8'))
    assert layers.lighting_constants(root)==['lighting data/shader constant differs: MAX_LIGHTS']
print('PASS: CPU light budget and shader uniform capacity reject drift without requiring a GPU')

for source in ('resources/shadow/mod.xu','resources/shadow/spot.xu','resources/shadow/point.xu','resources/shadow/cascade_camera.xu','resources/shadow/cascades.xu'):
    rejects(changed(source, 'gpu'), 'forbidden external import')
    rejects(changed(source, module + '/scene'), 'forbidden dependency')
    rejects(changed(source, module + '/rendering/three_d'), 'forbidden dependency')
print('PASS: shadow coverage/bias descriptions remain pure CPU data')

rejects(changed('integration/ui/painter.xu', module + '/scene'), 'forbidden dependency')
rejects(changed('integration/ui/painter.xu', 'os'), 'forbidden external import')
rejects(changed('integration/ui/painter.xu', 'game_gpu_native'), 'forbidden external import')
rejects(changed('integration/ui/xdf.xu', 'gpu'), 'forbidden external import')
rejects(changed('integration/ui/input.xu', 'os'), 'forbidden external import')
rejects(changed('examples/ui_hud/main.xu', 'game_gpu_native'), 'forbidden external import')
rejects(changed('examples/ui_hud/main.xu', module + '/script/compiler'), 'cannot import script compiler')
print('PASS: integration/ui and ui_hud example respect layer, native, and toolchain boundaries')

rejects(changed('resources/steam/mod.xu', 'os'), 'forbidden external import')
rejects(changed('resources/steam/mod.xu', 'gpu'), 'forbidden external import')
rejects(changed('resources/steam/mod.xu', 'nexus_steam_native'), 'native steam import must stay')
rejects(changed('steam/mod.xu', 'nexus_steam_native'), 'native steam import must stay')
rejects(changed('integration/steam/mod.xu', 'nexus_steam_native'), 'native steam import must stay')
print('PASS: steam data, service, and integration packages respect native bridge and OS/GPU isolation')

rejects(changed('resources/console/mod.xu', 'os'), 'forbidden external import')
rejects(changed('resources/console/mod.xu', 'gpu'), 'forbidden external import')
rejects(changed('resources/console/mod.xu', 'nexus_console_native'), 'native console import must stay')
rejects(changed('console/mod.xu', 'nexus_console_native'), 'native console import must stay')
rejects(changed('integration/platform_services/mod.xu', 'nexus_console_native'), 'native console import must stay')
rejects(changed('integration/platform_services/mod.xu', 'nexus_steam_native'), 'native steam import must stay')
print('PASS: console and platform_services packages respect native bridge and OS/GPU isolation')

rejects(changed('resources/taptap/mod.xu', 'os'), 'forbidden external import')
rejects(changed('resources/taptap/mod.xu', 'gpu'), 'forbidden external import')
rejects(changed('resources/taptap/mod.xu', 'nexus_taptap_native'), 'native taptap import must stay')
rejects(changed('taptap/mod.xu', 'nexus_taptap_native'), 'native taptap import must stay')
rejects(changed('integration/platform_services/mod.xu', 'nexus_taptap_native'), 'native taptap import must stay')
print('PASS: taptap packages respect native bridge and OS/GPU isolation')

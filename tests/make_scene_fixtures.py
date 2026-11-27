#!/usr/bin/env python3
"""Current full-schema scene files and independent malformed input corpus."""
import copy
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'build/scene-fixtures'
out.mkdir(parents=True, exist_ok=True)
identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
def node(parent, name, kind='Node'):
    n = dict(parent=parent, name=name, type=kind, visible=True, process='inherit')
    if kind == 'Node2D': n['transform'] = [1, 0, 0, 1, 0, 0]
    if kind == 'Node3D': n['transform'] = identity.copy()
    return n
base = dict(format='xu.scene', version=1, nodes=[node(-1, '世界', 'Node3D'), node(0, 'Group'), node(1, 'Cube', 'Node3D'), node(0, 'HUD', 'Node2D')])
for key in ['resources','surfaces','audio_buses','audio_emitters','scripts','script_connections','lights']: base[key] = []
base['nodes'][2]['transform'][12:15] = [1.1234567890123457, 2, -3]
base['nodes'][3]['transform'] = [-2, .25, .5, 3, 12.75, -20.5]
base['nodes'][3]['visible'] = False
base['nodes'][3]['process'] = 'always'
def write(name, value):
    (out / name).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
write('valid.xuscene', base)
for kind in ['Node', 'Node2D', 'Node3D']:
    write(kind + '.xuscene', dict(format='xu.scene', version=1, nodes=[node(-1, kind, kind)], resources=[],surfaces=[],audio_buses=[],audio_emitters=[],scripts=[],script_connections=[],lights=[]))
rejects = []
def bad(name, mutate):
    value = copy.deepcopy(base); mutate(value); write(name + '.xuscene', value); rejects.append(name + '.xuscene')
def top(key, value): return lambda d: d.__setitem__(key, value)
def prop(key, value, index=2): return lambda d: d['nodes'][index].__setitem__(key, value)
for v in [9, 10]: bad('version-unsupported-'+str(v), top('version', v))
bad('version-7-missing-attachments', top('version', 7))

camera_lens = dict(vertical_fov=0.8765432101234567, near=0.25, far=50)
camera_scene = copy.deepcopy(base)
camera_scene['version'] = 2
camera_scene['nodes'][2]['camera'] = camera_lens
write('camera.xuscene', camera_scene)
bad('camera-v1', prop('camera', camera_lens))
for label, index, lens in [
    ('group', 1, camera_lens),
    ('2d', 3, camera_lens),
    ('null', 2, None),
    ('missing', 2, dict(vertical_fov=0.9, near=0.25)),
    ('unknown', 2, dict(camera_lens, aspect=1)),
    ('fov-zero', 2, dict(camera_lens, vertical_fov=0)),
    ('fov-wide', 2, dict(camera_lens, vertical_fov=3.14)),
    ('near-zero', 2, dict(camera_lens, near=0)),
    ('clip-order', 2, dict(camera_lens, far=0.25)),
    ('clip-string', 2, dict(camera_lens, far='50')),
    ('projection-overflow', 2, dict(camera_lens, near=1e308, far=1.5e308)),
]:
    def invalid_camera(d, node_index=index, invalid_lens=lens):
        d['version'] = 2
        d['nodes'][node_index]['camera'] = invalid_lens
    bad('camera-' + label, invalid_camera)
ortho_lens = dict(projection='orthographic', vertical_size=6, near=0.25, far=50)
view_lens = dict(design_width=320, design_height=180, zoom=2)
multi_camera_scene = copy.deepcopy(camera_scene)
multi_camera_scene['version'] = 3
multi_camera_scene['nodes'][0]['camera'] = camera_lens
multi_camera_scene['nodes'][2]['camera'] = ortho_lens
multi_camera_scene['nodes'].append(dict(node(3, 'View', 'Node2D'),
    camera=view_lens, transform=[1, 0, 0, 1, 2, 3]))
write('multi-camera.xuscene', multi_camera_scene)
for label, version, index, lens in [
    ('ortho-v2', 2, 2, ortho_lens),
    ('ortho-size', 3, 2, dict(ortho_lens, vertical_size=0)),
    ('ortho-near', 3, 2, dict(ortho_lens, near=-1)),
    ('ortho-depth', 3, 2, dict(ortho_lens, far=0.25)),
    ('ortho-conflict', 3, 2, dict(ortho_lens, vertical_fov=1)),
    ('projection-name', 3, 2, dict(ortho_lens, projection='custom')),
    ('2d-v2', 2, 3, view_lens),
    ('2d-on-3d', 3, 2, view_lens),
    ('3d-on-2d', 3, 3, ortho_lens),
    ('2d-size', 3, 3, dict(view_lens, design_height=16385)),
    ('2d-zoom', 3, 3, dict(view_lens, zoom=0.0001)),
    ('2d-unknown', 3, 3, dict(view_lens, rotation=1)),
]:
    def invalid_lens(d, schema=version, node_index=index, invalid=lens):
        d['version'] = schema
        d['nodes'][node_index]['camera'] = invalid
    bad('camera-' + label, invalid_lens)
for key in ['resources','surfaces','audio_buses','audio_emitters','scripts','script_connections','lights']: bad('missing-'+key, lambda d,k=key:d.pop(k))
bad('version-old', top('version', 0))
bad('version-string', top('version', '1'))
bad('version-fraction', top('version', 1.5))
bad('format', top('format', 'nexus.scene'))
bad('format-null', top('format', None))
bad('unknown-root', top('attachments', []))
bad('missing-version', lambda d: d.pop('version'))
bad('nodes-null', top('nodes', None))
bad('nodes-object', top('nodes', {}))
bad('nodes-empty', top('nodes', []))
bad('node-number', lambda d: d['nodes'].__setitem__(2, 2))
bad('node-null', lambda d: d['nodes'].__setitem__(2, None))
bad('missing-type', lambda d: d['nodes'][2].pop('type'))
bad('unknown-type', prop('type', 'RigidBody3D'))
bad('null-type', prop('type', None))
bad('unknown-node-property', prop('script', 'player.xus'))
bad('missing-visible', lambda d: d['nodes'][2].pop('visible'))
bad('visible-number', prop('visible', 1))
bad('null-name', prop('name', None))
for label, name in [('empty',''),('slash','a/b'),('dot','.'),('dotdot','..'),('control','a\nb'),('nul','a\x00b'),('del','a\x7fb'),('long','a'*256),('long-utf8','中'*86)]:
    bad('name-' + label, prop('name', name))
bad('duplicate-sibling', lambda d: d['nodes'].append(node(0, 'HUD', 'Node2D')))
bad('root-parent', prop('parent', 0, 0))
bad('second-root', prop('parent', -1))
bad('future-parent', prop('parent', 3))
bad('self-parent', prop('parent', 2))
bad('float-parent', prop('parent', 1.5))
bad('negative-parent', prop('parent', -2))
bad('parent-string', prop('parent', '1'))
bad('non-preorder', lambda d: d['nodes'].append(node(1, 'Late')))
bad('mode', prop('process', 'sometimes'))
bad('mode-number', prop('process', 0))
bad('group-transform', prop('transform', identity, 1))
bad('missing-transform', lambda d: d['nodes'][2].pop('transform'))
bad('short-transform', prop('transform', identity[:-1]))
bad('long-transform', prop('transform', identity + [0]))
bad('null-transform', prop('transform', None))
bad('object-transform', prop('transform', {}))
bad('transform-string', prop('transform', ['1'] + identity[1:]))
bad('transform-null', prop('transform', [None] + identity[1:]))
bad('projective-transform', prop('transform', identity[:3] + [.1] + identity[4:]))
bad('wrong-affine-w', prop('transform', identity[:-1] + [2]))
bad('2d-length', prop('transform', [1, 0, 0, 1, 0], 3))
bad('too-many-nodes', top('nodes', [node(-1, 'root')] + [node(0, 'n'+str(i)) for i in range(4096)]))
bad('too-deep', top('nodes', [node(i-1, 'n'+str(i)) for i in range(257)]))
raw = json.dumps(base, ensure_ascii=False).encode()
for name, value in {
    'duplicate-key': raw.replace(b'"version": 1', b'"version": 1, "version": 1'),
    'invalid-utf8': raw.replace(b'Cube', b'\xffbad'),
    'truncated': raw[:-4],
    'trailing': raw + b'false',
    'overflow': raw.replace(b'1.1234567890123457', b'1e999'),
    'nan': raw.replace(b'1.1234567890123457', b'NaN'),
    'oversized': b' ' * (4194304 + 1),
    'json-budget': b'{"format":"xu.scene","version":1,"nodes":[],"unsupported":[' + b'0,'*131072 + b'0]}'
}.items():
    (out / (name + '.xuscene')).write_bytes(value); rejects.append(name + '.xuscene')
(out / 'reject-list.txt').write_text('\n'.join(rejects) + '\n')
(out / 'destination-dir').mkdir(exist_ok=True)
print(f'Scene fixtures: {len(rejects)} malformed/version/topology/transform/budget rejects; mixed 2D/3D and all root kinds')

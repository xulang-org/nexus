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
for v in [2,3,4,5]: bad('version-unsupported-'+str(v), top('version', v))
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

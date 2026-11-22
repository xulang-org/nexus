"""Exercise versioned LOD files through the regular scene preview process."""
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'build/scene-asset-fixtures'
OUTPUT = ROOT / 'build/scene-lod-preview-results'


def render(scene, name, report, *args):
    path = OUTPUT / f'{name}.png'
    result = subprocess.run(
        [str(ROOT / 'build/scene-lod-preview'), '--frames', '1', '--scene', str(scene),
         '--capture', str(path), *map(str, args)],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=30,
    )
    assert report in result.stdout, result.stdout + result.stderr
    png = path.read_bytes()
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    return png


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    captures = []
    for scene, count, coarse in (('lod-authored', 2, 0), ('lod-far', 1, 1)):
        source = FIXTURES / f'{scene}.xuscene'
        saved = FIXTURES / f'{scene}-saved.xuscene'
        report = f'Submitted {count} triangles, {coarse} coarser LOD surfaces'
        before = render(source, scene, report, '--save', saved)
        after = render(saved, scene + '-restored', report)
        assert before == after, scene
        original, restored = (json.loads(path.read_text()) for path in (source, saved))
        assert restored['version'] == 6
        assert restored['surfaces'] == original['surfaces'] and restored['resources'] == original['resources']
        captures.append(before)
    assert captures[0] != captures[1]
    print('PASS: new-process scene preview restores both LODs and their source hashes; near/far submit 2/1 triangles')


if __name__ == '__main__':
    main()

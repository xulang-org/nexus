#!/usr/bin/env python3
"""Cross-backend 3D shader parity and syntax checks across Metal, Vulkan GLSL 450, and D3D12 HLSL SM 6.0."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SHADERS_DIR = ROOT / 'rendering/three_d/shaders'
sys.path.insert(0, str(ROOT / 'tools'))
import mesh_shaders  # noqa: E402


def check_balanced(text: str, label: str) -> None:
    stripped = re.sub(r'//.*', '', text)
    pairs = {'(': ')', '{': '}', '[': ']'}
    closing = {v: k for k, v in pairs.items()}
    stack = []
    for ch in stripped:
        if ch in pairs:
            stack.append(ch)
        elif ch in closing:
            if not stack or stack[-1] != closing[ch]:
                raise AssertionError(f'{label}: unmatched bracket {ch!r}')
            stack.pop()
    if stack:
        raise AssertionError(f'{label}: unclosed brackets {stack}')


def main() -> int:
    discovered = mesh_shaders.discover_shaders(SHADERS_DIR)
    assert len(discovered) == 45, f'expected 45 3D shaders, found {len(discovered)}'

    has_metal = False
    if shutil.which('xcrun') is not None:
        probe = subprocess.run(['xcrun', 'metal', '--version'], capture_output=True, text=True)
        has_metal = probe.returncode == 0
    has_glslang = shutil.which('glslangValidator') is not None
    has_dxc = shutil.which('dxc') is not None

    with tempfile.TemporaryDirectory(prefix='nexus-shader-check-') as tmpdir:
        tmp_path = Path(tmpdir)
        for shader, stage, _profile in discovered:
            msl_path = SHADERS_DIR / f'{shader}.msl'
            glsl_path = SHADERS_DIR / shader
            hlsl_path = SHADERS_DIR / f'{shader}.hlsl'
            assert msl_path.is_file(), f'missing MSL shader: {msl_path}'
            assert glsl_path.is_file(), f'missing GLSL shader: {glsl_path}'
            assert hlsl_path.is_file(), f'missing HLSL shader: {hlsl_path}'

            msl_text = mesh_shaders.expand_includes(msl_path.read_bytes(), SHADERS_DIR).decode('utf-8')
            glsl_text = glsl_path.read_text(encoding='utf-8')
            hlsl_text = hlsl_path.read_text(encoding='utf-8')

            assert 'main0(' in msl_text, f'{msl_path.name}: missing main0 entrypoint'
            assert '#version 450' in glsl_text, f'{glsl_path.name}: missing #version 450'
            assert re.search(r'\bvoid\s+main\s*\(', glsl_text), f'{glsl_path.name}: missing void main()'
            assert re.search(r'\bmain\s*\(', hlsl_text), f'{hlsl_path.name}: missing main(...) entrypoint'

            check_balanced(msl_text, msl_path.name)
            check_balanced(glsl_text, glsl_path.name)
            check_balanced(hlsl_text, hlsl_path.name)

            if stage == 'comp':
                assert 'local_size_x' in glsl_text, f'{glsl_path.name}: missing local_size_x layout'
                assert '[numthreads(' in hlsl_text, f'{hlsl_path.name}: missing [numthreads(...)]'
            elif stage == 'vert':
                assert 'gl_Position' in glsl_text, f'{glsl_path.name}: missing gl_Position write'
                assert 'SV_Position' in hlsl_text, f'{hlsl_path.name}: missing SV_Position semantic'
            elif stage == 'frag':
                if shader == 'shadow.frag':
                    assert 'SV_Depth' in hlsl_text or 'SV_Target0' in hlsl_text
                else:
                    assert 'SV_Target0' in hlsl_text, f'{hlsl_path.name}: missing SV_Target0 semantic'

            # Verify uniform buffer set/space conventions match SDL3 GPU rules.
            if stage == 'vert' and ('cbuffer' in hlsl_text or ' uniform ' in glsl_text):
                assert 'space1' in hlsl_text and 'set = 1' in glsl_text.replace(' ', '').replace('set=1', 'set = 1'), \
                    f'{shader}: vertex uniform must use set=1 / space1'
            if stage == 'frag' and 'cbuffer' in hlsl_text:
                assert 'space3' in hlsl_text and 'set = 3' in glsl_text.replace(' ', '').replace('set=3', 'set = 3'), \
                    f'{shader}: fragment uniform must use set=3 / space3'
            if stage == 'comp' and 'cbuffer' in hlsl_text:
                assert 'space2' in hlsl_text and 'set = 2' in glsl_text.replace(' ', '').replace('set=2', 'set = 2'), \
                    f'{shader}: compute uniform must use set=2 / space2'

            if has_metal:
                expanded_msl = tmp_path / f'{shader}.metal'
                expanded_msl.write_text(msl_text, encoding='utf-8')
                res = subprocess.run(
                    ['xcrun', 'metal', '-x', 'metal', '-std=macos-metal2.4', '-fsyntax-only', str(expanded_msl)],
                    capture_output=True, text=True
                )
                if res.returncode != 0:
                    raise AssertionError(f'xcrun metal failed for {shader}.msl:\n{res.stderr}')

            if has_glslang:
                res = subprocess.run(
                    ['glslangValidator', '-V', '-I' + str(SHADERS_DIR), '-o', str(tmp_path / f'{shader}.spv'), str(glsl_path)],
                    capture_output=True, text=True
                )
                if res.returncode != 0:
                    raise AssertionError(f'glslangValidator failed for {shader}:\n{res.stderr}{res.stdout}')

            if has_dxc:
                res = subprocess.run(
                    ['dxc', '-T', _profile, '-E', 'main', '-I', str(SHADERS_DIR), '-Fo', str(tmp_path / f'{shader}.dxil'), str(hlsl_path)],
                    capture_output=True, text=True
                )
                if res.returncode != 0:
                    raise AssertionError(f'dxc failed for {shader}.hlsl:\n{res.stderr}')

        mesh_shaders.prepare_mesh('metal', tmp_path / 'out-metal')
        for shader, _, _ in discovered:
            assert (tmp_path / 'out-metal' / f'{shader}.bin').stat().st_size > 0

    print(
        f'PASS: shader_cross_backend_checks ({len(discovered)}/45 3D shaders verified across MSL/GLSL450/HLSL-SM6; '
        f'metal={has_metal}, glslang={has_glslang}, dxc={has_dxc})'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

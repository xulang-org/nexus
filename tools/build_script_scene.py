#!/usr/bin/env python3
"""Offline source compilation and pinned scene publication into an asset generation."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile


def portable(name):
    if not isinstance(name, str) or not name or len(name.encode()) > 1024 or any(c in name for c in '\\:\x00') or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError('invalid portable resource path')
    if any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('resource paths must be normalized and relative')
    return Path(*PurePosixPath(name).parts)


def build(project_path, output, tool):
    project_path = project_path.resolve()
    project = json.loads(project_path.read_text())
    template_path = project_path.parent / portable(project['template'])
    scene = json.loads(template_path.read_text())
    arrays = {'nodes', 'resources', 'surfaces', 'audio_buses', 'audio_emitters', 'scripts', 'script_connections', 'lights'}
    if not isinstance(scene, dict) or set(scene) != arrays | {'format', 'version'}:
        raise ValueError('scene template must provide the complete current schema')
    if scene['format'] != 'xu.scene' or type(scene['version']) is not int or scene['version'] != 1:
        raise ValueError('script scene template must use xu.scene version 1')
    if any(not isinstance(scene[name], list) for name in arrays):
        raise ValueError('scene template collections must be arrays')
    scripts = {item['uid']: item for item in project['scripts']}
    references = scene['resources']
    identities = [item['uid'] for item in references]
    paths = [item['path'] for item in references]
    if len(references) > 32 or len(set(paths)) != len(paths) or len(scripts) != len(project['scripts']):
        raise ValueError('resource paths and script mappings must be unique and bounded')
    if len(set(identities)) != len(identities) or set(scripts) != {r['uid'] for r in references if r['type'] == 'xu_bytecode'}:
        raise ValueError('script source mappings must match unique template resource IDs')
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.scene-candidate-', dir=output.parent))
    temporary_scene = None
    try:
        for reference in references:
            if reference['type'] not in {'glb_model', 'wav_clip', 'xu_bytecode'}:
                raise ValueError('unsupported source resource type')
            target = stage / portable(reference['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            if reference['type'] == 'xu_bytecode':
                source = scripts[reference['uid']]
                subprocess.run([str(tool.resolve()), 'build', str(project_path.parent / portable(source['source'])),
                    str(project_path.parent / portable(source['schema'])), str(target)], check=True)
            else:
                shutil.copyfile(template_path.parent / portable(reference['path']), target)
            reference['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
        # Include paths/types/IDs in the generation key, not just concatenated bytes.
        generation = hashlib.sha256(json.dumps(references, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        relative_generation = Path('resources') / generation
        destination = output.parent / relative_generation
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            for reference in references:
                existing = destination / portable(reference['path'])
                if not existing.is_file() or hashlib.sha256(existing.read_bytes()).hexdigest() != reference['sha256']:
                    raise ValueError('existing immutable asset generation differs')
        else:
            os.rename(stage, destination)
        for reference in references:
            published_path = (relative_generation / portable(reference['path'])).as_posix()
            portable(published_path)
            reference['path'] = published_path
        encoded = (json.dumps(scene, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        if len(encoded) > 4194304:
            raise ValueError('encoded scene exceeds 4 MiB')
        with tempfile.NamedTemporaryFile(prefix=output.name+'.tmp-', dir=output.parent, delete=False) as handle:
            temporary_scene = Path(handle.name)
            handle.write(encoded)
        os.replace(temporary_scene, output)
        temporary_scene = None
        print(json.dumps({'scene': str(output), 'generation': generation, 'scripts': len(scripts)}))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if temporary_scene is not None:
            temporary_scene.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tool', type=Path, default=Path('build/xu-nexus-script'))
    args = parser.parse_args()
    build(args.project, args.output, args.tool)

if __name__ == '__main__':
    main()

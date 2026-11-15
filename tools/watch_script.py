#!/usr/bin/env python3
"""Compile bounded Xu script snapshots in a child; publish only successful builds."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
import time

MAX_SOURCE = 16384


def snapshot(path):
    with path.open('rb') as stream:
        data = stream.read(MAX_SOURCE + 1)
    if len(data) > MAX_SOURCE:
        raise ValueError(f'{path}: exceeds {MAX_SOURCE} bytes')
    return data


def compile_snapshot(tool, source, schema, output, source_path):
    with tempfile.TemporaryDirectory(prefix='xu-script-') as directory:
        source_copy = Path(directory) / 'source.xus'
        schema_copy = Path(directory) / 'schema.json'
        source_copy.write_bytes(source)
        schema_copy.write_bytes(schema)
        try:
            result = subprocess.run([str(tool), 'build', str(source_copy), str(schema_copy), str(output)],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5)
        except subprocess.TimeoutExpired:
            print(f'{source_path}: compiler timed out; output left unchanged', flush=True)
            return False
        message = (result.stdout + result.stderr).replace(str(source_copy), str(source_path))
        if message:
            print(message, end='' if message.endswith('\n') else '\n', flush=True)
        if result.returncode:
            print(f'{source_path}: compile rejected (exit {result.returncode}); output left unchanged', flush=True)
        return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    tool, source_path, schema_path, output = (p.resolve() for p in
                                            (args.tool, args.source, args.schema, args.output))
    observed = None
    error = None
    while True:
        try:
            source, schema = snapshot(source_path), snapshot(schema_path)
            digest = hashlib.sha256(source + b'\0' + schema).digest()
            error = None
            if digest != observed:
                observed = digest
                ok = compile_snapshot(tool, source, schema, output, source_path)
                if args.once:
                    return 0 if ok else 1
        except (OSError, ValueError) as failure:
            if str(failure) != error:
                print(str(failure), flush=True)
                error = str(failure)
            if args.once:
                return 1
        time.sleep(0.2)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)

#!/usr/bin/env python3
"""Own both source watchers while the Xu GPU demonstration runs."""
from pathlib import Path
import os
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def stop_watcher(watcher):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(watcher.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(watcher.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        watcher.wait(timeout=6)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            watcher.kill()
        else:
            try:  # It may have exited between timeout and termination.
                os.killpg(watcher.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        watcher.wait()


def main():
    commands = []
    for name in ('player', 'indicator'):
        command = [sys.executable, str(ROOT / 'tools/watch_script.py'),
                   '--tool', str(ROOT / 'build/xu-nexus-script'),
                   '--source', str(ROOT / f'examples/script_reload/{name}.xus'),
                   '--schema', str(ROOT / f'examples/script_reload/{name}.schema.json'),
                   '--output', str(ROOT / f'build/{name}.xubc')]
        first = subprocess.run(command + ['--once'], cwd=ROOT)
        if first.returncode:
            return first.returncode
        commands.append(command)
    watchers = []
    try:
        for command in commands:
            watchers.append(subprocess.Popen(command, cwd=ROOT, start_new_session=os.name != 'nt'))
        return subprocess.call([str(ROOT / 'build/script-reload'), *sys.argv[1:]], cwd=ROOT)
    finally:
        for watcher in watchers:
            stop_watcher(watcher)


if __name__ == '__main__':
    raise SystemExit(main())

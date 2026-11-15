#!/usr/bin/env python3
"""Require the SDK selected by the product manifest; never select an older compiler."""
import argparse
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected = re.search(r'^xu: !ver ([^\s]+)$', (root/'xu.xun').read_text(), re.MULTILINE).group(1)
    result = subprocess.run([args.xu, '--version'], capture_output=True, text=True, timeout=10)
    match = re.search(r'Xu Compiler Toolchain v([^\s]+)', result.stdout + result.stderr)
    actual = match.group(1) if match else 'unknown'
    if result.returncode or actual != expected:
        print(f'Xu SDK {expected} is required; selected compiler reports {actual}. Set XU to that SDK executable.', file=sys.stderr)
        return 1
    print(f'PASS: Xu SDK {actual}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

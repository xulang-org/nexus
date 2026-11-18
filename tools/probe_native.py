#!/usr/bin/env python3
"""Exercise scalar, stack-argument and borrowed-array native calls without SDL, rendering, or engine source."""
import argparse
import json
from pathlib import Path
import re
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root/'build/native-probe'
    target.mkdir(parents=True, exist_ok=True)
    sdk = re.search(r'^xu: !ver (\S+)$', (root/'xu.xun').read_text(), re.MULTILINE).group(1)
    (target/'xu.xun').write_text('module: example/nexus_native_probe\nversion: !ver 0.1.0\nxu: !ver '+sdk+'\nnative:\n  nexus_native_probe: file:./probe.xulib\n')
    manifest = {'module': 'nexus_native_probe', 'abi': 'xu-c-2', 'exports': [
        {'name': 'increment', 'params': ['int'], 'ret': 'int'},
        {'name': 'weighted', 'params': ['int'] * 12, 'ret': 'int'},
        {'name': 'total', 'params': ['i64_span'], 'ret': 'int'},
        {'name': 'mutate', 'params': ['i64_span_mut'], 'ret': 'int'},
        {'name': 'clear', 'params': ['i64_span_mut'], 'ret': 'void'},
        {'name': 'mixed', 'params': ['int', 'i64_span', 'int', 'i64_span_mut', 'int', 'i64_span', 'int', 'i64_span_mut', 'int', 'int'], 'ret': 'int'}]}
    (target/'native.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (target/'probe.c').write_text('''#include "xu_native.h"
#define API(name) XU_NATIVE_SYMBOL(xu_nexus_native_probe_##name)
xu_int API(increment)(xu_int value) { return value + 1; }
xu_int API(weighted)(xu_int a, xu_int b, xu_int c, xu_int d, xu_int e, xu_int f,
                    xu_int g, xu_int h, xu_int i, xu_int j, xu_int k, xu_int l) {
    return a+2*b+3*c+4*d+5*e+6*f+7*g+8*h+9*i+10*j+11*k+12*l;
}
xu_int API(total)(const xu_i64_span *s) {
    xu_int result=0;
    for (xu_int i=0; i<s->len; ++i) result+=s->data[i];
    return result;
}
xu_int API(mutate)(const xu_i64_span_mut *s) {
    for (xu_int i=0; i<s->len; ++i) s->data[i]+=7;
    return s->len;
}
void API(clear)(const xu_i64_span_mut *s) {
    for (xu_int i=0; i<s->len; ++i) s->data[i]=0;
}
xu_int API(mixed)(xu_int a, const xu_i64_span *b, xu_int c, const xu_i64_span_mut *d,
                 xu_int e, const xu_i64_span *f, xu_int g, const xu_i64_span_mut *h,
                 xu_int i, xu_int j) {
    xu_int base=a+c+e+g+i+j;
    d->data[0]=base+API(total)(b);
    h->data[0]=base+API(total)(f);
    return d->data[0]+h->data[0];
}
''')
    (target/'main.xu').write_text('''@main
#nexus_native_probe
struct Holder { pad int
    values []int }
fn holder_sum(value &Holder) int { << nexus_native_probe.total(&value.values) }
fn main() int {
    assert(nexus_native_probe.increment(41) == 42)
    assert(nexus_native_probe.weighted(1,2,3,4,5,6,7,8,9,10,11,12) == 650)
    $values := [1,2,3]
    shared := ~values
    assert(nexus_native_probe.total(&values) == 6)
    assert(nexus_native_probe.mutate($&values) == 3)
    assert(values[0] == 8 && values[2] == 10 && shared[0] == 1 && shared[2] == 3)
    $empty := []int{}
    assert(nexus_native_probe.total(&empty) == 0 && nexus_native_probe.mutate($&empty) == 0)
    $holder := Holder{pad: 123456, values: [2,4]}
    assert(holder_sum(&holder) == 6)
    holder_copy := ~holder
    assert(nexus_native_probe.mutate($&holder.values) == 2)
    assert(holder_sum(&holder) == 20 && holder_sum(&holder_copy) == 6)
    $first := [0]
    $second := [0]
    other := [11,13]
    assert(nexus_native_probe.mixed(1,&shared,3,$&first,5,&other,7,$&second,9,10) == 100)
    assert(first[0] == 41 && second[0] == 59)
    nexus_native_probe.clear($&values)
    assert(nexus_native_probe.total(&values) == 0 && nexus_native_probe.total(&shared) == 6)
    println("PASS: native 41 -> 42, twelve scalar arguments, mixed stack/spans, empty arrays, borrowed fields, mutable COW isolation and void result")
    << 0
}
''')
    host_os = {'Darwin': 'macos', 'Linux': 'linux', 'Windows': 'windows'}[platform.system()]
    host_arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}[platform.machine()]
    host = host_os+'-'+host_arch
    subprocess.run([args.xu, 'native', 'compile', '--manifest', str(target/'native.json'),
                    '--target', host, '-o', str(target/'probe.a'), str(target/'probe.c')], cwd=root, check=True)
    subprocess.run([args.xu, 'native', 'pack', '--manifest', str(target/'native.json'),
                    '--slice', host+'='+str(target/'probe.a'), '-o', str(target/'probe.xulib')], cwd=root, check=True)
    binary = target/'probe'
    subprocess.run([args.xu, 'build', str(target/'main.xu'), '-o', str(binary)], cwd=target, check=True)
    subprocess.run([str(binary)], cwd=target, check=True)
    print('PASS: native archive packaging, import, linking and engine ABI execution')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print('Native probe failed; reproducible sources are in build/native-probe. No older SDK was selected.', file=sys.stderr)
        raise SystemExit(error.returncode or 1)

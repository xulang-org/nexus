"""Bound real resident growth while clearing and recording 100,000 CPU frames."""
from pathlib import Path
import os
import platform
import re
import select
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
XU = os.environ.get('XU', 'xu')
if platform.system() not in ('Darwin', 'Linux'):
    raise SystemExit('canvas memory check requires ps RSS sampling on macOS/Linux')

SOURCE = '''@main
canvas #"github.com/xulang-org/nexus/resources/canvas"
fm #"github.com/xulang-org/nexus/foundation/math"
fn inaccessible(batch &canvas.Batch2D, index int) bool {
    batch.vertex_at(index) or (err) { << true }
    << false
}
fn record(batch $&canvas.Batch2D, frame int) int {
    batch.clear()
    assert(batch.vertex_count() == 0)
    for i in 0:20 { batch.quad(fm.rect2(f64(frame % 4) + f64(i),0.0,20.0,20.0),
        fm.identity(),4294967295) or >> }
    assert(batch.vertex_count() == 120)
    first := batch.vertex_at(0) or >>
    assert(first.point.x == f64(frame % 4))
    << 0
}
fn run() int {
    $batch := canvas.new_batch()
    assert(inaccessible(&batch, 0))
    for i in 0:10000 { record($&batch, i) or >> }
    println("warm")
    sleep_ns(1000000000)
    for i in 0:90000 { record($&batch, i) or >> }
    batch.clear()
    batch.quad(fm.rect2(0.0,0.0,1.0,1.0),fm.identity(),4294967295) or >>
    assert(batch.vertex_count() == 6 && inaccessible(&batch,6))
    println("steady")
    sleep_ns(1000000000)
    << 0
}
fn main() int { << run() or (err) { eprintln(err.msg())
    << 1 } }
'''

def rss(pid):
    return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(pid)], text=True).strip()) * 1024

def marker(child, expected):
    assert select.select([child.stdout], [], [], 30)[0], 'timed out waiting for memory phase'
    actual = child.stdout.readline().strip()
    assert actual == expected, (actual, child.stderr.read() if child.poll() is not None else '')
    return rss(child.pid)

with tempfile.TemporaryDirectory(prefix='canvas memory ') as directory:
    root = Path(directory)
    version = re.search(r'^xu: !ver (.+)$', (ROOT/'xu.xun').read_text(), re.M)[1]
    (root/'xu.xun').write_text(f'module: test/canvas_memory\nversion: !ver 0.1.0\nxu: !ver {version}\nrequire:\n  "github.com/xulang-org/nexus": file:{ROOT}\n')
    (root/'main.xu').write_text(SOURCE)
    binary = root/'memory-check'
    subprocess.run([XU, 'build', root, '-o', binary], check=True)
    child = subprocess.Popen([binary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             env=dict(os.environ, SDL_VIDEODRIVER='nonexistent', XU_SDL_LIBRARY='/nonexistent'))
    try:
        warm = marker(child, 'warm')
        steady = marker(child, 'steady')
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0, stdout + stderr
        growth = max(0, steady - warm)
        assert growth <= 16 * 1024 * 1024, f'canvas resident growth: {growth} bytes'
        print(f'PASS: 100000 canvas frames, resident growth {growth} bytes; cleared/shrunk geometry inaccessible')
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()

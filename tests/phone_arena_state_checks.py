"""Exercise the actual sample checkpoint codec/atomic storage without SDL."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
XU = os.environ.get('XU', 'xu')
SOURCE = r'''@main
fn rejects(raw string, solids &[]fm.Rect2) bool {
    decode_checkpoint(&raw, solids) or (err) { << true }
    << false
}
fn save_fails(path string, state &Checkpoint, solids &[]fm.Rect2) bool {
    save_checkpoint(path, state, solids) or (err) { << true }
    << false
}
fn run() int {
    args := os.args()
    root := args[1]
    path := root + "/arena.json"
    solids := [fm.rect2(122.0,75.0,14.0,225.0)]
    initial := load_checkpoint(path + "", &solids) or >>
    assert(initial.position.x == 42.0 && initial.collected == 0 && !initial.paused)
    state := Checkpoint{position: fm.vec2(61.123456789,215.000000001), collected: 37, paused: true}
    raw := encode_checkpoint(&state, &solids) or >>
    decoded := decode_checkpoint(&raw, &solids) or >>
    assert(decoded.position.x == state.position.x && decoded.position.y == state.position.y)
    assert(decoded.collected == 37 && decoded.paused)
    save_checkpoint(path + "", &state, &solids) or >>
    loaded := load_checkpoint(path + "", &solids) or >>
    assert(loaded.position.x == state.position.x && loaded.collected == 37 && loaded.paused)
    invalid := ["", "{", "[]", "{}",
        "{\"version\":2,\"x\":42,\"y\":180,\"collected\":0,\"paused\":false}",
        "{\"version\":1,\"x\":130,\"y\":180,\"collected\":0,\"paused\":false}",
        "{\"version\":1,\"x\":-1,\"y\":180,\"collected\":0,\"paused\":false}",
        "{\"version\":1,\"x\":42,\"y\":180,\"collected\":64,\"paused\":false}",
        "{\"version\":1,\"x\":42,\"y\":180,\"collected\":1.5,\"paused\":false}",
        "{\"version\":1,\"x\":1e999,\"y\":180,\"collected\":0,\"paused\":false}",
        "{\"version\":1,\"x\":42,\"y\":180,\"collected\":0,\"extra\":false}"]
    for bad in invalid { assert(rejects(bad + "", &solids)) }
    // A failed replacement must not destroy an existing directory or leave staging files.
    protected := root + "/protected"
    os.mkdir(protected + "") or >>
    os.write(protected + "/original", "retained") or >>
    assert((save_fails(protected + "", &state, &solids) or >>) && (os.read(protected + "/original") or >>) == "retained")
    entries := os.entries(root + "") or >>
    for entry in entries {
        assert(!strings.contains(&entry.name, ".tmp-"))
    }
    os.write(path + "", "malformed") or >>
    recovered := load_checkpoint(path + "", &solids) or >>
    assert(recovered.position.x == 42.0 && recovered.collected == 0)
    $preserved := false
    recovered_entries := os.entries(root + "") or >>
    for entry in recovered_entries {
        if strings.contains(&entry.name, ".rejected-") {
            assert((os.read(root + "/" + entry.name) or >>) == "malformed")
            preserved = true
        }
    }
    assert(preserved)
    println("arena checkpoint: strict codec, exact float round-trip, atomic failure cleanup and corrupt-file recovery PASS")
    << 0
}
fn main() int { << run() or (err) { eprintln(err.msg())
    << 1 } }
'''

with tempfile.TemporaryDirectory(prefix='phone checkpoint ') as directory:
    temporary = Path(directory)
    module = temporary/'module'
    module.mkdir()
    (module/'state.xu').write_text((ROOT/'examples/phone_arena/state.xu').read_text())
    (module/'main.xu').write_text('@main\n#strings\n#os\nfm #"github.com/xulang-org/nexus/foundation/math"\n' + SOURCE.removeprefix('@main\n'))
    (module/'xu.xun').write_text('module: test/phone_checkpoint\nversion: !ver 0.1.0\nxu: !ver 0.12.5\nrequire:\n  "github.com/xulang-org/nexus": file:' + str(ROOT) + '\n')
    binary = temporary/'check'
    data = temporary/'data'
    data.mkdir()
    subprocess.run([XU, 'build', module, '-o', binary], check=True)
    subprocess.run([binary, data], check=True, env=dict(os.environ, SDL_VIDEODRIVER='nonexistent', XU_SDL_LIBRARY='/nonexistent'))

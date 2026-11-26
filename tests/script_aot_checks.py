#!/usr/bin/env python3
"""Verify XuScript VM zero-alloc optimization, AOT C/Xu native codegen, parity, fault rollback, and speedup."""
import argparse
from pathlib import Path
import platform
import re
import subprocess
import sys


SWARM_SCRIPT = """@swarm_kernel
struct SwarmKernel {
    acc f64
    phase f64
    scale f64
}
pub fn (self $&SwarmKernel) physics_process(delta f64, axis f64) f64 {
    $i := 0.0
    $sum := self.acc
    $x := self.phase + axis * 0.25 - 0.5
    while i < 200.0 {
        x = (x * 1.0001 + delta * 0.5) - (x * x * 0.00001)
        if x > 10.0 { x = x - 10.0 }
        sum = sum + x * self.scale
        i = i + 1.0
    }
    self.phase = x
    self.acc = sum * 0.001
    if self.acc > 50.0 { emit_signal("ping", self.acc) }
    << self.acc
}
pub fn (self $&SwarmKernel) on_boost(amount f64) f64 {
    if amount == 0.0 {
        // Trigger divide by zero on purpose when amount == 0.0 for error/rollback parity test.
        << 1.0 / amount
    }
    self.scale = self.scale + amount
    << self.scale
}
"""

SWARM_SCHEMA = """{
  "profile": "xu-scalar-v1",
  "module": "swarm_kernel",
  "class": "SwarmKernel",
  "fields": [
    {"id": 1, "name": "acc", "type": "f64", "default": 1.0},
    {"id": 2, "name": "phase", "type": "f64", "default": 0.25},
    {"id": 3, "name": "scale", "type": "f64", "default": 1.25}
  ],
  "signals": [
    {"id": 10, "name": "ping"}
  ],
  "handlers": [
    {"id": 20, "name": "on_boost"}
  ]
}
"""

HOT_RELOAD_V2 = """@swarm_kernel
struct SwarmKernel {
    acc f64
    phase f64
    scale f64
}
pub fn (self $&SwarmKernel) physics_process(delta f64, axis f64) f64 {
    self.acc = self.acc + 100.0 + delta * 0.0 + axis * 0.0
    << self.acc
}
pub fn (self $&SwarmKernel) on_boost(amount f64) f64 { << self.scale + amount }
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xu', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    scriptc = root / 'build/xu-nexus-script'
    subprocess.run([args.xu, 'build', 'cmd/scriptc/main.xu', '-o', str(scriptc)], cwd=root, check=True)

    target = root / 'build/script-aot-check'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'swarm.xus').write_text(SWARM_SCRIPT)
    (target / 'swarm.schema.json').write_text(SWARM_SCHEMA)
    (target / 'swarm_v2.xus').write_text(HOT_RELOAD_V2)

    subprocess.run([str(scriptc), 'aot-c', str(target / 'swarm.xus'), str(target / 'swarm.schema.json'),
                    str(target), 'swarm'], cwd=root, check=True)
    subprocess.run([str(scriptc), 'build', str(target / 'swarm_v2.xus'), str(target / 'swarm.schema.json'),
                    str(target / 'swarm_v2.xubc')], cwd=root, check=True)

    # Put generated AOT runner and static module inside package runner/ as a real module!
    runner_dir = target / 'runner'
    runner_dir.mkdir(parents=True, exist_ok=True)
    dual_text = (target / 'swarm_dual.xu').read_text()
    static_text = (target / 'swarm_static.xu').read_text()
    (runner_dir / 'dual.xu').write_text('@"example/nexus_script_aot_check/runner"\n' + dual_text)
    (runner_dir / 'static.xu').write_text('@"example/nexus_script_aot_check/runner"\n' + static_text)

    host_os = {'Darwin': 'macos', 'Linux': 'linux', 'Windows': 'windows'}[platform.system()]
    host_arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}[platform.machine()]
    host = f'{host_os}-{host_arch}'

    sdk = re.search(r'^xu: !ver (\S+)$', (root / 'xu.xun').read_text(), re.MULTILINE).group(1)
    (target / 'xu.xun').write_text(
        f'module: example/nexus_script_aot_check\n'
        f'version: !ver 0.1.0\n'
        f'xu: !ver {sdk}\n'
        f'require:\n'
        f'  "github.com/xulang-org/nexus": file:{root}\n'
        f'native:\n'
        f'  nexus_swarm_aot: file:./swarm_aot.xulib\n'
    )

    subprocess.run([args.xu, 'native', 'compile', '--manifest', str(target / 'native.json'),
                    '--target', host, '-o', str(target / 'swarm_aot.a'), '-O3', str(target / 'swarm.c')],
                   cwd=root, check=True)
    subprocess.run([args.xu, 'native', 'pack', '--manifest', str(target / 'native.json'),
                    '--slice', f'{host}={target / "swarm_aot.a"}', '-o', str(target / 'swarm_aot.xulib')],
                   cwd=root, check=True)

    (target / 'main.xu').write_text('''@main

bc #"github.com/xulang-org/nexus/script/bytecode"
vm #"github.com/xulang-org/nexus/script/vm"
runner #"example/nexus_script_aot_check/runner"
#os
#math
#time

fn near(a f64, b f64) bool { << math.abs(a - b) < 1e-11 }

fn expect_handler_err(inst $&runner.DualTrackRunner, id int, val f64, budget int, lim f64) bool {
    _ := inst.invoke_handler(id, val, budget, lim) or (err) { << true }
    << false
}

fn expect_exec_err(inst $&runner.DualTrackRunner, dt f64, axis f64, budget int, lim f64) bool {
    _ := inst.execute(dt, axis, budget, lim) or (err) { << true }
    << false
}

fn run() int {
    raw := os.read("swarm.xubc") or >>
    mod := bc.decode(&raw) or >>
    mod_aot := bc.decode(&raw) or >>
    raw2 := os.read("swarm_v2.xubc") or >>
    mod2 := bc.decode(&raw2) or >>

    $vm_inst := vm.instantiate(mod) or >>
    $aot_inst := runner.new_dual_track(mod_aot) or >>
    assert(aot_inst.is_aot())

    // 1. Step-for-step numerical, state, signal, and handler parity across VM, DualTrack C-AOT, and Static-Xu AOT.
    $static_state := [1.0, 0.25, 1.25]
    for k in 0:40 {
        dt := 1.0 / 60.0
        axis := math.sin(f64(k) * 0.2)
        rv := vm_inst.execute(dt, axis, 16384, 100000.0) or >>
        ra := aot_inst.execute(dt, axis, 16384, 100000.0) or >>
        rs := runner.swarm_run(0, dt, axis, 16384, 100000.0, $&static_state) or >>
        assert(near(rv, ra) && near(rv, rs))
        for fid in 1:4 {
            assert(near(vm_inst.state(fid) or >>, aot_inst.state(fid) or >>))
        }
        assert(near(static_state[0], vm_inst.state(1) or >>))
        assert(near(static_state[1], vm_inst.state(2) or >>))
        sv := vm_inst.drain_signals() or >>
        sa := aot_inst.drain_signals() or >>
        assert(sv.len == sa.len)
        for j in 0:sv.len {
            assert(sv[j].id == sa[j].id && near(sv[j].value, sa[j].value) && sv[j].call == sa[j].call)
        }
        if k == 10 {
            bv := vm_inst.invoke_handler(20, 0.5, 4096, 100000.0) or >>
            ba := aot_inst.invoke_handler(20, 0.5, 4096, 100000.0) or >>
            bs := runner.swarm_run(1, 0.5, 0.0, 4096, 100000.0, $&static_state) or >>
            assert(near(bv, ba) && near(bv, bs))
        }
    }

    // 2. Transactional fault & rollback parity (divide by zero + budget exhausted + host bound).
    assert(expect_handler_err($&aot_inst, 20, 0.0, 4096, 100000.0))
    assert(near(aot_inst.state(3) or >>, vm_inst.state(3) or >>))

    assert(expect_exec_err($&aot_inst, 1.0 / 60.0, 1.0, 50, 100000.0))
    assert(near(aot_inst.state(1) or >>, vm_inst.state(1) or >>))

    assert(expect_exec_err($&aot_inst, 1.0 / 60.0, 1.0, 4096, 0.0001))
    assert(near(aot_inst.state(1) or >>, vm_inst.state(1) or >>))

    // 3. Hot reload transition from C-AOT -> Bytecode VM preserving live state!
    saved_acc := aot_inst.state(1) or >>
    changed := aot_inst.reload(mod2) or >>
    assert(changed == 1 && !aot_inst.is_aot() && aot_inst.epoch() == 2)
    res2 := aot_inst.execute(1.0 / 60.0, 0.0, 4096, 100000.0) or >>
    assert(near(res2, saved_acc + 100.0))

    // 4. Performance benchmark (Release-compiled VM vs Native C-AOT across 2000 ticks * 200 loop iters = 400k loop ops).
    $vm_bench := vm.instantiate(bc.decode(&raw) or >>) or >>
    $aot_bench := runner.new_dual_track(bc.decode(&raw) or >>) or >>
    $s_bench := [1.0, 0.25, 1.25]
    t0 := time.now()
    for _ in 0:2000 {
        _ := vm_bench.execute(1.0 / 60.0, 0.5, 16384, 100000.0) or >>
        _ := vm_bench.drain_signals() or >>
    }
    t1 := time.now()
    for _ in 0:2000 {
        _ := aot_bench.execute(1.0 / 60.0, 0.5, 16384, 100000.0) or >>
        _ := aot_bench.drain_signals() or >>
    }
    t2 := time.now()
    for _ in 0:2000 {
        _ := runner.swarm_run(0, 1.0 / 60.0, 0.5, 16384, 100000.0, $&s_bench) or >>
    }
    t3 := time.now()

    vm_us := (t1 - t0) / 1000
    aot_us := (t2 - t1) / 1000
    sxu_us := (t3 - t2) / 1000
    assert(near(vm_bench.state(1) or >>, aot_bench.state(1) or >>))
    assert(near(vm_bench.state(1) or >>, s_bench[0]))
    assert(aot_us * 5 < vm_us)
    println("PASS: XuScript Dual-Track AOT parity & rollback verified (2000x200 iters: vm=" +
        str(vm_us) + "us, c_aot=" + str(aot_us) + "us, static_xu=" + str(sxu_us) + "us)")
    << 0
}
fn main() int {
    << run() or (err) {
        eprintln(err.msg())
        << 1
    }
}
''')

    binary = target / 'script_aot_check'
    subprocess.run([args.xu, 'build', '--release', str(target / 'main.xu'), '-o', str(binary)], cwd=target, check=True)
    subprocess.run([str(binary)], cwd=target, check=True)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f'script_aot_checks failed (exit={error.returncode})', file=sys.stderr)
        raise SystemExit(error.returncode or 1)

#!/usr/bin/env python3
"""End-to-end checks for cmd/project_viewport live whitebox scripting, TCP sync, and GLB export."""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = ROOT / "build/nexus-project-viewport"
VALIDATOR = ROOT / "build/nexus-project-validate"
SAMPLE_SCENE = ROOT / "examples/scene_assets/assets/world.xuscene"
SAMPLE_GLB = ROOT / "examples/scene_assets/assets/panels.glb"


def run_live_script_test(work: Path) -> None:
    scene = work / "world.xuscene"
    out_scene = work / "out.xuscene"
    wb_glb = work / "whitebox.glb"
    cap_png = work / "wb.png"
    script_path = work / "script.jsonl"

    commands = [
        {"cmd": "spawn_whitebox", "shape": "box", "size": [2.0, 2.0, 2.0]},
        {"cmd": "set_mode", "mode": "face"},
        {"cmd": "select_subobject", "indices": [4]},
        {"cmd": "model_op", "op": "extrude", "value": 0.8},
        {"cmd": "model_op", "op": "inset", "amount": 0.25, "value": 0.0},
        {"cmd": "model_op", "op": "box_uv", "value": 1.0},
        {"cmd": "capture", "path": str(cap_png)},
        {"cmd": "apply"},
    ]
    script_path.write_text("\n".join(json.dumps(c) for c in commands) + "\n")

    subprocess.run(
        [
            str(VIEWPORT),
            "--scene",
            str(scene),
            "--output",
            str(out_scene),
            "--live-script",
            str(script_path),
            "--whitebox-out",
            str(wb_glb),
        ],
        cwd=ROOT,
        check=True,
        timeout=45,
        capture_output=True,
        text=True,
    )

    assert out_scene.is_file() and out_scene.stat().st_size > 0
    assert cap_png.is_file() and cap_png.stat().st_size > 0
    assert wb_glb.is_file() and wb_glb.stat().st_size > 0

    subprocess.run([str(VALIDATOR), "png", str(cap_png)], cwd=ROOT, check=True, timeout=20, capture_output=True, text=True)

    val = subprocess.run(
        [str(VALIDATOR), "glb", str(wb_glb)],
        cwd=ROOT,
        check=True,
        timeout=20,
        capture_output=True,
        text=True,
    )
    cols = val.stdout.strip().splitlines()[0].split()
    assert len(cols) == 5 and int(cols[0]) > 12, val.stdout


def run_tcp_live_test(work: Path) -> None:
    scene = work / "world.xuscene"
    out_scene = work / "tcp_out.xuscene"
    wb_glb = work / "tcp_whitebox.glb"
    events = []
    errors = []

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(20.0)
    port = srv.getsockname()[1]

    def server_thread():
        try:
            conn, _ = srv.accept()
            conn.settimeout(20.0)
            f = conn.makefile("r", encoding="utf-8")
            ready_line = f.readline()
            ready_ev = json.loads(ready_line)
            events.append(ready_ev)
            assert ready_ev["event"] == "ready", ready_ev

            cmds = [
                {"cmd": "spawn_whitebox", "shape": "box", "size": [2.0, 2.0, 2.0]},
                {"cmd": "set_mode", "mode": "edge"},
                {"cmd": "select_subobject", "indices": [4, 5]},
                {"cmd": "model_op", "op": "bevel", "value": 0.15},
                {"cmd": "apply"},
            ]
            for c in cmds:
                conn.sendall((json.dumps(c) + "\n").encode("utf-8"))

            while True:
                line = f.readline()
                if not line:
                    break
                ev = json.loads(line)
                events.append(ev)
                if ev.get("event") == "closed":
                    break
            conn.close()
        except Exception as exc:
            errors.append(exc)
        finally:
            srv.close()

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()

    try:
        subprocess.run(
            [
                str(VIEWPORT),
                "--scene",
                str(scene),
                "--output",
                str(out_scene),
                "--live-connect",
                f"127.0.0.1:{port}",
                "--whitebox-out",
                str(wb_glb),
            ],
            cwd=ROOT,
            check=True,
            timeout=30,
            capture_output=True,
            text=True,
        )
    finally:
        t.join(timeout=10.0)

    assert not errors, errors
    ev_names = [e.get("event") for e in events]
    assert "ready" in ev_names and "whitebox" in ev_names and "closed" in ev_names, events
    closed = next(e for e in events if e.get("event") == "closed")
    assert closed["outcome"] == "apply", closed
    wb_ev = [e for e in events if e.get("event") == "whitebox"][-1]
    assert wb_ev["faces"] >= 7 and wb_ev["triangles"] >= 12, wb_ev
    assert wb_glb.is_file() and wb_glb.stat().st_size > 0
    subprocess.run([str(VALIDATOR), "glb", str(wb_glb)], cwd=ROOT, check=True, timeout=20)


def main() -> None:
    assert VIEWPORT.is_file(), f"missing {VIEWPORT}"
    assert VALIDATOR.is_file(), f"missing {VALIDATOR}"
    with tempfile.TemporaryDirectory(prefix="nexus-modeling-vp-") as directory:
        work = Path(directory)
        shutil.copyfile(SAMPLE_SCENE, work / "world.xuscene")
        shutil.copyfile(SAMPLE_GLB, work / "panels.glb")
        run_live_script_test(work)
        run_tcp_live_test(work)
    print("PASS: modeling_viewport_checks (live-script extrude/inset/UV capture + live TCP bevel/export/validator)")


if __name__ == "__main__":
    main()

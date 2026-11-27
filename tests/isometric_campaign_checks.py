"""Edit, publish and run the two maps through the real Phone resource layout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_phone import stage_isometric_project


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-isometric-campaign-") as directory:
        work = Path(directory)
        sample = ROOT / "examples/isometric_2d"
        shutil.copytree(sample / "assets", work / "assets")
        config = json.loads((sample / "project.json").read_bytes())
        authored = work / config["scenes"]["world.xuscene"]
        editor = ROOT / "build/nexus-tilemap-editor"
        subprocess.run([str(editor), str(authored), "--check", str(work / "edited")],
                       cwd=work, timeout=35, check=True)
        edited = work / "edited/edited.xuscene"
        shutil.copyfile(edited, authored)
        gate = next(node for node in json.loads(edited.read_bytes())["nodes"] if node["name"] == "Exit_grove")
        assert abs(gate["transform"][-1] - 264) < .001, gate
        project = work / "project.json"
        project.write_text(json.dumps(config))
        stage = work / "phone"
        entries = stage_isometric_project(project, stage, "world.xuscene", ROOT / "build/nexus-project-validate")
        assert len([name for name in entries if name.startswith("map/assets/")]) == 1
        assert "map/world.xuscene" in entries and "map/grove.xuscene" in entries
        shutil.copytree(ROOT / "build/canvas-shaders", stage / "canvas")

        data = work / "data"
        data.mkdir()
        checkpoint = data / "isometric-campaign-v1.json"
        env = os.environ | {"XU_PHONE_RESOURCE_ROOT": str(stage), "XU_PHONE_DATA_ROOT": str(data)}
        game = str(ROOT / "build/isometric-2d")
        with (work / "run.log").open("w+") as log:
            process = subprocess.Popen([game, "--autoplay", "--frames", "50000"], cwd=work, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and process.poll() is None:
                    if checkpoint.exists() and json.loads(checkpoint.read_bytes())["map"] == "grove.xuscene":
                        break
                    time.sleep(.05)
                else:
                    log.seek(0)
                    raise AssertionError(log.read())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        before = json.loads(checkpoint.read_bytes())
        recovered = subprocess.run([game, "--frames", "1"], cwd=work, env=env,
                                   capture_output=True, text=True, timeout=10, check=True)
        assert "Isometric map: grove.xuscene" in recovered.stdout
        assert "Isometric map: world.xuscene" not in recovered.stdout
        assert json.loads(checkpoint.read_bytes()) == before
    print("PASS: editor exit move, shared project export, two-map transition and cold restart after process death")


if __name__ == "__main__":
    main()

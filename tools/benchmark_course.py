#!/usr/bin/env python3
"""Capture elapsed frame phases and peak process RSS on the fixed Nexus course."""

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.tmp-', delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(data)
    os.replace(tmp, path)


def published_scene(build, name):
    cli = ROOT / "build/nexus-project"
    if not cli.is_file():
        subprocess.run(["make", "project-cli"], cwd=ROOT, check=True)
    result = subprocess.run(
        [str(cli), "scene", str(name), "--output", str(build)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    return Path(result.stdout.strip())
PHASES = ("frame", "simulation", "encoding", "present")


def percentiles(values):
    values.sort()
    return {f"p{percent}": round(values[math.ceil(len(values) * percent / 100) - 1] / 1e6, 4)
            for percent in (50, 95, 99)}


def max_rss():
    if platform.system() not in {"Darwin", "Linux"}:
        return None
    import resource
    value = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return value if platform.system() == "Darwin" else value * 1024


def benchmark(build, output):
    frames, warmup = 240, 12
    output.mkdir(parents=True, exist_ok=True)
    scene = published_scene(build, "course.xuscene")
    trace = output / "frames.csv"
    capture = subprocess.run([str(ROOT / "build/nexus-character-course"), "--scene", str(scene),
                              "--autoplay", "--frames", str(frames), "--trace", str(trace)],
                             cwd=ROOT, check=True, capture_output=True, text=True)
    peak = max_rss()
    with trace.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != frames or "Course complete." not in capture.stdout:
        raise ValueError("the course did not finish with the expected frame count")
    first = rows[0]
    dimensions = int(first["width"]), int(first["height"])
    if min(dimensions) < 1 or int(first["first_frame_ns"]) <= 0:
        raise ValueError("invalid framebuffer or startup metrics")
    warmed = [row for row in rows[warmup:] if row["playing"] == "1"]
    if not warmed:
        raise ValueError("no active frames after warmup")
    if any(any(int(row[f"{phase}_ns"]) < 0 for phase in PHASES)
           or int(row["frame_ns"]) <= 0 or int(row["draws"]) <= 0 for row in warmed):
        raise ValueError("invalid timing or draw counter")
    report = {
        "scenario": "character_course",
        "generation": scene.parent.name,
        "scene_sha256": hashlib.sha256(scene.read_bytes()).hexdigest(),
        "os": platform.platform(),
        "architecture": platform.machine(),
        "backend": first["backend"],
        "resolution_px": dimensions,
        "sample_frames": len(warmed),
        "warmup_frames": warmup,
        "first_frame_ms": round(int(first["first_frame_ns"]) / 1e6, 4),
        "peak_process_rss_bytes": peak,
        "peak_scene_draw_calls": max(int(row["draws"]) for row in warmed),
        "peak_triangles": max(int(row["triangles"]) for row in warmed),
        "wall_time_ms": {phase: percentiles([int(row[f"{phase}_ns"]) for row in warmed])
                         for phase in PHASES},
    }
    data = (json.dumps(report, indent=2) + "\n").encode()
    atomic_write(output / "report.json", data)
    print(data.decode().strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    benchmark(args.project_build.resolve(), args.output.resolve())

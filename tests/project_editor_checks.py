#!/usr/bin/env python3
"""Drive the real editor widgets against a writable example scene."""

import json
from copy import deepcopy
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from project_editor import ProjectEditor, multiply
from editor_theme import TOKENS, EntryField
from project import encoded, publish, published_scene


paper = TOKENS["themes"]["light"]
viewport_source = (ROOT / "cmd/project_viewport/main.xu").read_text()
viewport_colors = {name.lower().replace("_", "-"): f"#{rgb}" for name, rgb in
                   re.findall(r"^const EDITOR_(\w+) = 0x([0-9a-f]{6})ff$", viewport_source, re.MULTILINE)}
assert viewport_colors == {key: paper[key] for key in (
    "canvas", "surface", "border", "text", "muted", "brand", "chart-1", "chart-2", "chart-3", "chart-4")}


with tempfile.TemporaryDirectory(prefix="nexus-editor-") as directory:
    project = Path(directory) / "project"
    shutil.copytree(ROOT / "examples/scene_assets/assets", project / "assets")
    shutil.copy(ROOT / "examples/scene_assets/project.json", project)
    course_example = ROOT / "examples/character_course"
    shutil.copytree(course_example / "assets", project / "course")
    config = json.loads((project / "project.json").read_bytes())
    course = json.loads((course_example / "project.json").read_bytes())
    config["assets"].update({uid: f"course/{Path(path).name}" for uid, path in course["assets"].items()})
    config["scenes"]["course.xuscene"] = "course/course.xuscene"
    (project / "project.json").write_text(json.dumps(config))
    output = project / "build"
    root = tk.Tk()
    validator = ROOT / "build/nexus-project-validate"
    preview = ROOT / "build/nexus-project-preview"
    app = ProjectEditor(root, project / "project.json", output, validator, preview)
    root.update()
    canvas = app.canvas
    assert canvas.cget("background") == paper["canvas"]
    style = ttk.Style(root)
    assert style.lookup("TFrame", "background") == paper["surface"]
    assert style.lookup("Primary.TButton", "foreground") == paper["on-brand"]
    assert style.lookup("FieldValue.TEntry", "background") == paper["surface"]
    assert app.undo_button.instate(["disabled"]) and app.redo_button.instate(["disabled"])
    assert app.save_state.get() == "Saved"
    assert app.status.get().startswith("Select a node")
    root.geometry("940x560")
    root.update()
    assert canvas.winfo_width() >= 420 and app.snap_button.winfo_viewable()
    assert app.snap_button.winfo_rootx() + app.snap_button.winfo_width() <= canvas.winfo_rootx() + canvas.winfo_width()
    assert app.stage_label.winfo_width() >= app.stage_label.winfo_reqwidth()
    assert app.apply_button.winfo_rooty() + app.apply_button.winfo_height() <= app.status_label.winfo_rooty()
    caption, outline = app.name_field.caption, app.name_field.box
    assert caption.winfo_rooty() < outline.winfo_rooty() < caption.winfo_rooty() + caption.winfo_height()
    original_name = app.name.get()
    app.name.set("节点")
    assert app.name_field.counter.cget("text") == "6 / 255 bytes"
    app.name_field.clear_button.invoke()
    assert app.name.get() == "" and app.name_field.counter.cget("text") == "0 / 255 bytes"
    app.name.set("Bad/name")
    app.apply_button.invoke()
    root.update()
    assert app.name_field.entry.instate(["invalid"]) and app.name_field.error.winfo_viewable()
    assert app.name.get() == "Bad/name" and not app.edit.dirty
    assert app.apply_button.winfo_rooty() + app.apply_button.winfo_height() <= app.status_label.winfo_rooty()
    app.name.set(original_name)
    assert app.name_field.entry.instate(["!invalid"])
    root.geometry("1240x700")
    root.update()
    app.frame_top()
    point = (canvas.winfo_width() // 2 + 40, canvas.winfo_height() // 2 + 30)
    anchored = app.world_point(*point)
    previous_scale = app.scale
    canvas.event_generate("<MouseWheel>", x=point[0], y=point[1], delta=120)
    assert app.scale > previous_scale
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(app.world_point(*point), anchored))
    canvas.event_generate("<ButtonPress-2>", x=point[0], y=point[1])
    canvas.event_generate("<B2-Motion>", x=point[0] + 35, y=point[1] + 20)
    assert math.isclose(app.world_point(point[0] + 35, point[1] + 20)[0], anchored[0], abs_tol=1e-9)
    app.frame_top()
    labels = set(canvas.find_withtag("node-label"))
    for label in labels:
        assert (set(canvas.find_overlapping(*canvas.bbox(label))) & labels) == {label}
    x0, y0 = canvas.winfo_width() // 2, canvas.winfo_height() // 2
    x, _, z = app.edit.world_positions()[2]
    px, py = app.view_point(x, z)
    canvas.event_generate("<Button-1>", x=round(px), y=round(py))
    root.update()
    assert app.index in {2, 6}, app.index
    original = app.name.get()
    app.name.set("Edited panel")
    app.position[0].set("1.25")
    app.visible.set(False)
    app.apply()
    root.update()
    assert app.edit.dirty and not app.edit.document["nodes"][app.index]["visible"]
    assert app.save_state.get() == "Unsaved changes" and not app.undo_button.instate(["disabled"])
    app.undo()
    assert app.name.get() == original and not app.edit.dirty
    app.redo()
    assert app.name.get() == "Edited panel"
    app.place_next()
    canvas.event_generate("<Button-1>", x=x0 + 100, y=y0 + 45)
    root.update()
    assert app.name.get() == "Model 1"
    assert len(app.edit.document["surfaces"]) == 9

    app.save()
    assert not app.edit.dirty
    assert app.save_state.get() == "Saved"
    saved = json.loads((project / "assets/world.xuscene").read_bytes())
    assert any(node["name"] == "Edited panel" for node in saved["nodes"])
    assert saved["nodes"][-1]["name"] == "Model 1"
    app.launch_preview()
    assert app.preview_process is not None
    try:
        assert app.preview_process.poll() is None
        published = json.loads((output / "current.json").read_bytes())
        path = output / "generations" / published["generation"] / "gallery.xuscene"
        assert json.loads(path.read_bytes())["nodes"] == saved["nodes"]
    finally:
        app.preview_process.terminate()
        app.preview_process.wait(timeout=10)

    def wait_viewport():
        deadline = time.monotonic() + 30
        while app.viewport is not None and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        if app.viewport is not None:
            app.viewport.process.terminate()
            app.viewport.process.wait(timeout=10)
            app.check_viewport()
            raise AssertionError("3D View did not close after the checked edit")

    try:
        # A world X drag under a rotated/scaled parent must change two local coordinates.
        fixture = json.loads((project / "assets/world.xuscene").read_bytes())
        angle = math.pi / 6
        c, s = math.cos(angle), math.sin(angle)
        fixture["nodes"][0]["transform"] = [2*c, 0, -2*s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]
        fixture_path = project / "assets/transformed.xuscene"
        fixture_path.write_bytes(encoded(fixture))
        capture = project / "transformed-edit.xuscene"
        binary = ROOT / "build/nexus-project-viewport"
        rejected = project / "invalid-snap.xuscene"
        for option, value in [("--snap-move", "NaN"), ("--snap-rotate", "181"), ("--snap-scale", "0")]:
            attempt = subprocess.run([str(binary), "--scene", str(fixture_path), "--output", str(rejected),
                                      option, value], cwd=ROOT, capture_output=True, text=True, timeout=10)
            assert attempt.returncode == 1 and option in attempt.stderr and not rejected.exists(), attempt.stderr
        subprocess.run([str(binary), "--scene", str(fixture_path), "--output", str(capture),
                        "--check-node", "Five_maps"], cwd=ROOT, check=True)
        selected = next(i for i, item in enumerate(fixture["nodes"]) if item["name"] == "Five_maps")
        current = json.loads(capture.read_bytes())["nodes"][selected]["transform"]
        before = fixture["nodes"][selected]["transform"]
        assert current[:12] == before[:12] and current[13] == before[13]
        assert math.isclose(current[12] - before[12], 0.1*c, abs_tol=1e-6)
        assert math.isclose(current[14] - before[14], 0.2*s, abs_tol=1e-6)

        # Exercise the full affine result through the editor's normal draft merge.
        app.edit.change(deepcopy(fixture))
        group_draft = encoded(app.edit.document)
        launcher = project / "viewport-check"
        launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(binary))
                            + ' "$@" --check-node "Five_maps" --check-also "MR_AO"\n')
        launcher.chmod(0o755)
        app.viewport_binary = launcher
        app.launch_viewport()
        wait_viewport()
        assert app.status.get().startswith("Applied transforms to 2 nodes"), app.status.get()
        original_nodes = fixture["nodes"]
        edited_nodes = app.edit.document["nodes"]
        selection = [i for i, node in enumerate(original_nodes) if node["name"] in {"Five_maps", "MR_AO"}]
        original_world = [multiply(original_nodes[0]["transform"], original_nodes[i]["transform"])
                          for i in selection]
        centroid = [(original_world[0][i] + original_world[1][i]) / 2 for i in range(12, 15)]

        def expected_vector(x, y, z):
            return [1.375 * (c*x - s*y), 1.1 * (s*x + c*y), 1.1*z]

        for i, world_before in zip(selection, original_world):
            world_after = multiply(edited_nodes[0]["transform"], edited_nodes[i]["transform"])
            for col in (0, 4, 8):
                expected = expected_vector(*world_before[col:col+3])
                assert all(math.isclose(a, b, abs_tol=1e-6)
                           for a, b in zip(world_after[col:col+3], expected))
            delta = [world_before[12+k] - centroid[k] for k in range(3)]
            expected = [base + offset for base, offset in zip(centroid, expected_vector(*delta))]
            expected[0] += 0.2
            assert all(math.isclose(a, b, abs_tol=1e-6)
                       for a, b in zip(world_after[12:15], expected)), (world_after, expected)
        assert all(edited_nodes[i] == node for i, node in enumerate(original_nodes) if i not in selection)
        group_result = encoded(app.edit.document)
        app.undo()
        assert encoded(app.edit.document) == group_draft
        app.redo()
        assert encoded(app.edit.document) == group_result
        app.save()
        publish(project / "project.json", output.resolve(), validator)
        published_gallery = json.loads(published_scene(output.resolve(), "gallery.xuscene").read_bytes())
        assert published_gallery["nodes"] == edited_nodes

        # The last selected node has a reflected, sheared local frame under the
        # rotated non-uniform parent. Compare captured matrices in world space.
        local_scene = deepcopy(fixture)
        local_nodes = local_scene["nodes"]
        active = next(i for i in selection if local_nodes[i]["name"] == "MR_AO")
        local_nodes[active]["transform"][:12] = [-1, 0, 0, 0, 0.3, 1, 0, 0, 0, 0, 1, 0]
        local_world = [multiply(local_nodes[0]["transform"], local_nodes[i]["transform"]) for i in selection]
        pivot = [(local_world[0][i] + local_world[1][i]) / 2 for i in range(12, 15)]
        axis_x = [-c, 0, s]
        axis_z = [s, 0, c]

        def dot(a, b):
            return sum(x*y for x, y in zip(a, b))

        def rotated(vector, angle):
            ax, ay, az = axis_z
            x, y, z = vector
            cross = (ay*z - az*y, az*x - ax*z, ax*y - ay*x)
            cosine, sine = math.cos(angle), math.sin(angle)
            return [cosine*v + sine*w + (1-cosine)*u*dot(axis_z, vector)
                    for v, w, u in zip(vector, cross, axis_z)]

        def check_snapped_edit(distance, degrees, axis_factor, uniform_factor):
            angle = math.radians(degrees)
            rotated_x = rotated(axis_x, angle)

            def snapped_linear(vector):
                turned = rotated(vector, angle)
                stretched = dot(turned, rotated_x) * (axis_factor - 1)
                return [uniform_factor * (value + stretched * along) for value, along in zip(turned, rotated_x)]

            app.edit.change(deepcopy(local_scene))
            snap_draft = encoded(app.edit.document)
            app.launch_viewport()
            wait_viewport()
            assert app.status.get().startswith("Applied transforms to 2 nodes"), app.status.get()
            snapped_nodes = app.edit.document["nodes"]
            for i, original_matrix in zip(selection, local_world):
                matrix = multiply(snapped_nodes[0]["transform"], snapped_nodes[i]["transform"])
                for col in (0, 4, 8):
                    expected = snapped_linear(original_matrix[col:col+3])
                    assert all(math.isclose(a, b, abs_tol=1e-6)
                               for a, b in zip(matrix[col:col+3], expected)), (matrix[col:col+3], expected)
                offsets = snapped_linear([original_matrix[12+k] - pivot[k] for k in range(3)])
                expected = [base + offset + along*distance for base, offset, along in zip(pivot, offsets, axis_x)]
                assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(matrix[12:15], expected)), (
                    matrix[12:15], expected)
            assert all(snapped_nodes[i] == node for i, node in enumerate(local_nodes) if i not in selection)
            snapped_result = encoded(app.edit.document)
            app.undo()
            assert encoded(app.edit.document) == snap_draft
            app.redo()
            assert encoded(app.edit.document) == snapped_result
            app.save()
            publish(project / "project.json", output.resolve(), validator)
            published_gallery = json.loads(published_scene(output.resolve(), "gallery.xuscene").read_bytes())
            assert published_gallery["nodes"] == snapped_nodes

        launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(binary))
                            + ' "$@" --check-node "Five_maps" --check-also "MR_AO" --check-local\n')
        check_snapped_edit(-0.25, 30, 1.3, 1.2)

        def open_snap_settings():
            app.snap_button.invoke()
            dialog = root.nametowidget("snap_settings")
            panel = dialog.winfo_children()[0]
            fields = [item for item in panel.winfo_children() if isinstance(item, EntryField)]
            buttons = {item.cget("text"): item for item in panel.winfo_children()[-1].winfo_children()}
            return dialog, fields, buttons

        def set_entry(field, value):
            field.delete(0, "end")
            field.insert(0, value)

        revision = encoded(app.edit.document)
        pointer = (output / "current.json").read_bytes()
        settings = output / "editor-snap.json"
        dialog, fields, buttons = open_snap_settings()
        assert [float(field.entry.get()) for field in fields] == [0.25, 15, 10]
        set_entry(fields[0].entry, "inf")
        set_entry(fields[2].entry, "101")
        buttons["Apply"].invoke()
        root.update()
        assert dialog.winfo_exists() and not settings.exists()
        assert fields[0].entry.instate(["invalid"]) and fields[0].error.winfo_viewable()
        assert fields[2].entry.instate(["invalid"]) and fields[2].error.winfo_viewable()
        assert fields[1].entry.instate(["!invalid"])
        assert [field.entry.get() for field in fields] == ["inf", "15.0", "101"]
        for field, value in zip(fields, ["0.5", "20", "40"]):
            set_entry(field.entry, value)
        assert all(field.entry.instate(["!invalid"]) for field in fields)
        buttons["Apply"].invoke()
        assert not dialog.winfo_exists()
        saved_steps = {"move": 0.5, "rotate": 20, "scale": 40}
        assert json.loads(settings.read_bytes()) == saved_steps
        assert encoded(app.edit.document) == revision and not app.edit.dirty
        assert (output / "current.json").read_bytes() == pointer

        dialog, fields, buttons = open_snap_settings()
        set_entry(fields[1].entry, "90")
        buttons["Cancel"].invoke()
        assert json.loads(settings.read_bytes()) == saved_steps

        reopened = tk.Toplevel(root)
        try:
            after_restart = ProjectEditor(reopened, project / "project.json", output, validator, preview)
            assert after_restart.snap_steps == saved_steps
        finally:
            reopened.destroy()
        check_snapped_edit(-0.5, 40, 1.4, 1.4)

        # A selected child is carried once by the same selected parent's transform.
        nested = deepcopy(fixture)
        first = next(i for i, node in enumerate(nested["nodes"]) if node["name"] == "Five_maps")
        child = next(i for i, node in enumerate(nested["nodes"]) if node["name"] == "MR_AO")
        sequence = [i for i in range(len(nested["nodes"])) if i != child]
        sequence.insert(sequence.index(first) + 1, child)
        index_map = {old: new for new, old in enumerate(sequence)}
        nodes = nested["nodes"]
        nodes[child]["parent"] = first
        nodes[child]["transform"][12:15] = [0.6, 1.9, 0.25]
        nested["nodes"] = [nodes[i] for i in sequence]
        for node in nested["nodes"]:
            if node["parent"] >= 0:
                node["parent"] = index_map[node["parent"]]
        for binding in nested["surfaces"]:
            binding["node"] = index_map[binding["node"]]
        nested_path = project / "assets/nested-selection.xuscene"
        nested_path.write_bytes(encoded(nested))
        capture = project / "nested-edit.xuscene"
        subprocess.run([str(binary), "--scene", str(nested_path), "--output", str(capture),
                        "--check-node", "Five_maps", "--check-also", "MR_AO"], cwd=ROOT, check=True)
        nested_result = json.loads(capture.read_bytes())["nodes"]
        assert nested_result[index_map[child]] == nested["nodes"][index_map[child]]
        assert nested_result[index_map[first]]["transform"] != nested["nodes"][index_map[first]]["transform"]

        app.scene.set("course.xuscene")
        app.open_scene()
        landing = next(i for i, node in enumerate(app.edit.document["nodes"])
                       if node["name"] == "Landing deck")
        app.select(landing)
        app.position[0].set("0.20")
        app.apply()
        ramp = next(i for i, node in enumerate(app.edit.document["nodes"])
                    if node["name"] == "Approach ramp")
        original = (project / "course/course.xuscene").read_bytes()
        draft = encoded(app.edit.document)
        launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(binary))
                            + ' "$@" --check-node "Approach ramp"\n')
        launcher.chmod(0o755)
        app.viewport_binary = launcher
        app.launch_viewport()
        wait_viewport()
        assert app.status.get().startswith("Applied transforms to 1 node"), app.status.get()
        assert app.index == ramp and app.edit.dirty
        assert (project / "course/course.xuscene").read_bytes() == original
        moved = app.edit.document["nodes"][ramp]["transform"]
        assert math.isclose(moved[12], 0.20, abs_tol=1e-6) and moved[13:15] == [0.0625, 1.675]
        app.undo()
        assert encoded(app.edit.document) == draft
        app.redo()
        assert app.edit.document["nodes"][ramp]["transform"] == moved

        # Concurrent authoring in the parent keeps its draft rather than accepting an old capture.
        app.launch_viewport()
        app.select(landing)
        app.position[0].set("0.25")
        app.apply()
        latest = encoded(app.edit.document)
        wait_viewport()
        assert "scene changed" in app.status.get(), app.status.get()
        assert encoded(app.edit.document) == latest
        app.save()
        publish(project / "project.json", output.resolve(), validator)
        level = published_scene(output.resolve(), "course.xuscene")
        restored = json.loads(level.read_bytes())
        assert restored["nodes"][landing]["transform"][12] == 0.25
        assert restored["nodes"][ramp]["transform"] == moved
        result = subprocess.run([str(ROOT / "build/nexus-character-course"), "--scene", str(level),
                                 "--frames", "240", "--autoplay"], cwd=ROOT, check=True,
                                capture_output=True, text=True)
        assert "Course complete." in result.stdout
        assert "steps=2, jumps=1, pose_mask=7" in result.stdout
        slope = re.search(r"slope_ticks=(\d+)", result.stdout)
        assert slope and int(slope[1]) >= 8, result.stdout
    finally:
        root.destroy()

print("PASS: editor workspace at minimum width, top-view navigation, saved snap steps, group transforms, undo/redo and a playable edited course")

#!/usr/bin/env python3
"""Edit authored Nexus project scenes and preview the published generation."""

import argparse
from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk

from editor_theme import PAPER, EntryField, install_theme, pixels
from project import atomic_write, encoded, project_config, publish, read_json, run_validator, source_path


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
SNAP_FIELDS = (
    ("move", "Translation step", 0.25, 0.0001, 1_000_000.0, "units"),
    ("rotate", "Rotation step", 15.0, 0.01, 180.0, "°"),
    ("scale", "Scale step", 10.0, 0.01, 100.0, "%"),
)


def default_snap_steps():
    return {key: default for key, _, default, _, _, _ in SNAP_FIELDS}


def parse_snap_step(value, minimum, maximum):
    try:
        step = float(str(value))
    except (ValueError, OverflowError):
        step = math.nan
    if not minimum <= step <= maximum:
        raise ValueError(f"Enter a number from {minimum:,.15g} to {maximum:,.15g}.")
    return step


def parse_snap_steps(values):
    if not isinstance(values, dict) or values.keys() != default_snap_steps().keys():
        raise ValueError("Snap settings require move, rotate and scale steps.")
    steps = {}
    for key, label, _, minimum, maximum, _ in SNAP_FIELDS:
        try:
            steps[key] = parse_snap_step(values[key], minimum, maximum)
        except ValueError as error:
            raise ValueError(f"{label}. {error}") from error
    return steps


def multiply(parent, local):
    return [sum(parent[k * 4 + row] * local[column * 4 + k] for k in range(4))
            for column in range(4) for row in range(4)]


class InvalidNodeName(ValueError):
    pass


class SceneEdit:
    def __init__(self, source):
        self.source = source
        self.document = read_json(source)
        self.saved = encoded(self.document)
        self.undo_stack = []
        self.redo_stack = []

    @property
    def dirty(self):
        return encoded(self.document) != self.saved

    def change(self, document):
        if document == self.document:
            return
        self.undo_stack.append(self.document)
        self.undo_stack = self.undo_stack[-32:]
        self.document = document
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.document)
            self.document = self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.document)
            self.document = self.redo_stack.pop()

    def set_properties(self, index, name, visible, position):
        draft = deepcopy(self.document)
        node = draft["nodes"][index]
        if not name:
            raise InvalidNodeName("Enter a node name.")
        if len(name.encode()) > 255:
            raise InvalidNodeName("Name exceeds 255 bytes.")
        if name in {".", ".."}:
            raise InvalidNodeName("Use a name other than '.' or '..'.")
        if "/" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise InvalidNodeName("Remove slashes and control characters.")
        if any(i != index and sibling["parent"] == node["parent"] and sibling["name"] == name
               for i, sibling in enumerate(draft["nodes"])):
            raise InvalidNodeName("A sibling already uses this name.")
        if node["type"] == "Node3D":
            coordinates = [float(item) for item in position]
            if not all(math.isfinite(value) and abs(value) <= 1e9 for value in coordinates):
                raise ValueError("position is outside the editor range")
            node["transform"][12:15] = coordinates
        node.update(name=name, visible=visible)
        self.change(draft)

    def place(self, uid, position):
        draft = deepcopy(self.document)
        nodes = draft["nodes"]
        index = len(nodes)
        if index >= 4096:
            raise ValueError("scene node limit reached")
        names = {item["name"] for item in nodes if item["parent"] == 0}
        number = 1
        while f"Model {number}" in names:
            number += 1
        transform = list(IDENTITY)
        transform[12:15] = position
        nodes.append(dict(parent=0, name=f"Model {number}", visible=True, process="inherit",
                          type="Node3D", transform=transform))
        if not any(item["uid"] == uid for item in draft["resources"]):
            draft["resources"].append(dict(uid=uid, type="glb_model", path=f"assets/{uid}.glb",
                                           sha256="0" * 64))
        draft["surfaces"].append(dict(node=index, resource=uid, primitive=0))
        self.change(draft)
        return index

    def place_on_ground(self, uid, x, z):
        root = self.document["nodes"][0]
        matrix = root["transform"] if root["type"] == "Node3D" else IDENTITY
        a, b, c, d = matrix[0], matrix[8], matrix[2], matrix[10]
        determinant = a * d - b * c
        if not math.isfinite(determinant) or abs(determinant) < 1e-12:
            raise ValueError("the root's XZ plane cannot be picked from this view")
        x -= matrix[12]
        z -= matrix[14]
        position = [(d * x - b * z) / determinant, 0, (a * z - c * x) / determinant]
        if not all(math.isfinite(value) and abs(value) <= 1e9 for value in position):
            raise ValueError("position is outside the editor range")
        return self.place(uid, position)

    def world_positions(self):
        transforms = []
        for node in self.document["nodes"]:
            parent = IDENTITY if node["parent"] < 0 else transforms[node["parent"]]
            local = node["transform"] if node["type"] == "Node3D" else IDENTITY
            transforms.append(multiply(parent, local))
        return {i: transform[12:15] for i, transform in enumerate(transforms)
                if self.document["nodes"][i]["type"] == "Node3D"}

    def apply_viewport(self, captured, revision):
        if encoded(self.document) != revision:
            raise ValueError("the scene changed while 3D View was open")
        draft = deepcopy(self.document)
        original = draft["nodes"]
        moved = captured.get("nodes") if isinstance(captured, dict) else None
        if not isinstance(moved, list) or len(moved) != len(original):
            raise ValueError("3D View result does not match the draft scene")
        changed = []
        for index, (node, result) in enumerate(zip(original, moved)):
            if (not isinstance(result, dict)
                    or any(result.get(key) != node[key] for key in ("type", "name", "parent"))):
                raise ValueError("3D View returned different node topology")
            if node["type"] != "Node3D":
                continue
            transform = result.get("transform")
            basis = node["transform"]
            if (not isinstance(transform, list) or len(transform) != 16
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in transform)
                    or [transform[i] for i in (3, 7, 11, 15)] != [0, 0, 0, 1]):
                raise ValueError("3D View returned an invalid affine transform")
            if any(abs(value) > 1e9 for value in transform[12:15]):
                raise ValueError("3D View position is outside the editor range")
            if transform != basis:
                node["transform"] = transform
                changed.append(index)
        self.change(draft)
        return changed

    def save(self, validator):
        data = encoded(self.document)
        if data == self.saved:
            return
        if encoded(read_json(self.source)) != self.saved:
            raise ValueError("the scene changed on disk; reopen it before saving")
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / self.source.name
            candidate.write_bytes(data)
            run_validator(validator, "scene", candidate)
        atomic_write(self.source, data, mode=self.source.stat().st_mode & 0o777)
        self.saved = data


@dataclass
class ViewportSession:
    directory: tempfile.TemporaryDirectory
    process: subprocess.Popen
    scene: str
    revision: bytes
    result: Path


class ProjectEditor:
    def __init__(self, root, project, output, validator, preview, viewport=ROOT / "build/nexus-project-viewport"):
        if tk.TkVersion < 8.6:
            raise ValueError("the editor requires Tk 8.6 or newer")
        self.root = root
        self.project = project.resolve(strict=True)
        self.output = output.resolve()
        self.validator = validator.resolve(strict=True)
        self.preview = preview.resolve(strict=True)
        self.viewport_binary = viewport.resolve()
        self.viewport = None
        self.snap_path = self.output / "editor-snap.json"
        self.snap_steps = default_snap_steps()
        self.config = project_config(self.project)
        self.edits = {}
        self.index = 0
        self.tree_scene = None
        self.placing = False
        self.preview_process = None
        self.center_x = self.center_z = 0.0
        self.scale = 40.0
        self.frame_on_draw = True
        self.pan_start = (0, 0)
        self.scene = tk.StringVar(root, value=next(iter(self.config["scenes"])))
        self.asset = tk.StringVar(root)
        self.status = tk.StringVar(root)
        self.save_state = tk.StringVar(root)
        self.name = tk.StringVar(root)
        self.kind = tk.StringVar(root)
        self.visible = tk.BooleanVar(root)
        self.position = [tk.StringVar(root) for _ in range(3)]
        self.small_font, self.mono_font = install_theme(root)
        root.title("Nexus Scene Editor")
        root.geometry("1240x700")
        root.minsize(940, 560)
        root.configure(background=PAPER["border"])
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        self.build_toolbar()
        self.build_workspace()
        footer = ttk.Frame(root, padding=(16, 8))
        footer.grid(row=2, column=0, sticky="ew", pady=(1, 0))
        footer.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(footer, textvariable=self.status)
        self.status_label.grid(row=0, column=0, sticky="ew")
        self.status_label.bind("<Configure>", lambda event: self.status_label.configure(wraplength=event.width))
        self.save_label = ttk.Label(footer, textvariable=self.save_state)
        self.save_label.grid(row=0, column=1, sticky="e", padx=(16, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        modifier = "Command" if root.tk.call("tk", "windowingsystem") == "aqua" else "Control"
        root.bind(f"<{modifier}-s>", lambda _: self.action(self.save))
        root.bind("<Escape>", self.cancel_placement)
        self.open_scene()
        try:
            if self.snap_path.exists():
                self.snap_steps = parse_snap_steps(read_json(self.snap_path, limit=1024))
        except (ValueError, OSError) as error:
            self.report(f"Using default snap steps. {error}", "Warning")

    def build_toolbar(self):
        toolbar = ttk.Frame(self.root, padding=(16, 12))
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 1))
        toolbar.columnconfigure(4, weight=1)
        ttk.Label(toolbar, text="Nexus", style="Brand.TLabel").grid(row=0, column=0, padx=(0, 24))
        ttk.Label(toolbar, text="Scene", style="Field.TLabel").grid(row=0, column=1, padx=(0, 8))
        scenes = ttk.Combobox(toolbar, textvariable=self.scene, values=list(self.config["scenes"]),
                              state="readonly", width=19)
        scenes.grid(row=0, column=2, sticky="ew")
        scenes.bind("<<ComboboxSelected>>", lambda _: self.action(self.open_scene))
        ttk.Separator(toolbar, orient="vertical").grid(row=0, column=3, sticky="ns", padx=(16, 8), pady=6)
        history = ttk.Frame(toolbar)
        history.grid(row=0, column=4, sticky="w")
        self.undo_button = ttk.Button(history, text="Undo", style="Quiet.TButton",
                                      command=lambda: self.action(self.undo))
        self.redo_button = ttk.Button(history, text="Redo", style="Quiet.TButton",
                                      command=lambda: self.action(self.redo))
        self.undo_button.pack(side="left", padx=(0, 4))
        self.redo_button.pack(side="left")
        ttk.Button(toolbar, text="Save Scene", style="Primary.TButton", command=lambda: self.action(self.save)).grid(
            row=0, column=5, padx=(16, 8))
        ttk.Button(toolbar, text="Preview", command=lambda: self.action(self.launch_preview)).grid(row=0, column=6)

    def build_workspace(self):
        panes = tk.PanedWindow(self.root, orient="horizontal", background=PAPER["border"],
                               sashwidth=5, sashrelief="flat", borderwidth=0, opaqueresize=True)
        panes.grid(row=1, column=0, sticky="nsew")
        scene_panel = ttk.Frame(panes, padding=pixels("space-4"))
        stage = ttk.Frame(panes)
        inspector = ttk.Frame(panes, padding=pixels("space-4"))
        panes.add(scene_panel, width=220, minsize=184, stretch="never")
        panes.add(stage, minsize=420, stretch="always")
        panes.add(inspector, width=264, minsize=228, stretch="never")
        self.build_scene_panel(scene_panel)
        self.build_stage(stage)
        self.build_inspector(inspector)

    def build_scene_panel(self, panel):
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="Scene Tree", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        tree_area = ttk.Frame(panel)
        tree_area.grid(row=1, column=0, sticky="nsew")
        tree_area.rowconfigure(0, weight=1)
        tree_area.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_area, show="tree", selectmode="browse", height=4)
        self.tree.column("#0", minwidth=0, width=140)
        scroll = ttk.Scrollbar(tree_area, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.tag_configure("hidden", foreground=PAPER["muted"])
        self.tree.bind("<<TreeviewSelect>>", self.select_tree)
        ttk.Separator(panel).grid(row=2, column=0, sticky="ew", pady=(12, 16))
        ttk.Label(panel, text="Assets", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 12))
        self.asset_ids = {path: uid for uid, path in self.config["assets"].items()}
        ttk.Combobox(panel, textvariable=self.asset, values=list(self.asset_ids), width=12,
                     state="readonly" if self.asset_ids else "disabled").grid(row=4, column=0, sticky="ew")
        if self.asset_ids:
            self.asset.set(next(iter(self.asset_ids)))
        else:
            self.asset.set("No registered GLB")
        ttk.Button(panel, text="Place GLB", command=self.place_next,
                   state="normal" if self.asset_ids else "disabled").grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def build_stage(self, stage):
        stage.columnconfigure(0, weight=1)
        stage.rowconfigure(1, weight=1)
        tools = ttk.Frame(stage, padding=(12, 8))
        tools.grid(row=0, column=0, sticky="ew")
        tools.columnconfigure(0, weight=1)
        self.stage_label = ttk.Label(tools, text="Top View · XZ", style="Panel.TLabel")
        self.stage_label.grid(row=0, column=0, sticky="w")
        ttk.Button(tools, text="Fit", style="Quiet.TButton", command=self.frame_top).grid(row=0, column=1)
        ttk.Button(tools, text="3D View", command=lambda: self.action(self.launch_viewport)).grid(
            row=0, column=2, padx=8)
        self.snap_button = ttk.Button(tools, text="Snap Settings", style="Quiet.TButton",
                                      command=lambda: self.action(self.configure_snapping))
        self.snap_button.grid(row=0, column=3)
        self.canvas = tk.Canvas(stage, background=PAPER["canvas"], highlightthickness=1,
                                highlightbackground=PAPER["border"], highlightcolor=PAPER["focus"], takefocus=True)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self.draw)
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<Key-f>", lambda _: self.frame_top())
        self.canvas.bind("<MouseWheel>", self.zoom_top)
        self.canvas.bind("<Button-4>", self.zoom_top)
        self.canvas.bind("<Button-5>", self.zoom_top)
        for button in (2, 3):
            self.canvas.bind(f"<ButtonPress-{button}>", self.start_pan)
            self.canvas.bind(f"<B{button}-Motion>", self.pan_top)
        ttk.Label(stage, padding=(12, 8), style="Muted.TLabel",
                  text="Scroll zooms  ·  Right-drag pans  ·  F fits all").grid(row=2, column=0, sticky="ew")

    def build_inspector(self, inspector):
        inspector.columnconfigure(1, weight=1)
        header = ttk.Frame(inspector)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, text="Inspector", style="Panel.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.kind, style="Muted.TLabel").pack(side="right")
        ttk.Separator(inspector).grid(row=1, column=0, columnspan=2, sticky="ew", pady=12)
        self.name_field = EntryField(inspector, "Name *", self.name, width=12, max_bytes=255)
        self.name_field.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Checkbutton(inspector, text="Visible in scene", variable=self.visible).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(inspector, text="Local position", style="Field.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.coordinates = []
        for row, (axis, value) in enumerate(zip("XYZ", self.position), 5):
            ttk.Label(inspector, text=axis, style="Muted.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8))
            field = ttk.Entry(inspector, textvariable=value, width=8, style="Coordinate.TEntry")
            field.grid(row=row, column=1, sticky="ew", pady=4)
            self.coordinates.append(field)
        self.apply_button = ttk.Button(inspector, text="Apply Changes", command=lambda: self.action(self.apply))
        self.apply_button.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    @property
    def edit(self):
        return self.edits[self.scene.get()]

    def action(self, command):
        try:
            command()
        except (OSError, ValueError) as error:
            self.report(str(error), "Error")

    def report(self, message, tone="Normal"):
        self.status.set(message)
        self.status_label.configure(style="TLabel" if tone == "Normal" else f"{tone}.TLabel")

    def open_scene(self):
        name = self.scene.get()
        if name not in self.edits:
            source = source_path(self.project.parent, self.config["scenes"][name])
            run_validator(self.validator, "scene", source)
            self.edits[name] = SceneEdit(source)
        self.index = 0
        self.cancel_placement()
        self.frame_on_draw = True
        self.refresh()
        self.report("Select a node in the scene tree or the top view.")

    def refresh(self):
        self.index = min(self.index, len(self.edit.document["nodes"]) - 1)
        expansion = {}
        if self.tree_scene == self.scene.get():
            expansion = {str(i): self.tree.item(str(i), "open") for i in range(len(self.edit.document["nodes"]))
                         if self.tree.exists(str(i))}
        self.tree.delete(*self.tree.get_children())
        for index, node in enumerate(self.edit.document["nodes"]):
            parent = "" if node["parent"] < 0 else str(node["parent"])
            self.tree.insert(parent, "end", iid=str(index), text=node["name"],
                             open=expansion.get(str(index), True), tags=() if node["visible"] else ("hidden",))
        self.tree_scene = self.scene.get()
        self.select(self.index)
        dirty = self.edit.dirty
        self.root.title(f"Nexus Scene Editor — {self.scene.get()}{' *' if dirty else ''}")
        self.save_state.set("Unsaved changes" if dirty else "Saved")
        self.save_label.configure(style="Warning.TLabel" if dirty else "Success.TLabel")
        self.undo_button.state(["!disabled" if self.edit.undo_stack else "disabled"])
        self.redo_button.state(["!disabled" if self.edit.redo_stack else "disabled"])

    def select_tree(self, _):
        selection = self.tree.selection()
        if selection and int(selection[0]) != self.index:
            self.select(int(selection[0]))

    def select(self, index):
        self.index = index
        if str(index) not in self.tree.selection():
            self.tree.selection_set(str(index))
            self.tree.focus(str(index))
            self.tree.see(str(index))
        node = self.edit.document["nodes"][index]
        self.name.set(node["name"])
        self.kind.set({"Node3D": "3D node", "Node2D": "2D node"}.get(node["type"], "Node"))
        self.visible.set(node["visible"])
        spatial = node["type"] == "Node3D"
        values = node["transform"][12:15] if spatial else ("", "", "")
        for field, value, variable in zip(self.coordinates, values, self.position):
            field.configure(state="normal" if spatial else "disabled")
            variable.set(value)
        self.draw()

    def view_point(self, x, z):
        return (self.canvas.winfo_width() / 2 + (x - self.center_x) * self.scale,
                self.canvas.winfo_height() / 2 + (z - self.center_z) * self.scale)

    def world_point(self, x, y):
        return (self.center_x + (x - self.canvas.winfo_width() / 2) / self.scale,
                self.center_z + (y - self.canvas.winfo_height() / 2) / self.scale)

    def frame_top(self):
        self.frame_on_draw = True
        self.draw()

    def zoom_top(self, event):
        if event.num in (4, 5):
            direction = 1 if event.num == 4 else -1
        elif event.delta == 0:
            return "break"
        else:
            direction = 1 if event.delta > 0 else -1
        x, z = self.world_point(event.x, event.y)
        self.scale = min(600.0, max(1e-7, self.scale * 1.15 ** direction))
        next_x, next_z = self.world_point(event.x, event.y)
        self.center_x += x - next_x
        self.center_z += z - next_z
        self.draw()
        return "break"

    def start_pan(self, event):
        self.canvas.focus_set()
        self.pan_start = event.x, event.y

    def pan_top(self, event):
        x, y = self.pan_start
        self.center_x -= (event.x - x) / self.scale
        self.center_z -= (event.y - y) / self.scale
        self.pan_start = event.x, event.y
        self.draw()

    def draw(self, _=None):
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 80 or height < 80:
            return
        nodes = self.edit.document["nodes"]
        groups = {node["parent"] for node in nodes}
        mesh_nodes = {surface["node"] for surface in self.edit.document["surfaces"]}
        points = {i: (x, z) for i, (x, _, z) in self.edit.world_positions().items()
                  if i and (i in mesh_nodes or i not in groups or i == self.index)
                  and math.isfinite(x) and math.isfinite(z)}
        if self.frame_on_draw:
            self.frame_on_draw = False
            self.center_x = self.center_z = 0.0
            self.scale = 40.0
            if points:
                xs, zs = zip(*points.values())
                low_x, high_x, low_z, high_z = min(xs), max(xs), min(zs), max(zs)
                self.center_x = low_x / 2 + high_x / 2
                self.center_z = low_z / 2 + high_z / 2
                fit_x = max(1, width - 176) / max(1, high_x - low_x)
                fit_z = max(1, height - 96) / max(1, high_z - low_z)
                self.scale = max(1e-7, min(80.0, fit_x, fit_z))

        origin_x, origin_y = self.view_point(0, 0)
        step = 10.0 ** math.floor(math.log10(56 / self.scale))
        if step * self.scale < 20:
            step *= 5
        spacing = step * self.scale
        phase_x = (width / 2 - (self.center_x % step) * self.scale) % spacing
        phase_y = (height / 2 - (self.center_z % step) * self.scale) % spacing
        for i in range(math.ceil(width / spacing)):
            x = phase_x + i * spacing
            canvas.create_line(x, 0, x, height, fill=PAPER["subtle"])
        for i in range(math.ceil(height / spacing)):
            y = phase_y + i * spacing
            canvas.create_line(0, y, width, y, fill=PAPER["subtle"])
        if 0 <= origin_x <= width:
            canvas.create_line(origin_x, 0, origin_x, height, fill=PAPER["border"])
        if 0 <= origin_y <= height:
            canvas.create_line(0, origin_y, width, origin_y, fill=PAPER["border"])
        unit = "unit" if step == 1.0 else "units"
        scale_text = f"{step:g} {unit} / grid"
        canvas.create_text(width - 14, height - 14, anchor="se", text=scale_text,
                           fill=PAPER["muted"], font=self.mono_font, tags=("node-label",))
        canvas.create_text(14, height - 14, anchor="sw", text="X →   Z ↓", fill=PAPER["muted"],
                           font=self.mono_font, tags=("node-label",))
        labels = []
        for index, (x, z) in sorted(points.items(), key=lambda item: item[0] == self.index):
            px, py = self.view_point(x, z)
            if not (1 < px < width - 1 and 1 < py < height - 1):
                continue
            selected = index == self.index
            color = PAPER["brand"] if selected else PAPER["text"] if index in mesh_nodes else PAPER["info"]
            size = 5 if selected else 3
            fill = color if nodes[index]["visible"] else PAPER["canvas"]
            tag = f"node:{index}"
            if selected:
                canvas.create_oval(px-9, py-9, px+9, py+9, outline=color, tags=(tag, "marker"))
            canvas.create_oval(px-size, py-size, px+size, py+size, fill=fill, outline=color, tags=(tag, "marker"))
            labels.append((px, py, index, color if selected else PAPER["muted"]))
        for px, py, index, color in reversed(labels):
            label = canvas.create_text(px, py, anchor="w", text=nodes[index]["name"], fill=color,
                                       font=self.small_font, tags=(f"node:{index}", "node-label"))
            for dx, dy, anchor in [(12, 0, "w"), (-12, 0, "e"), (12, -16, "w"), (12, 16, "w")]:
                canvas.coords(label, px + dx, py + dy)
                canvas.itemconfigure(label, anchor=anchor)
                x1, y1, x2, y2 = canvas.bbox(label)
                if x1 < 8 or x2 > width - 8 or y1 < 8 or y2 > height - 8:
                    continue
                if not any(other != label and ("marker" in canvas.gettags(other)
                                               or "node-label" in canvas.gettags(other))
                           for other in canvas.find_overlapping(x1-2, y1-2, x2+2, y2+2)):
                    break
            else:
                canvas.delete(label)

    def click(self, event):
        self.canvas.focus_set()

        def on_click():
            if self.placing:
                x, z = self.world_point(event.x, event.y)
                self.index = self.edit.place_on_ground(self.asset_ids[self.asset.get()], round(x, 2), round(z, 2))
                self.cancel_placement()
                self.refresh()
                self.report("Model placed. Save Scene writes it to disk.", "Success")
                return
            for target in reversed(self.canvas.find_overlapping(event.x-3, event.y-3, event.x+3, event.y+3)):
                for tag in self.canvas.gettags(target):
                    if tag.startswith("node:"):
                        self.select(int(tag[5:]))
                        return

        self.action(on_click)

    def place_next(self):
        if self.asset.get() not in self.asset_ids:
            self.report("Register a GLB before placing it.", "Warning")
            return
        self.placing = True
        self.canvas.configure(cursor="crosshair")
        self.canvas.focus_set()
        self.report("Click the top view to place the asset. Esc cancels.")

    def cancel_placement(self, event=None):
        if self.placing:
            self.placing = False
            self.canvas.configure(cursor="")
            if event is not None:
                self.report("Asset placement canceled.")
                return "break"

    def apply(self):
        try:
            self.edit.set_properties(self.index, self.name.get(), self.visible.get(),
                                     [item.get() for item in self.position])
        except InvalidNodeName as error:
            self.name_field.set_error(str(error))
            self.name_field.entry.focus_set()
            return
        self.refresh()
        self.report(f"Applied changes to {self.name.get()}.", "Success")

    def undo(self):
        self.edit.undo()
        self.refresh()
        self.report("Undid scene edit.")

    def redo(self):
        self.edit.redo()
        self.refresh()
        self.report("Redid scene edit.")

    def save(self):
        self.edit.save(self.validator)
        self.refresh()
        self.report(f"Saved {self.scene.get()}.", "Success")

    def configure_snapping(self):
        dialog = tk.Toplevel(self.root, name="snap_settings", background=PAPER["border"])
        dialog.title("3D Snap Settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.withdraw()
        panel = ttk.Frame(dialog, padding=24)
        panel.grid(sticky="nsew", padx=1, pady=1)
        panel.columnconfigure(0, weight=1)
        fields = {}
        for row, (key, label, _, _, _, unit) in enumerate(SNAP_FIELDS):
            value = tk.StringVar(dialog, value=str(self.snap_steps[key]))
            field = EntryField(panel, f"{label} *", value, width=26, unit=unit)
            field.grid(row=row, column=0, sticky="ew", pady=(0, pixels("space-5")))
            fields[key] = field
        feedback = tk.StringVar(dialog)
        form_error = ttk.Label(panel, textvariable=feedback, style="Error.TLabel", wraplength=300)
        form_error.grid(row=len(fields), column=0, sticky="ew", pady=(0, 8))
        form_error.grid_remove()
        buttons = ttk.Frame(panel)
        buttons.grid(row=len(fields) + 1, column=0, sticky="e")
        previous_focus = self.root.focus_get()

        def close_dialog():
            dialog.destroy()
            (previous_focus or self.snap_button).focus_set()

        def apply_steps():
            form_error.grid_remove()
            steps = {}
            invalid = []
            for key, _, _, minimum, maximum, _ in SNAP_FIELDS:
                field = fields[key]
                try:
                    steps[key] = parse_snap_step(field.variable.get(), minimum, maximum)
                    field.set_error("")
                except ValueError as error:
                    field.set_error(str(error))
                    invalid.append(field)
            if invalid:
                invalid[0].entry.focus_set()
                return
            try:
                atomic_write(self.snap_path, encoded(steps))
            except (OSError, ValueError) as error:
                feedback.set(str(error))
                form_error.grid()
                return
            self.snap_steps = steps
            self.report("Snap steps saved for the next 3D View.", "Success")
            close_dialog()

        ttk.Button(buttons, text="Apply", command=apply_steps, style="Primary.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=close_dialog).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Escape>", lambda _: close_dialog())
        dialog.bind("<Return>", lambda _: apply_steps())
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.deiconify()
        dialog.wait_visibility()
        dialog.grab_set()
        fields["move"].entry.focus_set()
        fields["move"].entry.selection_range(0, "end")

    def launch_viewport(self):
        if self.viewport is not None:
            self.report("3D View is already open.")
            return
        name = self.scene.get()
        revision = encoded(self.edit.document)
        scratch = tempfile.TemporaryDirectory(prefix="nexus-viewport-")
        try:
            base = Path(scratch.name)
            output = base / "draft"
            publication, _ = publish(self.project, output, self.validator,
                                     scene_drafts={name: self.edit.document})
            path = output / "generations" / publication["generation"] / name
            result = base / "edited.xuscene"
            args = [str(self.viewport_binary), "--scene", str(path), "--output", str(result)]
            for key, step in self.snap_steps.items():
                args.extend((f"--snap-{key}", str(step)))
            process = subprocess.Popen(args, cwd=ROOT)
        except (ValueError, OSError):
            scratch.cleanup()
            raise
        self.viewport = ViewportSession(scratch, process, name, revision, result)
        self.report("3D View is open. Enter applies its edits. Esc cancels.")
        self.root.after(150, self.check_viewport)

    def check_viewport(self):
        session = self.viewport
        if session is None:
            return
        code = session.process.poll()
        if code is None:
            self.root.after(150, self.check_viewport)
            return
        self.viewport = None
        try:
            if code != 0:
                self.report("3D View failed. See the terminal for details.", "Error")
            elif session.result.exists():
                changed = self.edits[session.scene].apply_viewport(read_json(session.result), session.revision)
                if changed and self.scene.get() == session.scene:
                    self.index = changed[-1]
                    self.refresh()
                nodes = "node" if len(changed) == 1 else "nodes"
                self.report(f"Applied transforms to {len(changed)} {nodes} in {session.scene}.", "Success")
            else:
                self.report("3D View closed without applying edits.")
        except (ValueError, OSError) as error:
            self.report(str(error), "Error")
        finally:
            session.directory.cleanup()

    def launch_preview(self):
        if any(edit.dirty for edit in self.edits.values()):
            self.report("Save modified scenes before publishing the preview.", "Warning")
            return
        if self.preview_process is not None and self.preview_process.poll() is None:
            self.report("Close the running preview before launching another.")
            return
        publication, _ = publish(self.project, self.output, self.validator)
        scene = self.output / "generations" / publication["generation"] / self.scene.get()
        self.preview_process = subprocess.Popen([str(self.preview), "--scene", str(scene)], cwd=ROOT)
        self.report(f"Previewing {self.scene.get()}")
        self.root.after(500, self.check_preview)

    def check_preview(self):
        code = self.preview_process.poll()
        if code is None:
            self.root.after(500, self.check_preview)
        elif code:
            self.report("Preview failed. See the terminal for the renderer error.", "Error")

    def close(self):
        if self.viewport is not None:
            self.report("Apply or close 3D View before closing the editor.", "Warning")
            return
        if any(edit.dirty for edit in self.edits.values()) and not messagebox.askokcancel(
                "Unsaved changes", "Close the editor and discard unsaved changes?", parent=self.root):
            return
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validator", type=Path, default=ROOT / "build/nexus-project-validate")
    parser.add_argument("--preview", type=Path, default=ROOT / "build/nexus-project-preview")
    parser.add_argument("--viewport", type=Path, default=ROOT / "build/nexus-project-viewport")
    args = parser.parse_args()
    try:
        root = tk.Tk()
        ProjectEditor(root, args.project.resolve(strict=True), args.output.resolve(),
                      args.validator.resolve(strict=True), args.preview.resolve(strict=True), args.viewport)
        root.mainloop()
    except (ValueError, OSError, tk.TclError) as error:
        parser.exit(1, f"nexus scene editor: {error}\n")


if __name__ == "__main__":
    main()

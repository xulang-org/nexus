#!/usr/bin/env python3
"""Generate deterministic pixel-art PNG atlases and scene files for 2.5D examples."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_hero_sheet(path: Path) -> None:
    """128x32 RGBA8 sprite sheet: 4 animation frames (32x32 each) with crisp alpha cutout."""
    img = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for frame in range(4):
        ox = frame * 32
        bob = 1 if frame in (1, 3) else 0
        stride = (-2, 0, 2, 0)[frame]
        # Boots (opaque dark brown)
        draw.rectangle([ox + 11 + stride, 26, ox + 14 + stride, 30], fill=(74, 46, 28, 255))
        draw.rectangle([ox + 17 - stride, 26, ox + 20 - stride, 30], fill=(74, 46, 28, 255))
        # Tunic (teal-blue)
        draw.rectangle([ox + 10, 15 - bob, ox + 21, 26 - bob], fill=(42, 134, 178, 255))
        # Belt (gold)
        draw.rectangle([ox + 10, 21 - bob, ox + 21, 22 - bob], fill=(232, 190, 66, 255))
        # Cape fluttering on the left
        cape_dx = 1 if frame in (1, 2) else 0
        draw.polygon(
            [(ox + 10, 15 - bob), (ox + 6 - cape_dx, 25 - bob), (ox + 10, 25 - bob)],
            fill=(196, 52, 62, 255),
        )
        # Head (warm peach)
        draw.rectangle([ox + 12, 7 - bob, ox + 19, 14 - bob], fill=(242, 206, 170, 255))
        # Eyes
        draw.point((ox + 14, 10 - bob), fill=(26, 28, 38, 255))
        draw.point((ox + 18, 10 - bob), fill=(26, 28, 38, 255))
        # Hat / hair (crimson band + deep navy)
        draw.rectangle([ox + 10, 4 - bob, ox + 21, 7 - bob], fill=(46, 54, 92, 255))
        draw.rectangle([ox + 12, 2 - bob, ox + 19, 4 - bob], fill=(46, 54, 92, 255))
        draw.rectangle([ox + 11, 6 - bob, ox + 20, 7 - bob], fill=(214, 72, 64, 255))
        # Staff + glowing lantern on right hand
        draw.rectangle([ox + 23, 9 - bob, ox + 24, 29], fill=(132, 92, 54, 255))
        draw.rectangle([ox + 22, 6 - bob, ox + 25, 9 - bob], fill=(255, 224, 112, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def make_props_sheet(path: Path) -> None:
    """64x32 RGBA8 sheet: tile 0 = cutout pine tree, tile 1 = stone archway with transparent center hole."""
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Tile 0 (x in [0, 32)): layered pixel-art pine tree
    draw.rectangle([14, 23, 17, 31], fill=(102, 66, 38, 255))
    draw.polygon([(15, 2), (7, 13), (24, 13)], fill=(44, 128, 72, 255))
    draw.polygon([(15, 7), (5, 19), (26, 19)], fill=(36, 112, 64, 255))
    draw.polygon([(15, 13), (4, 25), (27, 25)], fill=(28, 94, 54, 255))
    # Subtle highlight pixels on left slope
    draw.line([(15, 3), (8, 12)], fill=(78, 170, 96, 255))
    draw.line([(15, 8), (6, 18)], fill=(68, 152, 86, 255))

    # Tile 1 (x in [32, 64)): stone archway with a crisp transparent opening in the center
    ox = 32
    draw.rectangle([ox + 3, 4, ox + 28, 31], fill=(168, 162, 152, 255))
    draw.rectangle([ox + 2, 2, ox + 29, 7], fill=(198, 192, 180, 255))
    # Cut out the transparent doorway hole (alpha = 0)
    draw.rectangle([ox + 10, 12, ox + 21, 31], fill=(0, 0, 0, 0))
    # Stone brick accents
    draw.rectangle([ox + 5, 10, ox + 8, 14], fill=(140, 134, 126, 255))
    draw.rectangle([ox + 23, 18, ox + 26, 22], fill=(140, 134, 126, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def make_iso_tiles(path: Path) -> None:
    """256x64 RGBA8 sheet: 4 isometric 64x64 tiles (grass, stone, tall pillar block, water)."""
    img = Image.new("RGBA", (256, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def diamond(ox: int, cy: int, top_color, edge_color, side_left, side_right, depth: int):
        top = [(ox + 32, cy - 16), (ox + 63, cy), (ox + 32, cy + 16), (ox + 1, cy)]
        left_face = [
            (ox + 1, cy),
            (ox + 32, cy + 16),
            (ox + 32, cy + 16 + depth),
            (ox + 1, cy + depth),
        ]
        right_face = [
            (ox + 32, cy + 16),
            (ox + 63, cy),
            (ox + 63, cy + depth),
            (ox + 32, cy + 16 + depth),
        ]
        if depth > 0:
            draw.polygon(left_face, fill=side_left)
            draw.polygon(right_face, fill=side_right)
        draw.polygon(top, fill=top_color, outline=edge_color)

    # Tile 0: Grass block (ground plane center at y=40, thickness 8)
    diamond(0, 40, (86, 168, 92, 255), (56, 124, 62, 255), (104, 76, 52, 255), (78, 56, 38, 255), 8)
    # Tile 1: Cobblestone tile
    diamond(64, 40, (164, 168, 178, 255), (112, 118, 130, 255), (118, 122, 132, 255), (88, 92, 104, 255), 8)
    # Tile 2: Tall extruded 2.5D stone pillar (rises 28 px above ground center -> occludes hero!)
    diamond(128, 18, (214, 198, 166, 255), (146, 130, 102, 255), (176, 152, 118, 255), (128, 108, 82, 255), 30)
    # Tile 3: Water tile
    diamond(192, 40, (54, 148, 212, 255), (36, 108, 168, 255), (32, 92, 148, 255), (24, 72, 122, 255), 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def look_at_transform(eye, target, up=(0.0, 1.0, 0.0)):
    """Column-major 4x4 Node3D world transform whose affine_inverse() equals look_at_3d(eye, target, up)."""
    bx, by, bz = eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]
    bl = math.sqrt(bx * bx + by * by + bz * bz)
    bx, by, bz = bx / bl, by / bl, bz / bl
    rx = up[1] * bz - up[2] * by
    ry = up[2] * bx - up[0] * bz
    rz = up[0] * by - up[1] * bx
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rl, ry / rl, rz / rl
    vx = by * rz - bz * ry
    vy = bz * rx - bx * rz
    vz = bx * ry - by * rx
    return [
        rx, ry, rz, 0.0,
        vx, vy, vz, 0.0,
        bx, by, bz, 0.0,
        eye[0], eye[1], eye[2], 1.0,
    ]


def trans3d(x: float, y: float, z: float):
    return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]


def build_hd2d_scene() -> None:
    assets = ROOT / "examples/hd2d_scene/assets"
    hero_path = assets / "hero_sheet.png"
    props_path = assets / "props_sheet.png"
    make_hero_sheet(hero_path)
    make_props_sheet(props_path)

    hero_uid = "a1000000000000000000000000000001"
    props_uid = "a1000000000000000000000000000002"
    doc = {
        "format": "xu.scene",
        "version": 7,
        "nodes": [
            {"parent": -1, "name": "World", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(0, 0, 0)},
            {
                "parent": 0, "name": "CameraOrtho", "type": "Node3D", "visible": True, "process": "inherit",
                "transform": look_at_transform((0.0, 5.2, 7.6), (0.0, 0.7, 0.0)),
                "camera": {"projection": "orthographic", "vertical_size": 6.4, "near": 0.2, "far": 48.0},
            },
            {
                "parent": 0, "name": "CameraPersp", "type": "Node3D", "visible": True, "process": "inherit",
                "transform": look_at_transform((0.0, 4.2, 7.2), (0.0, 0.8, 0.0)),
                "camera": {"vertical_fov": 0.78, "near": 0.2, "far": 48.0},
            },
            {"parent": 0, "name": "Sun", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(0, 6, 0)},
            {"parent": 0, "name": "Hero", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(0.0, 0.0, 0.8)},
            {"parent": 0, "name": "Archway", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(0.0, 0.0, -1.6)},
            {"parent": 0, "name": "PineLeft", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(-2.5, 0.0, -0.8)},
            {"parent": 0, "name": "PineRight", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(2.5, 0.0, -0.5)},
            {"parent": 0, "name": "Emblem", "type": "Node3D", "visible": True, "process": "inherit", "transform": trans3d(0.0, 2.7, -1.6)},
        ],
        "resources": [
            {"uid": hero_uid, "type": "image_rgba", "path": "hero_sheet.png", "sha256": sha256_file(hero_path)},
            {"uid": props_uid, "type": "image_rgba", "path": "props_sheet.png", "sha256": sha256_file(props_path)},
        ],
        "surfaces": [],
        "audio_buses": [],
        "audio_emitters": [],
        "scripts": [],
        "script_connections": [],
        "lights": [
            {
                "node": 3,
                "type": "directional",
                "direction": [0.42, 0.84, 0.34],
                "radiance": [2.9, 2.75, 2.5],
                "cascades": {
                    "count": 3,
                    "distance": 18.0,
                    "split_lambda": 0.65,
                    "blend_fraction": 0.1,
                    "caster_padding": 8.0,
                    "resolution": 512,
                    "stabilization_step": 0.0625,
                    "raster_bias_texels": 0.00390625,
                },
            }
        ],
        "sprites_3d": [
            {
                "node": 4, "resource": hero_uid, "size": [1.35, 1.35], "pivot": [0.5, 0.0],
                "region": [0.0, 0.0, 0.25, 1.0], "billboard": "y_axis", "alpha_mode": "cutout",
                "alpha_cutoff": 0.5, "double_sided": True, "cast_shadow": True, "shaded": True,
                "flip_x": False, "flip_y": False, "tint": [1.0, 1.0, 1.0], "pixel_art": True,
            },
            {
                "node": 5, "resource": props_uid, "size": [2.4, 2.4], "pivot": [0.5, 0.0],
                "region": [0.5, 0.0, 0.5, 1.0], "billboard": "disabled", "alpha_mode": "cutout",
                "alpha_cutoff": 0.5, "double_sided": True, "cast_shadow": True, "shaded": True,
                "flip_x": False, "flip_y": False, "tint": [1.0, 1.0, 1.0], "pixel_art": True,
            },
            {
                "node": 6, "resource": props_uid, "size": [1.85, 2.05], "pivot": [0.5, 0.0],
                "region": [0.0, 0.0, 0.5, 1.0], "billboard": "y_axis", "alpha_mode": "cutout",
                "alpha_cutoff": 0.5, "double_sided": True, "cast_shadow": True, "shaded": True,
                "flip_x": False, "flip_y": False, "tint": [1.0, 1.0, 1.0], "pixel_art": True,
            },
            {
                "node": 7, "resource": props_uid, "size": [1.7, 1.9], "pivot": [0.5, 0.0],
                "region": [0.0, 0.0, 0.5, 1.0], "billboard": "y_axis", "alpha_mode": "cutout",
                "alpha_cutoff": 0.5, "double_sided": True, "cast_shadow": True, "shaded": True,
                "flip_x": True, "flip_y": False, "tint": [0.95, 1.0, 0.92], "pixel_art": True,
            },
            {
                "node": 8, "resource": hero_uid, "size": [0.65, 0.65], "pivot": [0.5, 0.5],
                "region": [0.25, 0.0, 0.25, 1.0], "billboard": "enabled", "alpha_mode": "cutout",
                "alpha_cutoff": 0.5, "double_sided": True, "cast_shadow": False, "shaded": False,
                "flip_x": False, "flip_y": False, "tint": [1.0, 0.96, 0.78], "pixel_art": True,
            },
        ],
        "tilemaps_2d": [],
    }
    (assets / "world.xuscene").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def build_isometric_2d_scene() -> None:
    assets = ROOT / "examples/isometric_2d/assets"
    tiles_path = assets / "iso_tiles.png"
    hero_path = assets / "hero_iso.png"
    make_iso_tiles(tiles_path)
    make_hero_sheet(hero_path)

    tiles_uid = "b2000000000000000000000000000001"
    w, h = 7, 7
    ground_cells = []
    ground_elev = []
    ground_tints = []
    for row in range(h):
        for col in range(w):
            if col == 0 or row == 0:
                ground_cells.append(3)  # water border along top-left/top-right
            elif 2 <= col <= 4 and 2 <= row <= 4:
                ground_cells.append(1)  # cobblestone central plaza
                if col == 3 and row == 3:
                    ground_elev.append({"col": col, "row": row, "value": 1.0})
            else:
                ground_cells.append(0)  # emerald grass
            if (col + row) % 2 == 1 and not (col == 0 or row == 0):
                ground_tints.append({"col": col, "row": row, "rgba": 0xEDF4EBFF})

    struct_cells = [-1] * (w * h)
    # Place isometric pillars that will Y-Sort interleave with the hero
    for col, row in [(2, 2), (4, 2), (2, 4), (4, 4), (3, 1)]:
        struct_cells[row * w + col] = 2

    doc = {
        "format": "xu.scene",
        "version": 8,
        "nodes": [
            {"parent": -1, "name": "World", "type": "Node2D", "visible": True, "process": "inherit", "transform": [1, 0, 0, 1, 0, 0]},
            {
                "parent": 0, "name": "Camera2D", "type": "Node2D", "visible": True, "process": "inherit",
                "transform": [1, 0, 0, 1, 480, 290],
                "camera": {"design_width": 960.0, "design_height": 640.0, "zoom": 1.45},
            },
            {"parent": 0, "name": "GroundLayer", "type": "Node2D", "visible": True, "process": "inherit", "transform": [1, 0, 0, 1, 480, 180]},
            {"parent": 0, "name": "StructureLayer", "type": "Node2D", "visible": True, "process": "inherit", "transform": [1, 0, 0, 1, 480, 180]},
            {"parent": 0, "name": "Hero", "type": "Node2D", "visible": True, "process": "inherit", "transform": [1, 0, 0, 1, 480, 276]},
        ],
        "resources": [
            {"uid": tiles_uid, "type": "image_rgba", "path": "iso_tiles.png", "sha256": sha256_file(tiles_path)},
        ],
        "surfaces": [],
        "audio_buses": [],
        "audio_emitters": [],
        "scripts": [],
        "script_connections": [],
        "lights": [],
        "sprites_3d": [],
        "tilemaps_2d": [
            {
                "node": 2,
                "resource": tiles_uid,
                "layout": "isometric",
                "width": w,
                "height": h,
                "tile_size": [64.0, 32.0],
                "elevation_step": 12.0,
                "tileset": {"columns": 4, "rows": 1, "draw_size": [64.0, 64.0], "origin": [0.5, 0.625]},
                "z_index": -10,
                "y_sort_cells": False,
                "y_offset": 0.0,
                "pixel_art": True,
                "cells": ground_cells,
                "elevations": ground_elev,
                "tints": ground_tints,
                "solid_tiles": [],
            },
            {
                "node": 3,
                "resource": tiles_uid,
                "layout": "isometric",
                "width": w,
                "height": h,
                "tile_size": [64.0, 32.0],
                "elevation_step": 12.0,
                "tileset": {"columns": 4, "rows": 1, "draw_size": [64.0, 64.0], "origin": [0.5, 0.75]},
                "z_index": 0,
                "y_sort_cells": True,
                "y_offset": 4.0,
                "pixel_art": True,
                "cells": struct_cells,
                "elevations": [],
                "tints": [],
                "solid_tiles": [2],
            },
        ],
    }
    (assets / "world.xuscene").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_hd2d_scene()
    build_isometric_2d_scene()
    print("Generated 2.5D example assets and scene files")

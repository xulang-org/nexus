"""Author the small indexed crate GLB used by both WebGL 3D demos."""
import json
import struct


def crate_glb(png):
    front = [(-1.1, .04, .95), (.8, .04, .95), (.8, 1.94, .95), (-1.1, 1.94, .95)]
    corners = front + [(x, y, -.95) for x, y, _ in front]
    faces = [((0, 1, 2, 3), (0, 0, 1)), ((1, 5, 6, 2), (1, 0, 0)),
             ((3, 2, 6, 7), (0, 1, 0)), ((4, 0, 3, 7), (-1, 0, 0)),
             ((5, 4, 7, 6), (0, 0, -1)), ((4, 5, 1, 0), (0, -1, 0))]
    uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]
    vertices = bytearray()
    indices = []
    for face, (points, normal) in enumerate(faces):
        for point, uv in zip(points, uvs):
            vertices.extend(struct.pack("<8f", *corners[point], *normal, *uv))
        indices.extend(face * 4 + i for i in (0, 1, 2, 0, 2, 3))
    elements = struct.pack("<36H", *indices)
    binary = vertices + elements + png
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteLength": len(vertices), "byteStride": 32, "target": 34962},
                        {"buffer": 0, "byteOffset": len(vertices), "byteLength": len(elements), "target": 34963},
                        {"buffer": 0, "byteOffset": len(vertices) + len(elements), "byteLength": len(png)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 24, "type": "VEC3",
                       "min": [-1.1, .04, -.95], "max": [.8, 1.94, .95]},
                      {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "count": 24, "type": "VEC3"},
                      {"bufferView": 0, "byteOffset": 24, "componentType": 5126, "count": 24, "type": "VEC2"},
                      {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"}],
        "images": [{"bufferView": 2, "mimeType": "image/png"}],
        "samplers": [{"minFilter": 9728, "magFilter": 9728, "wrapS": 33071, "wrapT": 33071}],
        "textures": [{"source": 0, "sampler": 0}],
        "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0}}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                    "indices": 3, "material": 0}]}],
        "nodes": [{"name": "Crate", "mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    metadata = json.dumps(document, separators=(",", ":")).encode("utf-8")
    metadata += b" " * (-len(metadata) % 4)
    binary += b"\0" * (-len(binary) % 4)
    return (struct.pack("<III", 0x46546C67, 2, 28 + len(metadata) + len(binary))
            + struct.pack("<I4s", len(metadata), b"JSON") + metadata
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)

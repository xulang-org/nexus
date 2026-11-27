#version 450

layout(location = 0) flat in uint meshlet_id;
layout(location = 0) out uint out_vis;

void main() {
    out_vis = (((meshlet_id & 0xFFFFFFu) << 8u) | (uint(gl_PrimitiveID) & 0xFFu)) + 1u;
}

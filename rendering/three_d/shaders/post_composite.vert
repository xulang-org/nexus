#version 450

layout(location = 0) out vec2 uv;

void main() {
    uint vid = uint(gl_VertexIndex);
    vec2 pos = vec2((vid == 1u) ? 3.0 : -1.0, (vid == 2u) ? 3.0 : -1.0);
    gl_Position = vec4(pos, 0.0, 1.0);
    uv = vec2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5);
}

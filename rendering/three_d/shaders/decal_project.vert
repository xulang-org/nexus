#version 450

layout(location = 0) in vec3 position;
layout(set = 1, binding = 0, std140) uniform DecalVertUniform {
    mat4 mvp;
} u;

void main() {
    gl_Position = u.mvp * vec4(position, 1.0);
}

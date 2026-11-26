#version 450

layout(location = 0) in vec3 position;
layout(location = 1) in vec4 color;
layout(location = 2) in vec3 normal;
layout(location = 3) in vec2 uv;
layout(location = 4) in vec4 tangent;

layout(set = 1, binding = 0, std140) uniform TerrainVertUniform {
    mat4 view_proj;
    mat4 model;
    mat4 view;
} u;

layout(location = 0) out vec4 vertex_color;
layout(location = 1) out vec3 world;
layout(location = 2) out vec3 world_normal;
layout(location = 3) out vec2 splat_uv;
layout(location = 4) out float view_depth;

void main() {
    vec4 world4 = u.model * vec4(position, 1.0);
    gl_Position = u.view_proj * world4;
    vertex_color = color;
    world = world4.xyz;
    world_normal = normalize((u.model * vec4(normal, 0.0)).xyz);
    splat_uv = uv;
    view_depth = -(u.view * vec4(world4.xyz, 1.0)).z;
}

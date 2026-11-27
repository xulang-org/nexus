#version 450

layout(location = 0) in vec3 position;
layout(location = 1) in vec4 color;
layout(location = 2) in vec3 normal;
layout(location = 3) in vec2 uv;
layout(location = 4) in vec4 tangent;

layout(set = 1, binding = 0, std140) uniform Matrices {
    mat4 mvp;
    mat4 model;
    mat4 normals;
    mat4 view;
} m;

layout(location = 0) out vec4 vertex_color;
layout(location = 1) out vec3 world;
layout(location = 2) out vec3 world_normal;
layout(location = 3) out vec2 texture_uv;
layout(location = 4) out vec3 world_tangent;
layout(location = 5) out vec3 world_bitangent;
layout(location = 6) out float view_depth;

void main() {
    texture_uv = uv;
    gl_Position = m.mvp * vec4(position, 1.0);
    vertex_color = color;
    vec4 world4 = m.model * vec4(position, 1.0);
    world = world4.xyz;
    world_tangent = (m.model * vec4(tangent.xyz, 0.0)).xyz;
    world_bitangent = (m.model * vec4(cross(normal, tangent.xyz) * tangent.w, 0.0)).xyz;
    world_normal = (m.normals * vec4(normal, 0.0)).xyz;
    view_depth = -(m.view * vec4(world4.xyz, 1.0)).z;
}

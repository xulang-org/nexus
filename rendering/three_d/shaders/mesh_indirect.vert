#version 450

struct InstanceGpu {
    mat4 model;
    mat4 normals;
    vec4 bounds_min;
    vec4 bounds_max;
    uvec4 draw_info;
};

layout(location = 0) in vec3 position;
layout(location = 1) in vec4 color;
layout(location = 2) in vec3 normal;
layout(location = 3) in vec2 uv;
layout(location = 4) in vec4 tangent;

layout(set = 1, binding = 0, std140) uniform ViewUniform {
    mat4 view_proj;
    mat4 view;
} u;

layout(set = 0, binding = 0, std430) readonly buffer InstancesBuf {
    InstanceGpu instances[];
};

layout(location = 0) out vec4 vertex_color;
layout(location = 1) out vec3 world;
layout(location = 2) out vec3 world_normal;
layout(location = 3) out vec2 texture_uv;
layout(location = 4) out vec3 world_tangent;
layout(location = 5) out vec3 world_bitangent;
layout(location = 6) out float view_depth;
layout(location = 7) flat out uint material_id;
layout(location = 8) flat out float orientation;

void main() {
    InstanceGpu inst = instances[gl_InstanceIndex];
    texture_uv = uv;
    vec4 world4 = inst.model * vec4(position, 1.0);
    gl_Position = u.view_proj * world4;
    vertex_color = color;
    world = world4.xyz;
    world_tangent = (inst.model * vec4(tangent.xyz, 0.0)).xyz;
    world_bitangent = (inst.model * vec4(cross(normal, tangent.xyz) * tangent.w, 0.0)).xyz;
    world_normal = (inst.normals * vec4(normal, 0.0)).xyz;
    view_depth = -(u.view * vec4(world4.xyz, 1.0)).z;
    material_id = inst.draw_info.w;
    orientation = inst.bounds_min.w;
}

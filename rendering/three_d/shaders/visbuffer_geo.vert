#version 450

struct MeshletGpu {
    vec4 bound_sphere;
    vec4 cone;
    uvec4 info;
};

struct MeshletInstanceGpu {
    mat4 model;
    mat4 normals;
    vec4 scale_info;
    vec4 base_metallic;
    vec4 emission_roughness;
    vec4 maps_normal;
    vec4 surface;
    vec4 uv_rect;
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

layout(set = 0, binding = 0, std430) readonly buffer MeshletsBuf { MeshletGpu meshlets[]; };
layout(set = 0, binding = 1, std430) readonly buffer InstancesBuf { MeshletInstanceGpu instances[]; };

layout(location = 0) flat out uint meshlet_id;

void main() {
    MeshletGpu m = meshlets[gl_InstanceIndex];
    MeshletInstanceGpu inst = instances[m.info.x];
    gl_Position = u.view_proj * (inst.model * vec4(position, 1.0));
    meshlet_id = uint(gl_InstanceIndex);
}

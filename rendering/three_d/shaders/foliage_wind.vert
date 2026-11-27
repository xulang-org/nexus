#version 450

struct FoliageInstanceGpu {
    vec4 pos_scale;
    vec4 rot_wind;
    vec4 tint_var;
};

layout(location = 0) in vec3 position;
layout(location = 1) in vec4 color;
layout(location = 2) in vec3 normal;
layout(location = 3) in vec2 uv;
layout(location = 4) in vec4 tangent;

layout(set = 1, binding = 0, std140) uniform FoliageVertUniform {
    mat4 view_proj;
    mat4 view;
    vec4 wind_dir_strength;
    vec4 wind_wave;
    vec4 fade_camera;
    vec4 fade_extra;
} u;

layout(set = 0, binding = 0, std430) readonly buffer InstancesBuf { FoliageInstanceGpu instances[]; };
layout(set = 0, binding = 1, std430) readonly buffer VisibleIdxBuf { uint visible_indices[]; };

layout(location = 0) out vec4 vertex_color;
layout(location = 1) out vec3 world;
layout(location = 2) out vec3 world_normal;
layout(location = 3) out vec2 texture_uv;
layout(location = 4) out vec3 instance_tint;
layout(location = 5) out float height_frac;
layout(location = 6) out float fade;
layout(location = 7) out float view_depth;

void main() {
    uint real_idx = visible_indices[gl_InstanceIndex];
    FoliageInstanceGpu inst = instances[real_idx];

    float dist = length(inst.pos_scale.xyz - u.fade_camera.xyz);
    float fade_start = u.fade_camera.w;
    float max_dist = max(u.fade_extra.x, fade_start + 0.001);
    float fade_val = 1.0 - smoothstep(fade_start, max_dist, dist);

    float s_xz = inst.pos_scale.w;
    float s_y = s_xz * inst.rot_wind.w * mix(0.35, 1.0, fade_val);

    vec3 lp = vec3(position.x * s_xz, position.y * s_y, position.z * s_xz);
    float cy = inst.rot_wind.x, sy = inst.rot_wind.y;
    vec3 rot_p = vec3(lp.x * cy + lp.z * sy, lp.y, -lp.x * sy + lp.z * cy);
    vec3 rot_n = vec3(normal.x * cy + normal.z * sy, normal.y, -normal.x * sy + normal.z * cy);

    float h_frac = clamp(max(uv.y, position.y * u.fade_extra.y), 0.0, 1.0);
    float bend = (h_frac * h_frac) / max(u.fade_extra.z, 0.25);

    vec2 wdir = u.wind_dir_strength.xy;
    wdir /= max(length(wdir), 1e-5);
    vec2 perp = vec2(-wdir.y, wdir.x);

    float time = u.wind_dir_strength.w;
    float phase = dot(inst.pos_scale.xz, wdir) * u.wind_wave.y + inst.rot_wind.z;
    float primary = sin(time * u.wind_wave.x + phase);
    float gust = sin(time * u.wind_wave.w + dot(inst.pos_scale.xz, perp) * (u.wind_wave.y * 0.65) + inst.rot_wind.z * 1.7);
    float disp_main = (u.wind_dir_strength.z * (0.45 + 0.55 * primary) + u.wind_wave.z * gust) * bend;
    float disp_cross = u.wind_wave.z * 0.45 * cos(time * u.wind_wave.x * 1.3 + inst.rot_wind.z) * bend;

    vec3 world_pos = inst.pos_scale.xyz + rot_p;
    world_pos.xz += wdir * disp_main + perp * disp_cross;
    world_pos.y -= min(abs(disp_main) * 0.18, s_y * 0.35 * h_frac);

    vec3 bent_n = normalize(rot_n + vec3(wdir.x * disp_main, 0.35, wdir.y * disp_main));

    gl_Position = u.view_proj * vec4(world_pos, 1.0);
    vertex_color = color;
    world = world_pos;
    world_normal = bent_n;
    texture_uv = uv;
    instance_tint = inst.tint_var.rgb;
    height_frac = h_frac;
    fade = fade_val;
    view_depth = -(u.view * vec4(world_pos, 1.0)).z;
}

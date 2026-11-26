#version 450

layout(location = 0) in vec4 color;
layout(location = 1) in vec2 atlas_uv;
layout(location = 2) in vec2 local_uv;
layout(location = 3) in float view_z;
layout(location = 4) in float additive;

layout(set = 2, binding = 0) uniform sampler2D sprite_tex;
layout(set = 2, binding = 1) uniform sampler2D scene_depth_tex;

layout(set = 3, binding = 0, std140) uniform ParticleFragUniform {
    mat4 inv_proj;
    vec4 vp_soft_mode;
    vec4 flags;
    vec4 pad;
} u;

layout(location = 0) out vec4 output_color;

float reconstruct_view_dist(mat4 inv_proj, vec2 uv, float depth) {
    float ndc_x = uv.x * 2.0 - 1.0, ndc_y = 1.0 - uv.y * 2.0;
    vec4 v = inv_proj * vec4(ndc_x, ndc_y, depth, 1.0);
    return -(v.z / max(v.w, 1e-6));
}

void main() {
    vec2 screen_uv = clamp(gl_FragCoord.xy / max(u.vp_soft_mode.xy, vec2(1.0)), vec2(0.0), vec2(1.0));
    float soft_fade = 1.0;
    if (u.flags.x > 0.5) {
        float scene_d = textureLod(scene_depth_tex, screen_uv, 0.0).r;
        if (scene_d > 1e-6) {
            if (gl_FragCoord.z <= scene_d) discard;
            if (u.vp_soft_mode.z > 1e-4) {
                float scene_view_z = reconstruct_view_dist(u.inv_proj, screen_uv, scene_d);
                soft_fade = clamp((scene_view_z - view_z) / u.vp_soft_mode.z, 0.0, 1.0);
            }
        }
    }

    vec4 tex_c = texture(sprite_tex, atlas_uv);
    vec2 centered = local_uv * 2.0 - 1.0;
    float r2 = dot(centered, centered), shape_a = 1.0;
    int vmode = int(u.vp_soft_mode.w + 0.5);
    if (vmode == 1) shape_a = pow(clamp(1.0 - r2, 0.0, 1.0), max(u.flags.y, 0.25));
    else if (vmode == 2) {
        float r = sqrt(r2), inner = clamp(u.flags.z, 0.05, 0.8);
        shape_a = smoothstep(inner, inner + 0.15, r) * (1.0 - smoothstep(0.85, 1.0, r));
    }

    float alpha = clamp(color.a * tex_c.a * shape_a * soft_fade, 0.0, 1.0);
    if (alpha <= 1e-4) discard;
    vec3 rgb = color.rgb * tex_c.rgb * alpha;
    float a_out = alpha * (1.0 - clamp(additive, 0.0, 1.0));
    output_color = vec4(rgb, a_out);
}

#version 450
#extension GL_GOOGLE_include_directive : require
#define XU_VEC3 vec3
#define XU_VEC4 vec4
#define XU_MIX mix
#define XU_FINITE(x) (!(isnan(x) || isinf(x)))
#include "lighting.inc"
#define XU_VEC2 vec2
#define XU_DDX(v) dFdx(v)
#define XU_DDY(v) dFdy(v)
#define XU_MAT4 mat4
#define XU_MUL(m,v) ((m)*(v))
#define XU_SHADOW_RESOURCES sampler2D shadow_map
#define XU_SHADOW_READ(uv) textureLod(shadow_map,uv,0.0).r
#define XU_SHADOW_ARGS shadow_map
#include "shadow.inc"
layout(location=0) in vec4 vertex_color;
layout(location=1) in vec3 world;
layout(location=2) in vec3 world_normal;
layout(location=3) in vec2 texture_uv;
layout(location=4) in vec3 world_tangent;
layout(location=5) in vec3 world_bitangent;
layout(set=3,binding=2,std140) uniform Shadow { mat4 mvp[4]; vec4 direction_bias; vec4 shadow_filter; vec4 depth; vec4 camera_depth; vec4 ranges[4]; vec4 limits; vec4 gradient_scales; } s;
layout(set=2,binding=5) uniform sampler2D shadow_texture;
layout(set=2,binding=0) uniform sampler2D base_texture;
layout(set=2,binding=1) uniform sampler2D orm_texture;
layout(set=2,binding=2) uniform sampler2D emission_texture;
layout(set=2,binding=3) uniform sampler2D normal_texture;
layout(set=2,binding=4) uniform sampler2D occlusion_texture;
layout(set=3,binding=0,std140) uniform Material { vec4 base_metallic; vec4 emission_roughness; vec4 maps_normal; vec4 surface; vec4 uv_rect; } p;
layout(set=3,binding=1,std140) uniform Lighting { vec4 ambient_count; vec4 eye_exposure; vec4 sources[XU_MAX_LIGHTS*4]; } l;
layout(location=0) out vec4 output_color;
void main() {
    if (p.surface.z < 0.5) { output_color=vertex_color; return; };
    int mask = int(p.maps_normal.x);
    vec2 sample_uv = p.uv_rect.xy + texture_uv * p.uv_rect.zw;
    vec3 base = p.base_metallic.xyz * vertex_color.xyz;
    float alpha = vertex_color.a;
    if ((mask & 1) != 0) {
        vec4 base_texel = texture(base_texture, sample_uv);
        base *= base_texel.rgb;
        alpha *= base_texel.a;
    }
    float out_alpha = 1.0;
    if (p.surface.w < -0.5) {
        out_alpha = clamp(alpha * (-p.surface.w - 1.0), 0.0, 1.0);
    } else if (p.surface.w > 0.0 && alpha < p.surface.w) {
        discard;
    }
    if (p.surface.z > 1.5) {
        vec3 clamped = clamp(base, vec3(0.0, 0.0, 0.0), vec3(1.0, 1.0, 1.0));
        output_color = vec4(srgb_channel(clamped.x), srgb_channel(clamped.y), srgb_channel(clamped.z), out_alpha);
        return;
    }
    vec3 orm = vec3(1.0, 1.0, 1.0);
    if ((mask & 2) != 0) orm = texture(orm_texture, sample_uv).rgb;
    float ao_strength = p.maps_normal.y;
    if ((mask & 16) != 0) { orm.x = texture(occlusion_texture, sample_uv).r; ao_strength = p.surface.y; }
    vec3 emission = p.emission_roughness.xyz;
    if ((mask & 4) != 0) emission *= texture(emission_texture, sample_uv).rgb;
    vec3 shading_normal = world_normal;
    if ((mask & 8) != 0) {
        vec3 adj_tangent = p.uv_rect.z < 0.0 ? -world_tangent : world_tangent;
        vec3 adj_bitangent = p.uv_rect.w < 0.0 ? -world_bitangent : world_bitangent;
        shading_normal = normal_map_direction(world_normal, adj_tangent, adj_bitangent, texture(normal_texture, sample_uv).rgb, p.maps_normal.z);
    }
    bool surface_front = gl_FrontFacing;
    if (p.surface.x < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;
    float metallic = p.base_metallic.w * orm.z;
    float roughness = max(0.045, p.emission_roughness.w * orm.y);
    float occlusion = 1.0 + ao_strength * (orm.x - 1.0);
    vec3 linear_color = l.ambient_count.xyz * occlusion * base * (1.0 - metallic) + emission;
    for (int i = 0; i < XU_MAX_LIGHTS && i < int(l.ambient_count.w); ++i) {
        int offset = i * 4;
        float visibility = 1.0;
        if (s.shadow_filter.w > 0.5 && i == int(s.shadow_filter.z)) {
            if (s.shadow_filter.w > 3.5) visibility = cascade_shadow_visibility(world,world_normal,XU_MUL(s.mvp[0],XU_VEC4(world,1.0)),XU_MUL(s.mvp[1],XU_VEC4(world,1.0)),XU_MUL(s.mvp[2],XU_VEC4(world,1.0)),XU_MUL(s.mvp[3],XU_VEC4(world,1.0)),s.camera_depth,s.ranges[0],s.ranges[1],s.ranges[2],s.ranges[3],s.limits,s.direction_bias,s.shadow_filter,s.depth,s.gradient_scales,shadow_texture);
            else visibility = shadow_visibility(world,world_normal,s.mvp[0],s.direction_bias,s.shadow_filter,s.depth,shadow_texture);
        }
        linear_color += source_direct(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz,
            l.sources[offset], l.sources[offset+1], l.sources[offset+2], l.sources[offset+3]) * visibility;
    }
    output_color=vec4(finish_lighting(linear_color,l.eye_exposure.w),out_alpha);
}

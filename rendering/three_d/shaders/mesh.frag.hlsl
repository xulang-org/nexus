#define XU_VEC3 float3
#define XU_VEC4 float4
#define XU_MIX lerp
#define XU_FINITE isfinite
#include "lighting.inc"
#define XU_VEC2 float2
#define XU_DDX(v) ddx(v)
#define XU_DDY(v) ddy(v)
#define XU_MAT4 float4x4
#define XU_MUL(m,v) mul(m,v)
#define XU_SHADOW_RESOURCES Texture2D<float4> shadow_map, SamplerState shadow_sampling
#define XU_SHADOW_READ(uv) shadow_map.SampleLevel(shadow_sampling,uv,0.0).r
#define XU_SHADOW_ARGS shadow_map,shadow_sampling
#include "shadow.inc"
struct Material { float4 base_metallic; float4 emission_roughness; float4 maps_normal; float4 surface; float4 uv_rect; };
struct Shadow { column_major float4x4 mvp[4]; float4 direction_bias; float4 shadow_filter; float4 depth; float4 camera_depth; float4 ranges[4]; float4 limits; float4 gradient_scales; };
struct Lighting { float4 ambient_count; float4 eye_exposure; float4 sources[XU_MAX_LIGHTS*4]; };
cbuffer MaterialBlock : register(b0,space3) { Material p; };
cbuffer LightingBlock : register(b1,space3) { Lighting l; };
cbuffer ShadowBlock : register(b2,space3) { Shadow s; };
Texture2D<float4> shadow_texture : register(t5,space2);
SamplerState shadow_sampler : register(s5,space2);
Texture2D<float4> base_texture : register(t0,space2);
SamplerState base_sampler : register(s0,space2);
Texture2D<float4> orm_texture : register(t1,space2);
SamplerState orm_sampler : register(s1,space2);
Texture2D<float4> emission_texture : register(t2,space2);
SamplerState emission_sampler : register(s2,space2);
Texture2D<float4> normal_texture : register(t3,space2);
SamplerState normal_sampler : register(s3,space2);
Texture2D<float4> occlusion_texture : register(t4,space2);
SamplerState occlusion_sampler : register(s4,space2);
float4 main(float4 color : TEXCOORD0,float3 world : TEXCOORD1,float3 normal : TEXCOORD2,float2 uv : TEXCOORD3,float3 tangent : TEXCOORD4,float3 bitangent : TEXCOORD5,bool front : SV_IsFrontFace) : SV_Target0 {
    if (p.surface.z < 0.5) return color;
    int mask = int(p.maps_normal.x);
    float2 sample_uv = p.uv_rect.xy + uv * p.uv_rect.zw;
    float3 base = p.base_metallic.xyz * color.xyz;
    float alpha = color.a;
    if ((mask & 1) != 0) {
        float4 base_texel = base_texture.Sample(base_sampler, sample_uv);
        base *= base_texel.rgb;
        alpha *= base_texel.a;
    }
    float out_alpha = 1.0;
    if (p.surface.w < -0.5) {
        out_alpha = clamp(alpha * (-p.surface.w - 1.0), 0.0, 1.0);
    } else if (p.surface.w > 0.0) {
        clip(alpha - p.surface.w);
    }
    if (p.surface.z > 1.5) {
        float3 clamped = saturate(base);
        return float4(srgb_channel(clamped.x), srgb_channel(clamped.y), srgb_channel(clamped.z), out_alpha);
    }
    float3 orm = float3(1.0, 1.0, 1.0);
    if ((mask & 2) != 0) orm = orm_texture.Sample(orm_sampler, sample_uv).rgb;
    float ao_strength = p.maps_normal.y;
    if ((mask & 16) != 0) { orm.x = occlusion_texture.Sample(occlusion_sampler, sample_uv).r; ao_strength = p.surface.y; }
    float3 emission = p.emission_roughness.xyz;
    if ((mask & 4) != 0) emission *= emission_texture.Sample(emission_sampler, sample_uv).rgb;
    float3 shading_normal = normal;
    if ((mask & 8) != 0) {
        float3 adj_tangent = p.uv_rect.z < 0.0 ? -tangent : tangent;
        float3 adj_bitangent = p.uv_rect.w < 0.0 ? -bitangent : bitangent;
        shading_normal = normal_map_direction(normal, adj_tangent, adj_bitangent, normal_texture.Sample(normal_sampler, sample_uv).rgb, p.maps_normal.z);
    }
    bool surface_front = front;
    if (p.surface.x < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;
    float metallic = p.base_metallic.w * orm.z;
    float roughness = max(0.045, p.emission_roughness.w * orm.y);
    float occlusion = 1.0 + ao_strength * (orm.x - 1.0);
    float3 linear_color = l.ambient_count.xyz * occlusion * base * (1.0 - metallic) + emission;
    for (int i = 0; i < XU_MAX_LIGHTS && i < int(l.ambient_count.w); ++i) {
        int offset = i * 4;
        float visibility = 1.0;
        if (s.shadow_filter.w > 0.5 && i == int(s.shadow_filter.z)) {
            if (s.shadow_filter.w > 3.5) visibility = cascade_shadow_visibility(world,normal,XU_MUL(s.mvp[0],XU_VEC4(world,1.0)),XU_MUL(s.mvp[1],XU_VEC4(world,1.0)),XU_MUL(s.mvp[2],XU_VEC4(world,1.0)),XU_MUL(s.mvp[3],XU_VEC4(world,1.0)),s.camera_depth,s.ranges[0],s.ranges[1],s.ranges[2],s.ranges[3],s.limits,s.direction_bias,s.shadow_filter,s.depth,s.gradient_scales,shadow_texture,shadow_sampler);
            else visibility = shadow_visibility(world,normal,s.mvp[0],s.direction_bias,s.shadow_filter,s.depth,shadow_texture,shadow_sampler);
        }
        linear_color += source_direct(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz,
            l.sources[offset], l.sources[offset+1], l.sources[offset+2], l.sources[offset+3]) * visibility;
    }
    return float4(finish_lighting(linear_color,l.eye_exposure.w),out_alpha);
}

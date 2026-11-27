cbuffer ParticleFragUniform : register(b0, space3) {
    column_major float4x4 inv_proj;
    float4 vp_soft_mode;
    float4 flags;
    float4 pad;
};

Texture2D<float4> sprite_tex : register(t0, space2);
Texture2D<float> scene_depth_tex : register(t1, space2);
SamplerState sprite_samp : register(s0, space2);
SamplerState depth_samp : register(s1, space2);

struct Input {
    float4 position : SV_Position;
    float4 color : TEXCOORD0;
    float2 atlas_uv : TEXCOORD1;
    float2 local_uv : TEXCOORD2;
    float view_z : TEXCOORD3;
    float additive : TEXCOORD4;
};

float reconstruct_view_dist(float4x4 m, float2 uv, float depth) {
    float ndc_x = uv.x * 2.0 - 1.0, ndc_y = 1.0 - uv.y * 2.0;
    float4 v = mul(m, float4(ndc_x, ndc_y, depth, 1.0));
    return -(v.z / max(v.w, 1e-6));
}

float4 main(Input input) : SV_Target0 {
    float2 screen_uv = clamp(input.position.xy / max(vp_soft_mode.xy, float2(1.0, 1.0)), float2(0.0, 0.0), float2(1.0, 1.0));
    float soft_fade = 1.0;
    if (flags.x > 0.5) {
        float scene_d = scene_depth_tex.SampleLevel(depth_samp, screen_uv, 0.0).r;
        if (scene_d > 1e-6) {
            if (input.position.z <= scene_d) discard;
            if (vp_soft_mode.z > 1e-4) {
                float scene_view_z = reconstruct_view_dist(inv_proj, screen_uv, scene_d);
                soft_fade = clamp((scene_view_z - input.view_z) / vp_soft_mode.z, 0.0, 1.0);
            }
        }
    }

    float4 tex_c = sprite_tex.Sample(sprite_samp, input.atlas_uv);
    float2 centered = input.local_uv * 2.0 - 1.0;
    float r2 = dot(centered, centered), shape_a = 1.0;
    int vmode = int(vp_soft_mode.w + 0.5);
    if (vmode == 1) shape_a = pow(clamp(1.0 - r2, 0.0, 1.0), max(flags.y, 0.25));
    else if (vmode == 2) {
        float r = sqrt(r2), inner = clamp(flags.z, 0.05, 0.8);
        shape_a = smoothstep(inner, inner + 0.15, r) * (1.0 - smoothstep(0.85, 1.0, r));
    }

    float alpha = clamp(input.color.a * tex_c.a * shape_a * soft_fade, 0.0, 1.0);
    if (alpha <= 1e-4) discard;
    float3 rgb = input.color.rgb * tex_c.rgb * alpha;
    float a_out = alpha * (1.0 - clamp(input.additive, 0.0, 1.0));
    return float4(rgb, a_out);
}

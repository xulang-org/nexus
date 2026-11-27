Texture2D<float4> scene_tex : register(t0,space2);
SamplerState scene_sampler : register(s0,space2);
Texture2D<float4> bloom_tex : register(t1,space2);
SamplerState bloom_sampler : register(s1,space2);

cbuffer Bloom2DUniform : register(b0,space3) {
    float4 params0;
    float4 params1;
};

struct Input {
    float4 position : SV_Position;
    float4 color : TEXCOORD0;
    float2 uv : TEXCOORD1;
};

float3 bright_extract(float3 c, float threshold, float soft_knee) {
    float luma = max(c.r, max(c.g, c.b));
    float knee = max(soft_knee, 1e-4);
    float soft = clamp(luma - threshold + knee, 0.0, 2.0 * knee);
    soft = (soft * soft) / (4.0 * knee);
    float contrib = max(soft, luma - threshold) / max(luma, 1e-5);
    return c * max(contrib, 0.0);
}

float4 main(Input input) : SV_Target0 {
    static const float offsets[9] = { -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0 };
    static const float weights[9] = { 0.016216, 0.054054, 0.121622, 0.194595, 0.227027, 0.194595, 0.121622, 0.054054, 0.016216 };
    if (params0.x < 0.5) {
        float3 sum = float3(0.0, 0.0, 0.0);
        for (int k = 0; k < 9; ++k) {
            float2 suv = clamp(input.uv + float2(offsets[k] * params1.z * params1.x, 0.0), float2(0.0, 0.0), float2(1.0, 1.0));
            float3 tex = scene_tex.Sample(scene_sampler, suv).rgb;
            sum += bright_extract(tex, params0.y, params0.z) * weights[k];
        }
        return float4(sum, 1.0);
    }
    float3 vblur = float3(0.0, 0.0, 0.0);
    for (int k = 0; k < 9; ++k) {
        float2 buv = clamp(input.uv + float2(0.0, offsets[k] * params1.z * params1.y), float2(0.0, 0.0), float2(1.0, 1.0));
        vblur += bloom_tex.Sample(bloom_sampler, buv).rgb * weights[k];
    }
    float4 base = scene_tex.Sample(scene_sampler, input.uv);
    float3 out_rgb = clamp(base.rgb + vblur * params0.w, float3(0.0, 0.0, 0.0), float3(1.0, 1.0, 1.0));
    return float4(out_rgb * input.color.rgb, base.a * input.color.a);
}

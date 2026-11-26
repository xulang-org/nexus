cbuffer CompositeParams : register(b0, space3) {
    float4 gains;
    float4 mode;
};

Texture2D<float4> hdr_tex : register(t0, space2);
Texture2D<float> ao_tex : register(t1, space2);
Texture2D<float4> ssr_tex : register(t2, space2);
Texture2D<float4> bloom_tex : register(t3, space2);

SamplerState hdr_sampler : register(s0, space2);
SamplerState ao_sampler : register(s1, space2);
SamplerState ssr_sampler : register(s2, space2);
SamplerState bloom_sampler : register(s3, space2);

struct Input {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

float srgb_channel(float value) {
    return value <= 0.0031308 ? 12.92 * value : 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

float3 aces_filmic(float3 x) {
    float3 a = x * (2.51 * x + 0.03);
    float3 b = x * (2.43 * x + 0.59) + 0.14;
    return clamp(a / max(b, float3(1e-6, 1e-6, 1e-6)), float3(0.0, 0.0, 0.0), float3(1.0, 1.0, 1.0));
}

float4 main(Input input) : SV_Target0 {
    float3 hdr = hdr_tex.SampleLevel(hdr_sampler, input.uv, 0.0).rgb;
    float ao = ao_tex.SampleLevel(ao_sampler, input.uv, 0.0).r;
    float4 ssr = ssr_tex.SampleLevel(ssr_sampler, input.uv, 0.0);
    float3 bloom = bloom_tex.SampleLevel(bloom_sampler, input.uv, 0.0).rgb;

    float ao_factor = lerp(1.0, ao, clamp(gains.x, 0.0, 1.0));
    float3 combined = hdr * ao_factor + ssr.rgb * (ssr.a * gains.y) + bloom * gains.z;
    float3 exposed = max(combined * gains.w, float3(0.0, 0.0, 0.0));
    float3 mapped = mode.x > 0.5 ? aces_filmic(exposed) : (exposed / (1.0 + exposed));
    return float4(srgb_channel(mapped.x), srgb_channel(mapped.y), srgb_channel(mapped.z), 1.0);
}

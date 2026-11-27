cbuffer BloomDownParams : register(b0, space2) {
    float4 dims;
    float4 cfg;
};

Texture2D<float4> src_tex : register(t0, space0);
SamplerState src_sampler : register(s0, space0);
RWTexture2D<float4> dst_tex : register(u0, space1);

float karis_weight(float3 c) {
    float l = max(dot(c, float3(0.2126, 0.7152, 0.0722)), 0.0);
    return 1.0 / (1.0 + l);
}

float3 soft_threshold(float3 c, float thresh, float knee) {
    float lum = max(c.r, max(c.g, c.b));
    float soft = clamp(lum - thresh + knee, 0.0, 2.0 * knee);
    soft = (soft * soft) / (4.0 * knee);
    float contrib = max(soft, lum - thresh) / max(lum, 1e-5);
    return c * max(contrib, 0.0);
}

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint dw = uint(dims.z), dh = uint(dims.w);
    if (gid.x >= dw || gid.y >= dh) return;

    float2 uv = (float2(gid) + 0.5) / float2(dims.z, dims.w);
    float2 dx = float2(1.0 / dims.x, 0.0);
    float2 dy = float2(0.0, 1.0 / dims.y);

    float3 a = src_tex.SampleLevel(src_sampler, uv - 2.0 * dx - 2.0 * dy, 0.0).rgb;
    float3 b = src_tex.SampleLevel(src_sampler, uv - 2.0 * dy, 0.0).rgb;
    float3 c = src_tex.SampleLevel(src_sampler, uv + 2.0 * dx - 2.0 * dy, 0.0).rgb;
    float3 d = src_tex.SampleLevel(src_sampler, uv - 2.0 * dx, 0.0).rgb;
    float3 e = src_tex.SampleLevel(src_sampler, uv, 0.0).rgb;
    float3 f = src_tex.SampleLevel(src_sampler, uv + 2.0 * dx, 0.0).rgb;
    float3 g = src_tex.SampleLevel(src_sampler, uv - 2.0 * dx + 2.0 * dy, 0.0).rgb;
    float3 h = src_tex.SampleLevel(src_sampler, uv + 2.0 * dy, 0.0).rgb;
    float3 i = src_tex.SampleLevel(src_sampler, uv + 2.0 * dx + 2.0 * dy, 0.0).rgb;

    float3 j = src_tex.SampleLevel(src_sampler, uv - dx - dy, 0.0).rgb;
    float3 k = src_tex.SampleLevel(src_sampler, uv + dx - dy, 0.0).rgb;
    float3 l = src_tex.SampleLevel(src_sampler, uv - dx + dy, 0.0).rgb;
    float3 m = src_tex.SampleLevel(src_sampler, uv + dx + dy, 0.0).rgb;

    float3 out_rgb;
    if (cfg.z > 0.5) {
        float thresh = cfg.x;
        float knee = max(cfg.y, 1e-4);
        float3 g0 = soft_threshold((a + b + d + e) * 0.25, thresh, knee);
        float3 g1 = soft_threshold((b + c + e + f) * 0.25, thresh, knee);
        float3 g2 = soft_threshold((d + e + g + h) * 0.25, thresh, knee);
        float3 g3 = soft_threshold((e + f + h + i) * 0.25, thresh, knee);
        float3 g4 = soft_threshold((j + k + l + m) * 0.25, thresh, knee);
        float w0 = karis_weight(g0), w1 = karis_weight(g1), w2 = karis_weight(g2), w3 = karis_weight(g3), w4 = karis_weight(g4);
        out_rgb = (g0 * w0 + g1 * w1 + g2 * w2 + g3 * w3 + g4 * w4) / max(w0 + w1 + w2 + w3 + w4, 1e-5);
    } else {
        out_rgb = e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125;
    }

    dst_tex[gid] = float4(max(out_rgb, float3(0.0, 0.0, 0.0)), 1.0);
}

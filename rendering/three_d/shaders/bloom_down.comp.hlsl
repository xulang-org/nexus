cbuffer BloomDownParams : register(b0, space2) {
    float4 dims;
    float4 cfg;
};

Texture2D<float4> src_tex : register(t0, space0);
SamplerState src_sampler : register(s0, space0);
RWTexture2D<float4> dst_tex : register(u0, space1);

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint dw = uint(dims.z), dh = uint(dims.w);
    if (gid.x >= dw || gid.y >= dh) return;

    float2 uv = (float2(gid) + 0.5) / float2(dims.z, dims.w);
    float2 dx = float2(1.0 / dims.x, 0.0);
    float2 dy = float2(0.0, 1.0 / dims.y);

    float3 a = src_tex.SampleLevel(src_sampler, uv - dx - dy, 0.0).rgb;
    float3 b = src_tex.SampleLevel(src_sampler, uv + dx - dy, 0.0).rgb;
    float3 c = src_tex.SampleLevel(src_sampler, uv - dx + dy, 0.0).rgb;
    float3 d = src_tex.SampleLevel(src_sampler, uv + dx + dy, 0.0).rgb;
    float3 e = src_tex.SampleLevel(src_sampler, uv, 0.0).rgb;
    float3 avg = (a + b + c + d) * 0.125 + e * 0.5;

    if (cfg.z > 0.5) {
        float lum = max(avg.r, max(avg.g, avg.b));
        float thresh = cfg.x;
        float knee = max(cfg.y, 1e-4);
        float soft = clamp(lum - thresh + knee, 0.0, 2.0 * knee);
        soft = (soft * soft) / (4.0 * knee);
        float contrib = max(soft, lum - thresh) / max(lum, 1e-5);
        avg *= max(contrib, 0.0);
    }

    dst_tex[gid] = float4(max(avg, float3(0.0, 0.0, 0.0)), 1.0);
}

cbuffer TaaParams : register(b0, space2) {
    column_major float4x4 reproj;
    float4 info;
};

Texture2D<float4> curr_hdr : register(t0, space0);
Texture2D<float4> prev_history : register(t1, space0);
Texture2D<float> src_depth : register(t2, space0);
SamplerState curr_sampler : register(s0, space0);
SamplerState prev_sampler : register(s1, space0);
SamplerState depth_sampler : register(s2, space0);
RWTexture2D<float4> dst_history : register(u0, space1);

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint w = uint(info.x), h = uint(info.y);
    if (gid.x >= w || gid.y >= h) return;

    float2 inv_res = float2(1.0 / info.x, 1.0 / info.y);
    float2 uv = (float2(gid) + 0.5) * inv_res;
    float3 curr = curr_hdr.SampleLevel(curr_sampler, uv, 0.0).rgb;

    if (info.w < 0.5) {
        dst_history[gid] = float4(curr, 1.0);
        return;
    }

    float d = src_depth.SampleLevel(depth_sampler, uv, 0.0).r;
    float4 clip_curr = float4(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0, d, 1.0);
    float4 clip_prev = mul(reproj, clip_curr);
    if (clip_prev.w <= 1e-5) {
        dst_history[gid] = float4(curr, 1.0);
        return;
    }
    float2 ndc_prev = clip_prev.xy / clip_prev.w;
    float2 prev_uv = float2(ndc_prev.x * 0.5 + 0.5, 0.5 - ndc_prev.y * 0.5);
    if (prev_uv.x <= 0.0 || prev_uv.x >= 1.0 || prev_uv.y <= 0.0 || prev_uv.y >= 1.0) {
        dst_history[gid] = float4(curr, 1.0);
        return;
    }

    float3 box_min = curr, box_max = curr;
    for (int dy = -1; dy <= 1; ++dy) {
        for (int dx = -1; dx <= 1; ++dx) {
            float2 suv = clamp(uv + float2(float(dx), float(dy)) * inv_res, float2(0.0001, 0.0001), float2(0.9999, 0.9999));
            float3 n = curr_hdr.SampleLevel(curr_sampler, suv, 0.0).rgb;
            box_min = min(box_min, n);
            box_max = max(box_max, n);
        }
    }

    float3 hist = clamp(prev_history.SampleLevel(prev_sampler, prev_uv, 0.0).rgb, box_min, box_max);
    float3 resolved = lerp(curr, hist, clamp(info.z, 0.0, 0.95));
    dst_history[gid] = float4(resolved, 1.0);
}

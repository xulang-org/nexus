cbuffer GtaoParams : register(b0, space2) {
    column_major float4x4 inv_proj;
    column_major float4x4 view;
    float4 info;
};

Texture2D<float> src_depth : register(t0, space0);
Texture2D<float4> src_normal : register(t1, space0);
SamplerState depth_sampler : register(s0, space0);
SamplerState normal_sampler : register(s1, space0);
RWTexture2D<float4> dst_ao : register(u0, space1);

float3 reconstruct_view(float4x4 m, float2 uv, float depth) {
    float ndc_x = uv.x * 2.0 - 1.0;
    float ndc_y = 1.0 - uv.y * 2.0;
    float4 v = mul(m, float4(ndc_x, ndc_y, depth, 1.0));
    return v.xyz / max(v.w, 1e-6);
}

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint w = uint(info.x), h = uint(info.y);
    if (gid.x >= w || gid.y >= h) return;

    float2 inv_res = float2(1.0 / info.x, 1.0 / info.y);
    float2 uv = (float2(gid) + 0.5) * inv_res;
    float d = src_depth.SampleLevel(depth_sampler, uv, 0.0).r;
    if (d <= 1e-6) {
        dst_ao[gid] = float4(1.0, 0.0, 0.0, 1.0);
        return;
    }

    float3 P = reconstruct_view(inv_proj, uv, d);
    float3 nw = src_normal.SampleLevel(normal_sampler, uv, 0.0).xyz;
    float nlen = length(nw);
    if (nlen < 1e-4) {
        dst_ao[gid] = float4(1.0, 0.0, 0.0, 1.0);
        return;
    }
    float3 N = normalize(mul(view, float4(nw / nlen, 0.0)).xyz);
    float3 V = normalize(-P);

    float radius = info.z;
    float bias = info.w;
    float dist_view = max(-P.z, 0.1);
    float screen_radius = clamp((radius / dist_view) * 0.45, inv_res.x * 2.0, 0.18);

    float rot = frac(sin(dot(float2(gid), float2(12.9898, 78.233))) * 43758.5453) * 6.283185307;

    float occ_sum = 0.0;
    const int DIRS = 8;
    const int STEPS = 3;
    for (int d_i = 0; d_i < DIRS; ++d_i) {
        float ang = rot + float(d_i) * (6.283185307 / float(DIRS));
        float2 dir_uv = float2(cos(ang), sin(ang));
        float max_h = 0.0;
        for (int s_i = 1; s_i <= STEPS; ++s_i) {
            float t = float(s_i) / float(STEPS);
            float2 suv = uv + dir_uv * (screen_radius * t * t);
            if (suv.x <= 0.0 || suv.x >= 1.0 || suv.y <= 0.0 || suv.y >= 1.0) break;
            float sd = src_depth.SampleLevel(depth_sampler, suv, 0.0).r;
            if (sd <= 1e-6) continue;
            float3 Q = reconstruct_view(inv_proj, suv, sd);
            float3 diff = Q - P;
            float dlen = length(diff);
            if (dlen < 1e-4 || dlen > radius) continue;
            float horizon = dot(diff / dlen, N) - bias;
            float falloff = clamp(1.0 - (dlen / radius) * (dlen / radius), 0.0, 1.0);
            max_h = max(max_h, horizon * falloff);
        }
        occ_sum += clamp(max_h, 0.0, 1.0);
    }

    float ao = clamp(1.0 - (occ_sum / float(DIRS)) * (1.0 + 0.35 * max(dot(N, V), 0.0)), 0.0, 1.0);
    dst_ao[gid] = float4(ao, 0.0, 0.0, 1.0);
}

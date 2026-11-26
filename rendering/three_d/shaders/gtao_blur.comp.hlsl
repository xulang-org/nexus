cbuffer BlurParams : register(b0, space2) {
    float4 info;
};

Texture2D<float> src_ao : register(t0, space0);
Texture2D<float> src_depth : register(t1, space0);
SamplerState ao_sampler : register(s0, space0);
SamplerState depth_sampler : register(s1, space0);
RWTexture2D<float4> dst_ao : register(u0, space1);

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint w = uint(info.x), h = uint(info.y);
    if (gid.x >= w || gid.y >= h) return;

    float2 inv_res = float2(1.0 / info.x, 1.0 / info.y);
    float2 uv = (float2(gid) + 0.5) * inv_res;
    float center_d = src_depth.SampleLevel(depth_sampler, uv, 0.0).r;
    float center_ao = src_ao.SampleLevel(ao_sampler, uv, 0.0).r;
    if (center_d <= 1e-6) {
        dst_ao[gid] = float4(1.0, 0.0, 0.0, 1.0);
        return;
    }

    float sum_ao = 0.0, sum_w = 0.0;
    for (int dy = -2; dy <= 2; ++dy) {
        for (int dx = -2; dx <= 2; ++dx) {
            float2 suv = clamp(uv + float2(float(dx), float(dy)) * inv_res, float2(0.0001, 0.0001), float2(0.9999, 0.9999));
            float sd = src_depth.SampleLevel(depth_sampler, suv, 0.0).r;
            float sao = src_ao.SampleLevel(ao_sampler, suv, 0.0).r;
            float depth_diff = abs(sd - center_d) * 180.0;
            float spatial = exp(-float(dx * dx + dy * dy) * 0.2);
            float weight = spatial * exp(-depth_diff * depth_diff);
            sum_ao += sao * weight;
            sum_w += weight;
        }
    }
    float out_ao = (sum_w > 1e-5) ? (sum_ao / sum_w) : center_ao;
    dst_ao[gid] = float4(clamp(out_ao, 0.0, 1.0), 0.0, 0.0, 1.0);
}

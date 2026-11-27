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

float karis_luma(float3 c) {
    return max(dot(c, float3(0.2126, 0.7152, 0.0722)), 0.0);
}

float3 karis_tone(float3 c) {
    float3 sc = max(c, float3(0.0, 0.0, 0.0));
    return sc / (1.0 + karis_luma(sc));
}

float3 karis_inv(float3 c) {
    float3 sc = max(c, float3(0.0, 0.0, 0.0));
    return sc / max(1.0 - karis_luma(sc), 1e-4);
}

float3 rgb_to_ycocg(float3 c) {
    return float3(
        dot(c, float3(0.25, 0.50, 0.25)),
        dot(c, float3(0.50, 0.00, -0.50)),
        dot(c, float3(-0.25, 0.50, -0.25))
    );
}

float3 ycocg_to_rgb(float3 ycc) {
    return float3(
        ycc.x + ycc.y - ycc.z,
        ycc.x + ycc.z,
        ycc.x - ycc.y - ycc.z
    );
}

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

    float best_d = src_depth.SampleLevel(depth_sampler, uv, 0.0).r;
    float3 m1 = float3(0.0, 0.0, 0.0);
    float3 m2 = float3(0.0, 0.0, 0.0);
    float3 min_c = rgb_to_ycocg(karis_tone(curr));
    float3 max_c = min_c;
    for (int dy = -1; dy <= 1; ++dy) {
        for (int dx = -1; dx <= 1; ++dx) {
            float2 suv = clamp(uv + float2(float(dx), float(dy)) * inv_res, float2(0.0001, 0.0001), float2(0.9999, 0.9999));
            float sd = src_depth.SampleLevel(depth_sampler, suv, 0.0).r;
            best_d = max(best_d, sd);
            float3 ycc = rgb_to_ycocg(karis_tone(curr_hdr.SampleLevel(curr_sampler, suv, 0.0).rgb));
            m1 += ycc;
            m2 += ycc * ycc;
            min_c = min(min_c, ycc);
            max_c = max(max_c, ycc);
        }
    }

    float4 clip_curr = float4(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0, best_d, 1.0);
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

    float3 mean = m1 / 9.0;
    float3 sigma = sqrt(max(m2 / 9.0 - mean * mean, float3(0.0, 0.0, 0.0)));
    float3 aabb_min = max(min_c, mean - 1.25 * sigma);
    float3 aabb_max = min(max_c, mean + 1.25 * sigma);

    float3 curr_ycc = rgb_to_ycocg(karis_tone(curr));
    float3 hist_ycc = clamp(rgb_to_ycocg(karis_tone(prev_history.SampleLevel(prev_sampler, prev_uv, 0.0).rgb)), aabb_min, aabb_max);

    float motion_px = length((prev_uv - uv) * info.xy);
    float vel_scale = 1.0 / (1.0 + motion_px * 0.15);
    float alpha = clamp(info.z * vel_scale, 0.0, 0.95);
    float3 resolved = karis_inv(ycocg_to_rgb(lerp(curr_ycc, hist_ycc, alpha)));
    dst_history[gid] = float4(max(resolved, float3(0.0, 0.0, 0.0)), 1.0);
}

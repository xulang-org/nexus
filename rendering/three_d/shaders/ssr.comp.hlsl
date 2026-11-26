cbuffer SsrParams : register(b0, space2) {
    column_major float4x4 view;
    column_major float4x4 proj;
    column_major float4x4 inv_proj;
    float4 info;
    float4 zinfo;
};

Texture2D<float4> src_color : register(t0, space0);
Texture2D<float4> src_normal : register(t1, space0);
Texture2D<float> src_depth : register(t2, space0);
Texture2D<float> hiz0 : register(t3, space0);

SamplerState color_sampler : register(s0, space0);
SamplerState normal_sampler : register(s1, space0);
SamplerState depth_sampler : register(s2, space0);
SamplerState hiz_sampler : register(s3, space0);

RWTexture2D<float4> dst_ssr : register(u0, space1);

float3 reconstruct_view(float4x4 m, float2 uv, float depth) {
    float ndc_x = uv.x * 2.0 - 1.0;
    float ndc_y = 1.0 - uv.y * 2.0;
    float4 v = mul(m, float4(ndc_x, ndc_y, depth, 1.0));
    return v.xyz / max(v.w, 1e-6);
}

float3 project_uv_z(float4x4 p, float3 vp) {
    float4 c = mul(p, float4(vp, 1.0));
    if (c.w <= 1e-5) return float3(-1.0, -1.0, -1.0);
    float3 ndc = c.xyz / c.w;
    return float3(ndc.x * 0.5 + 0.5, 0.5 - ndc.y * 0.5, ndc.z);
}

float view_depth_from_ndc(float4x4 m, float2 uv, float depth) {
    return -reconstruct_view(m, uv, depth).z;
}

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint w = uint(info.x), h = uint(info.y);
    if (gid.x >= w || gid.y >= h) return;

    if (zinfo.w < 0.5) {
        dst_ssr[gid] = float4(0.0, 0.0, 0.0, 0.0);
        return;
    }

    float2 inv_res = float2(1.0 / info.x, 1.0 / info.y);
    float2 uv = (float2(gid) + 0.5) * inv_res;
    float d = src_depth.SampleLevel(depth_sampler, uv, 0.0).r;
    float4 nr = src_normal.SampleLevel(normal_sampler, uv, 0.0);
    float roughness = nr.w, nlen = length(nr.xyz);
    if (d <= 1e-6 || nlen < 1e-4 || roughness > info.z) {
        dst_ssr[gid] = float4(0.0, 0.0, 0.0, 0.0);
        return;
    }

    float3 P = reconstruct_view(inv_proj, uv, d);
    float3 N = normalize(mul(view, float4(nr.xyz / nlen, 0.0)).xyz);
    float3 V = normalize(-P);
    float3 R = reflect(-V, N);
    if (R.z > 0.3) {
        dst_ssr[gid] = float4(0.0, 0.0, 0.0, 0.0);
        return;
    }

    float max_dist = info.w, thickness = zinfo.z;
    const int STEPS = 32;
    float step_len = max_dist / float(STEPS);
    bool hit = false;
    float2 hit_uv = float2(0.0, 0.0);
    float prev_t = step_len * 0.5, hit_t = prev_t;

    for (int i = 1; i <= STEPS; ++i) {
        float t = step_len * float(i);
        float3 sample_vp = P + R * t;
        if (-sample_vp.z <= zinfo.x || -sample_vp.z >= zinfo.y) break;
        float3 uvd = project_uv_z(proj, sample_vp);
        if (uvd.x <= 0.0 || uvd.x >= 1.0 || uvd.y <= 0.0 || uvd.y >= 1.0) break;

        float coarse_z = hiz0.SampleLevel(hiz_sampler, uvd.xy, 0.0).r;
        if (coarse_z <= 1e-6) { prev_t = t; continue; }
        float fine_z = src_depth.SampleLevel(depth_sampler, uvd.xy, 0.0).r;
        if (fine_z <= 1e-6) { prev_t = t; continue; }
        float ray_dist = -sample_vp.z;
        float surf_dist = view_depth_from_ndc(inv_proj, uvd.xy, fine_z);
        float delta = ray_dist - surf_dist;
        if (delta > 0.0 && delta < thickness) { hit = true; hit_uv = uvd.xy; hit_t = t; break; }
        prev_t = t;
    }

    if (!hit) { dst_ssr[gid] = float4(0.0, 0.0, 0.0, 0.0); return; }

    float lo = prev_t, hi = hit_t;
    for (int r = 0; r < 4; ++r) {
        float mid = 0.5 * (lo + hi);
        float3 vp = P + R * mid;
        float3 uvd = project_uv_z(proj, vp);
        if (uvd.x > 0.0 && uvd.x < 1.0 && uvd.y > 0.0 && uvd.y < 1.0) {
            float fz = src_depth.SampleLevel(depth_sampler, uvd.xy, 0.0).r;
            float sd = view_depth_from_ndc(inv_proj, uvd.xy, fz);
            if ((-vp.z) - sd > 0.0) { hi = mid; hit_uv = uvd.xy; }
            else lo = mid;
        }
    }

    float3 refl_color = src_color.SampleLevel(color_sampler, hit_uv, 0.0).rgb;
    float edge_x = min(hit_uv.x, 1.0 - hit_uv.x), edge_y = min(hit_uv.y, 1.0 - hit_uv.y);
    float edge_fade = clamp(min(edge_x, edge_y) * 8.0, 0.0, 1.0);
    float rough_fade = clamp(1.0 - (roughness / max(info.z, 1e-4)), 0.0, 1.0);
    float nv = clamp(dot(N, V), 0.0, 1.0);
    float fresnel = 0.04 + 0.96 * pow(1.0 - nv, 4.0);
    float weight = clamp(edge_fade * rough_fade * fresnel, 0.0, 1.0);
    dst_ssr[gid] = float4(refl_color, weight);
}

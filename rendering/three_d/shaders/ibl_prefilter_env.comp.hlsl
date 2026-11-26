cbuffer EnvPrefilterUniform : register(b0, space2) {
    float4 size_roughness;
    float4 sky_top;
    float4 sky_horizon;
    float4 ground_color;
    float4 sun_dir;
    float4 sun_radiance;
};

RWTexture2D<float4> out_env : register(u0, space1);

float radical_inverse_vdc(uint bits) {
    bits = (bits << 16u) | (bits >> 16u);
    bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
    bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
    bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
    bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
    return float(bits) * 2.3283064365386963e-10;
}

float2 hammersley(uint i, uint n) {
    return float2(float(i) / float(n), radical_inverse_vdc(i));
}

float3 importance_sample_ggx(float2 xi, float3 n, float roughness) {
    float a = max(roughness, 0.015);
    a = a * a;
    float phi = 2.0 * 3.14159265359 * xi.x;
    float cos_theta = sqrt((1.0 - xi.y) / (1.0 + (a * a - 1.0) * xi.y));
    float sin_theta = sqrt(max(0.0, 1.0 - cos_theta * cos_theta));
    float3 h = float3(cos(phi) * sin_theta, sin(phi) * sin_theta, cos_theta);
    float3 up = abs(n.y) < 0.999 ? float3(0.0, 1.0, 0.0) : float3(1.0, 0.0, 0.0);
    float3 tangent = normalize(cross(up, n));
    float3 bitangent = cross(n, tangent);
    return normalize(tangent * h.x + bitangent * h.y + n * h.z);
}

float3 eval_env_radiance(float3 d) {
    float h_t = clamp(d.y, 0.0, 1.0);
    float g_t = clamp(-d.y, 0.0, 1.0);
    float3 sky = lerp(sky_horizon.rgb, sky_top.rgb, pow(h_t, 0.65));
    float3 col = (d.y >= 0.0) ? sky : lerp(sky_horizon.rgb * 0.75, ground_color.rgb, pow(g_t, 0.55));
    float sun_cos = max(dot(normalize(d), normalize(sun_dir.xyz)), 0.0);
    float disk = pow(sun_cos, 192.0) * 1.5 + pow(sun_cos, 12.0) * 0.15;
    return max(col + sun_radiance.rgb * disk, float3(0.0, 0.0, 0.0));
}

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint w = uint(size_roughness.x), h = uint(size_roughness.y);
    if (gid.x >= w || gid.y >= h) return;

    float2 uv = (float2(gid) + 0.5) / float2(float(w), float(h));
    float phi = (uv.x - 0.5) * 2.0 * 3.14159265359;
    float theta = uv.y * 3.14159265359;
    float sin_t = sin(theta);
    float3 r_vec = normalize(float3(sin_t * cos(phi), cos(theta), sin_t * sin(phi)));

    float roughness = clamp(size_roughness.z, 0.0, 1.0);
    if (roughness <= 0.01) {
        out_env[gid] = float4(eval_env_radiance(r_vec), 1.0);
        return;
    }

    uint samples = max(uint(size_roughness.w), 1u);
    float3 n = r_vec, v = r_vec, prefiltered = float3(0.0, 0.0, 0.0);
    float total_weight = 0.0;
    for (uint i = 0u; i < samples; ++i) {
        float2 xi = hammersley(i, samples);
        float3 hvec = importance_sample_ggx(xi, n, roughness);
        float3 l = normalize(2.0 * dot(v, hvec) * hvec - v);
        float nl = max(dot(n, l), 0.0);
        if (nl > 0.0) {
            prefiltered += eval_env_radiance(l) * nl;
            total_weight += nl;
        }
    }
    prefiltered = prefiltered / max(total_weight, 1e-4);
    out_env[gid] = float4(prefiltered, 1.0);
}

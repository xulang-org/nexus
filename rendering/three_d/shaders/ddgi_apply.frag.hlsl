struct ProbeShGpu { float4 dc; float4 px; float4 py; float4 pz; };

cbuffer DdgiApplyUniform : register(b0, space3) {
    column_major float4x4 inv_vp; float4 eye_strength; float4 origin_nx; float4 spacing_ny;
    float4 dims_flags; float4 tint_visres; float4 bias_misc; float4 pad0; float4 pad1;
};

Texture2D<float> scene_depth_tex : register(t0, space2);
Texture2D<float4> normal_rough_tex : register(t1, space2);
SamplerState depth_samp : register(s0, space2);
SamplerState norm_samp : register(s1, space2);
StructuredBuffer<ProbeShGpu> probes : register(t2, space2);
StructuredBuffer<float2> probe_vis : register(t3, space2);

struct Input {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

float2 sign_not_zero(float2 v) {
    return float2((v.x >= 0.0) ? 1.0 : -1.0, (v.y >= 0.0) ? 1.0 : -1.0);
}

float2 oct_encode(float3 v) {
    float l1 = abs(v.x) + abs(v.y) + abs(v.z);
    float2 p = v.xy / max(l1, 1e-6);
    if (v.z < 0.0) p = (1.0 - abs(p.yx)) * sign_not_zero(p);
    return p * 0.5 + 0.5;
}

float2 sample_oct_vis(uint probe_idx, uint vis_res, float3 dir) {
    uint texels = vis_res * vis_res, base = probe_idx * texels;
    float2 euv = clamp(oct_encode(dir), float2(0.0, 0.0), float2(1.0, 1.0));
    float fx = clamp(euv.x * float(vis_res) - 0.5, 0.0, float(vis_res - 1u));
    float fy = clamp(euv.y * float(vis_res) - 0.5, 0.0, float(vis_res - 1u));
    uint x0 = uint(floor(fx)), y0 = uint(floor(fy)), x1 = min(x0 + 1u, vis_res - 1u), y1 = min(y0 + 1u, vis_res - 1u);
    float tx = fx - float(x0), ty = fy - float(y0);
    float2 m00 = probe_vis[base + y0 * vis_res + x0], m10 = probe_vis[base + y0 * vis_res + x1];
    float2 m01 = probe_vis[base + y1 * vis_res + x0], m11 = probe_vis[base + y1 * vis_res + x1];
    return lerp(lerp(m00, m10, tx), lerp(m01, m11, tx), ty);
}

float4 main(Input input) : SV_Target0 {
    float d = scene_depth_tex.SampleLevel(depth_samp, input.uv, 0.0).r;
    float4 nr = normal_rough_tex.SampleLevel(norm_samp, input.uv, 0.0);
    if (d <= 1e-6 || dot(nr.xyz, nr.xyz) < 0.01) return float4(0.0, 0.0, 0.0, 0.0);

    float ndc_x = input.uv.x * 2.0 - 1.0, ndc_y = 1.0 - input.uv.y * 2.0;
    float4 wp4 = mul(inv_vp, float4(ndc_x, ndc_y, d, 1.0));
    float3 world_pos = wp4.xyz / max(wp4.w, 1e-6);
    float3 N = normalize(nr.xyz), V = normalize(eye_strength.xyz - world_pos);
    float3 biased_pos = world_pos + N * dims_flags.z + V * dims_flags.w;

    int nx = int(origin_nx.w), ny = int(spacing_ny.w), nz = int(dims_flags.x);
    if (nx <= 0 || ny <= 0 || nz <= 0) return float4(0.0, 0.0, 0.0, 0.0);

    float3 rel = (biased_pos - origin_nx.xyz) / max(spacing_ny.xyz, float3(1e-4, 1e-4, 1e-4));
    float fx = clamp(rel.x, 0.0, float(max(nx - 1, 0))), fy = clamp(rel.y, 0.0, float(max(ny - 1, 0))), fz = clamp(rel.z, 0.0, float(max(nz - 1, 0)));
    int x0 = min(int(floor(fx)), max(nx - 1, 0)), y0 = min(int(floor(fy)), max(ny - 1, 0)), z0 = min(int(floor(fz)), max(nz - 1, 0));
    int x1 = min(x0 + 1, max(nx - 1, 0)), y1 = min(y0 + 1, max(ny - 1, 0)), z1 = min(z0 + 1, max(nz - 1, 0));
    float tx = fx - float(x0), ty = fy - float(y0), tz = fz - float(z0);

    bool use_chebyshev = (dims_flags.y > 0.5);
    uint vis_res = max(uint(tint_visres.w), 1u);
    float min_cheb = clamp(bias_misc.x, 0.0, 0.2);

    float3 sum_irr = float3(0.0, 0.0, 0.0);
    float sum_w = 0.0;
    for (int dz = 0; dz < 2; ++dz) {
        int iz = (dz == 0) ? z0 : z1; float wz = (dz == 0) ? (1.0 - tz) : tz;
        for (int dy = 0; dy < 2; ++dy) {
            int iy = (dy == 0) ? y0 : y1; float wy = (dy == 0) ? (1.0 - ty) : ty;
            for (int dx = 0; dx < 2; ++dx) {
                int ix = (dx == 0) ? x0 : x1; float wx = (dx == 0) ? (1.0 - tx) : tx;
                uint pid = uint((iz * ny + iy) * nx + ix);
                ProbeShGpu sh = probes[pid];
                float w_tri = wx * wy * wz, w = w_tri;
                if (use_chebyshev) {
                    if (sh.dc.w < 0.5) continue;
                    float3 probe_pos = origin_nx.xyz + float3(float(ix), float(iy), float(iz)) * spacing_ny.xyz;
                    float3 to_probe = probe_pos - world_pos;
                    float3 dir_to_probe = to_probe / max(length(to_probe), 1e-5);
                    float wrap = clamp((dot(dir_to_probe, N) + 1.0) * 0.5, 0.0, 1.0), w_bf = wrap * wrap + 0.05;
                    float3 to_bias = biased_pos - probe_pos;
                    float dist = length(to_bias);
                    float2 moments = sample_oct_vis(pid, vis_res, to_bias / max(dist, 1e-5));
                    float cheb = 1.0;
                    if (dist > moments.x) {
                        float var = max(abs(moments.y - moments.x * moments.x), 1e-4), diff = dist - moments.x;
                        cheb = max(pow(var / (var + diff * diff), 3.0), min_cheb);
                    }
                    w = w_tri * w_bf * cheb;
                }
                sum_irr += max(sh.dc.xyz + sh.px.xyz * N.x + sh.py.xyz * N.y + sh.pz.xyz * N.z, float3(0.0, 0.0, 0.0)) * w;
                sum_w += w;
            }
        }
    }
    float3 final_irr = (sum_w > 1e-6) ? (sum_irr / sum_w) : float3(0.0, 0.0, 0.0);
    return float4(max(final_irr * tint_visres.rgb * eye_strength.w, float3(0.0, 0.0, 0.0)), 0.0);
}

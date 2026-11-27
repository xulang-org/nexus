#version 450

struct ProbeShGpu { vec4 dc; vec4 px; vec4 py; vec4 pz; };

layout(location = 0) in vec2 uv;
layout(set = 2, binding = 0) uniform sampler2D scene_depth_tex;
layout(set = 2, binding = 1) uniform sampler2D normal_rough_tex;
layout(set = 2, binding = 2, std430) readonly buffer ProbesBuf { ProbeShGpu probes[]; };
layout(set = 2, binding = 3, std430) readonly buffer VisBuf { vec2 probe_vis[]; };

layout(set = 3, binding = 0, std140) uniform DdgiApplyUniform {
    mat4 inv_vp; vec4 eye_strength; vec4 origin_nx; vec4 spacing_ny;
    vec4 dims_flags; vec4 tint_visres; vec4 bias_misc; vec4 pad0; vec4 pad1;
} u;

layout(location = 0) out vec4 output_color;

vec2 sign_not_zero(vec2 v) {
    return vec2((v.x >= 0.0) ? 1.0 : -1.0, (v.y >= 0.0) ? 1.0 : -1.0);
}

vec2 oct_encode(vec3 v) {
    float l1 = abs(v.x) + abs(v.y) + abs(v.z);
    vec2 p = v.xy / max(l1, 1e-6);
    if (v.z < 0.0) p = (1.0 - abs(p.yx)) * sign_not_zero(p);
    return p * 0.5 + 0.5;
}

vec2 sample_oct_vis(uint probe_idx, uint vis_res, vec3 dir) {
    uint texels = vis_res * vis_res, base = probe_idx * texels;
    vec2 euv = clamp(oct_encode(dir), vec2(0.0), vec2(1.0));
    float fx = clamp(euv.x * float(vis_res) - 0.5, 0.0, float(vis_res - 1u));
    float fy = clamp(euv.y * float(vis_res) - 0.5, 0.0, float(vis_res - 1u));
    uint x0 = uint(floor(fx)), y0 = uint(floor(fy)), x1 = min(x0 + 1u, vis_res - 1u), y1 = min(y0 + 1u, vis_res - 1u);
    float tx = fx - float(x0), ty = fy - float(y0);
    vec2 m00 = probe_vis[base + y0 * vis_res + x0], m10 = probe_vis[base + y0 * vis_res + x1];
    vec2 m01 = probe_vis[base + y1 * vis_res + x0], m11 = probe_vis[base + y1 * vis_res + x1];
    return mix(mix(m00, m10, tx), mix(m01, m11, tx), ty);
}

void main() {
    float d = textureLod(scene_depth_tex, uv, 0.0).r;
    vec4 nr = textureLod(normal_rough_tex, uv, 0.0);
    if (d <= 1e-6 || dot(nr.xyz, nr.xyz) < 0.01) { output_color = vec4(0.0); return; }

    float ndc_x = uv.x * 2.0 - 1.0, ndc_y = 1.0 - uv.y * 2.0;
    vec4 wp4 = u.inv_vp * vec4(ndc_x, ndc_y, d, 1.0);
    vec3 world_pos = wp4.xyz / max(wp4.w, 1e-6);
    vec3 N = normalize(nr.xyz), V = normalize(u.eye_strength.xyz - world_pos);
    vec3 biased_pos = world_pos + N * u.dims_flags.z + V * u.dims_flags.w;

    int nx = int(u.origin_nx.w), ny = int(u.spacing_ny.w), nz = int(u.dims_flags.x);
    if (nx <= 0 || ny <= 0 || nz <= 0) { output_color = vec4(0.0); return; }

    vec3 rel = (biased_pos - u.origin_nx.xyz) / max(u.spacing_ny.xyz, vec3(1e-4));
    float fx = clamp(rel.x, 0.0, float(max(nx - 1, 0))), fy = clamp(rel.y, 0.0, float(max(ny - 1, 0))), fz = clamp(rel.z, 0.0, float(max(nz - 1, 0)));
    int x0 = min(int(floor(fx)), max(nx - 1, 0)), y0 = min(int(floor(fy)), max(ny - 1, 0)), z0 = min(int(floor(fz)), max(nz - 1, 0));
    int x1 = min(x0 + 1, max(nx - 1, 0)), y1 = min(y0 + 1, max(ny - 1, 0)), z1 = min(z0 + 1, max(nz - 1, 0));
    float tx = fx - float(x0), ty = fy - float(y0), tz = fz - float(z0);

    bool use_chebyshev = (u.dims_flags.y > 0.5);
    uint vis_res = max(uint(u.tint_visres.w), 1u);
    float min_cheb = clamp(u.bias_misc.x, 0.0, 0.2);

    vec3 sum_irr = vec3(0.0);
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
                    vec3 probe_pos = u.origin_nx.xyz + vec3(float(ix), float(iy), float(iz)) * u.spacing_ny.xyz;
                    vec3 to_probe = probe_pos - world_pos;
                    vec3 dir_to_probe = to_probe / max(length(to_probe), 1e-5);
                    float wrap = clamp((dot(dir_to_probe, N) + 1.0) * 0.5, 0.0, 1.0), w_bf = wrap * wrap + 0.05;
                    vec3 to_bias = biased_pos - probe_pos;
                    float dist = length(to_bias);
                    vec2 moments = sample_oct_vis(pid, vis_res, to_bias / max(dist, 1e-5));
                    float cheb = 1.0;
                    if (dist > moments.x) {
                        float var = max(abs(moments.y - moments.x * moments.x), 1e-4), diff = dist - moments.x;
                        cheb = max(pow(var / (var + diff * diff), 3.0), min_cheb);
                    }
                    w = w_tri * w_bf * cheb;
                }
                sum_irr += max(sh.dc.xyz + sh.px.xyz * N.x + sh.py.xyz * N.y + sh.pz.xyz * N.z, vec3(0.0)) * w;
                sum_w += w;
            }
        }
    }
    vec3 final_irr = (sum_w > 1e-6) ? (sum_irr / sum_w) : vec3(0.0);
    output_color = vec4(max(final_irr * u.tint_visres.rgb * u.eye_strength.w, vec3(0.0)), 0.0);
}

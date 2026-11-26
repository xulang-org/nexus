struct LightGpu { float4 position_kind; float4 direction_range; float4 radiance_inner; float4 cone; };
struct ProbeShGpu { float4 dc; float4 px; float4 py; float4 pz; };
struct BvhNodeGpu { float4 bmin_left; float4 bmax_right; };
struct RtTriGpu { float4 v0_mat; float4 e1_pad; float4 e2_pad; float4 n_ds; };
struct RtMatGpu { float4 albedo_rough; float4 emission_metal; };

cbuffer DdgiTraceUniform : register(b0, space2) {
    float4 origin_nx; float4 spacing_ny; float4 dims_rays; float4 counts;
    float4 sky_color_dir; float4 ground_color_emi; float4 rot_row0; float4 rot_row1;
    float4 rot_row2; float4 ambient_pad; float4 pad0; float4 pad1;
};

StructuredBuffer<BvhNodeGpu> bvh_nodes : register(t0, space0);
StructuredBuffer<RtTriGpu> rt_tris : register(t1, space0);
StructuredBuffer<RtMatGpu> rt_mats : register(t2, space0);
StructuredBuffer<LightGpu> lights : register(t3, space0);
StructuredBuffer<ProbeShGpu> prev_probes : register(t4, space0);
RWStructuredBuffer<float4> ray_results : register(u0, space1);

float3 fibonacci_dir(uint ray_idx, uint ray_count, float3 r0, float3 r1, float3 r2) {
    float n = max(float(ray_count), 1.0), fi = float(ray_idx) + 0.5, phi = 2.399963229728653 * float(ray_idx);
    float cos_theta = 1.0 - 2.0 * fi / n, sin_theta = sqrt(max(0.0, 1.0 - cos_theta * cos_theta));
    float3 d = float3(cos(phi) * sin_theta, cos_theta, sin(phi) * sin_theta);
    return normalize(float3(dot(r0, d), dot(r1, d), dot(r2, d)));
}

bool intersect_aabb(float3 ro, float3 inv_rd, float3 bmin, float3 bmax, float t_max, out float out_tmin) {
    float3 t0 = (bmin - ro) * inv_rd, t1 = (bmax - ro) * inv_rd;
    float3 tsmaller = min(t0, t1), tbigger = max(t0, t1);
    float tmin = max(0.0, max(tsmaller.x, max(tsmaller.y, tsmaller.z)));
    float tmax = min(t_max, min(tbigger.x, min(tbigger.y, tbigger.z)));
    out_tmin = tmin;
    return tmin <= tmax;
}

bool intersect_tri(float3 ro, float3 rd, RtTriGpu tri, float t_min, float t_max, out float out_t) {
    out_t = t_max;
    float3 v0 = tri.v0_mat.xyz, e1 = tri.e1_pad.xyz, e2 = tri.e2_pad.xyz;
    float3 pvec = cross(rd, e2);
    float det = dot(e1, pvec);
    if (abs(det) < 1e-7) return false;
    float inv_det = 1.0 / det;
    float3 tvec = ro - v0;
    float u_b = dot(tvec, pvec) * inv_det;
    if (u_b < -1e-5 || u_b > 1.00001) return false;
    float3 qvec = cross(tvec, e1);
    float v_b = dot(rd, qvec) * inv_det;
    if (v_b < -1e-5 || (u_b + v_b) > 1.00002) return false;
    float t = dot(e2, qvec) * inv_det;
    if (t <= t_min || t >= t_max) return false;
    out_t = t;
    return true;
}

float3 make_inv_dir(float3 rd) {
    return float3(
        abs(rd.x) > 1e-8 ? (1.0 / rd.x) : (rd.x >= 0.0 ? 1e8 : -1e8),
        abs(rd.y) > 1e-8 ? (1.0 / rd.y) : (rd.y >= 0.0 ? 1e8 : -1e8),
        abs(rd.z) > 1e-8 ? (1.0 / rd.z) : (rd.z >= 0.0 ? 1e8 : -1e8)
    );
}

int trace_closest(float3 ro, float3 rd, float max_dist, uint node_count, uint tri_count, out float out_t) {
    out_t = max_dist;
    int best_tri = -1;
    if (node_count == 0u || tri_count == 0u) return -1;
    float3 inv_rd = make_inv_dir(rd);
    uint stack[32];
    int sp = 0;
    stack[sp++] = 0u;
    while (sp > 0) {
        uint ni = stack[--sp];
        if (ni >= node_count) continue;
        BvhNodeGpu node = bvh_nodes[ni];
        float box_t = 0.0;
        if (!intersect_aabb(ro, inv_rd, node.bmin_left.xyz, node.bmax_right.xyz, out_t, box_t)) continue;
        if (node.bmax_right.w > 0.5) {
            uint first = uint(max(0.0, node.bmin_left.w)), end = min(first + uint(node.bmax_right.w), tri_count);
            for (uint ti = first; ti < end; ++ti) {
                float hit_t = 0.0;
                if (intersect_tri(ro, rd, rt_tris[ti], 1e-4, out_t, hit_t)) { out_t = hit_t; best_tri = int(ti); }
            }
        } else {
            uint left = uint(max(0.0, node.bmin_left.w)), right = uint(max(0.0, -node.bmax_right.w));
            float tl = 0.0, tr = 0.0;
            bool hl = (left < node_count) && intersect_aabb(ro, inv_rd, bvh_nodes[left].bmin_left.xyz, bvh_nodes[left].bmax_right.xyz, out_t, tl);
            bool hr = (right < node_count) && intersect_aabb(ro, inv_rd, bvh_nodes[right].bmin_left.xyz, bvh_nodes[right].bmax_right.xyz, out_t, tr);
            if (hl && hr) {
                if (tl < tr) { if (sp < 31) stack[sp++] = right; if (sp < 31) stack[sp++] = left; }
                else { if (sp < 31) stack[sp++] = left; if (sp < 31) stack[sp++] = right; }
            } else if (hl) { if (sp < 31) stack[sp++] = left; }
            else if (hr) { if (sp < 31) stack[sp++] = right; }
        }
    }
    return best_tri;
}

bool trace_any_hit(float3 ro, float3 rd, float t_min, float t_max, uint node_count, uint tri_count) {
    if (node_count == 0u || tri_count == 0u || t_max <= t_min) return false;
    float3 inv_rd = make_inv_dir(rd);
    uint stack[32];
    int sp = 0;
    stack[sp++] = 0u;
    while (sp > 0) {
        uint ni = stack[--sp];
        if (ni >= node_count) continue;
        BvhNodeGpu node = bvh_nodes[ni];
        float box_t = 0.0;
        if (!intersect_aabb(ro, inv_rd, node.bmin_left.xyz, node.bmax_right.xyz, t_max, box_t)) continue;
        if (node.bmax_right.w > 0.5) {
            uint first = uint(max(0.0, node.bmin_left.w)), end = min(first + uint(node.bmax_right.w), tri_count);
            for (uint ti = first; ti < end; ++ti) {
                float hit_t = 0.0;
                if (intersect_tri(ro, rd, rt_tris[ti], t_min, t_max, hit_t)) return true;
            }
        } else {
            uint left = uint(max(0.0, node.bmin_left.w)), right = uint(max(0.0, -node.bmax_right.w));
            if (left < node_count && sp < 31) stack[sp++] = left;
            if (right < node_count && sp < 31) stack[sp++] = right;
        }
    }
    return false;
}

float3 sample_prev_sh_valid(float3 wpos, float3 n) {
    int nx = int(origin_nx.w), ny = int(spacing_ny.w), nz = int(dims_rays.x);
    if (nx <= 0 || ny <= 0 || nz <= 0) return float3(0.0, 0.0, 0.0);
    float3 rel = (wpos - origin_nx.xyz) / max(spacing_ny.xyz, float3(1e-4, 1e-4, 1e-4));
    float fx = clamp(rel.x, 0.0, float(max(nx - 1, 0))), fy = clamp(rel.y, 0.0, float(max(ny - 1, 0))), fz = clamp(rel.z, 0.0, float(max(nz - 1, 0)));
    int x0 = min(int(floor(fx)), max(nx - 1, 0)), y0 = min(int(floor(fy)), max(ny - 1, 0)), z0 = min(int(floor(fz)), max(nz - 1, 0));
    int x1 = min(x0 + 1, max(nx - 1, 0)), y1 = min(y0 + 1, max(ny - 1, 0)), z1 = min(z0 + 1, max(nz - 1, 0));
    float tx = fx - float(x0), ty = fy - float(y0), tz = fz - float(z0);
    float3 sum_irr = float3(0.0, 0.0, 0.0);
    float sum_w = 0.0;
    for (int dz = 0; dz < 2; ++dz) {
        int iz = (dz == 0) ? z0 : z1; float wz = (dz == 0) ? (1.0 - tz) : tz;
        for (int dy = 0; dy < 2; ++dy) {
            int iy = (dy == 0) ? y0 : y1; float wy = (dy == 0) ? (1.0 - ty) : ty;
            for (int dx = 0; dx < 2; ++dx) {
                int ix = (dx == 0) ? x0 : x1; float wx = (dx == 0) ? (1.0 - tx) : tx;
                ProbeShGpu sh = prev_probes[uint((iz * ny + iy) * nx + ix)];
                if (sh.dc.w < 0.5) continue;
                float w = wx * wy * wz;
                sum_irr += max(sh.dc.xyz + sh.px.xyz * n.x + sh.py.xyz * n.y + sh.pz.xyz * n.z, float3(0.0, 0.0, 0.0)) * w;
                sum_w += w;
            }
        }
    }
    return sum_w > 1e-5 ? (sum_irr / sum_w) : float3(0.0, 0.0, 0.0);
}

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint nx = uint(origin_nx.w), ny = uint(spacing_ny.w), nz = uint(dims_rays.x);
    uint rays_per_probe = uint(dims_rays.y), probe_count = nx * ny * nz, total_rays = probe_count * rays_per_probe;
    if (gid >= total_rays) return;

    uint probe_idx = gid / rays_per_probe, ray_idx = gid - probe_idx * rays_per_probe;
    uint slice_xy = nx * ny, iz = probe_idx / slice_xy, rem = probe_idx - iz * slice_xy, iy = rem / nx, ix = rem - iy * nx;
    float3 probe_pos = origin_nx.xyz + float3(float(ix), float(iy), float(iz)) * spacing_ny.xyz;
    float3 rd = fibonacci_dir(ray_idx, rays_per_probe, rot_row0.xyz, rot_row1.xyz, rot_row2.xyz);

    uint node_count = uint(counts.x), tri_count = uint(counts.y);
    float max_dist = dims_rays.w, hit_t = max_dist;
    int hit_tri = trace_closest(probe_pos, rd, max_dist, node_count, tri_count, hit_t);
    if (hit_tri < 0) {
        float t_sky = clamp(rd.y * 0.5 + 0.5, 0.0, 1.0);
        ray_results[gid] = float4(max(lerp(ground_color_emi.rgb, sky_color_dir.rgb, t_sky), float3(0.0, 0.0, 0.0)), max_dist);
        return;
    }

    RtTriGpu tri = rt_tris[uint(hit_tri)];
    float3 n = tri.n_ds.xyz;
    if (dot(rd, n) > 0.0) {
        if (tri.n_ds.w < 0.5) { ray_results[gid] = float4(0.0, 0.0, 0.0, -hit_t); return; }
        n = -n;
    }

    RtMatGpu mat = rt_mats[uint(max(0.0, tri.v0_mat.w))];
    float3 diffuse_albedo = max(mat.albedo_rough.rgb, float3(0.0, 0.0, 0.0)) * (1.0 - clamp(mat.emission_metal.w, 0.0, 1.0));
    float3 rad = max(mat.emission_metal.rgb, float3(0.0, 0.0, 0.0)) * ground_color_emi.w + ambient_pad.rgb * diffuse_albedo;

    float3 hit_p = probe_pos + rd * hit_t;
    float bias = max(rot_row1.w, 0.002);
    float3 shadow_ro = hit_p + n * bias;

    uint lcount = min(uint(counts.z), 64u);
    float dir_scale = sky_color_dir.w;
    if (dir_scale > 0.0) {
        for (uint li = 0u; li < lcount; ++li) {
            LightGpu src = lights[li];
            float3 ldir = src.direction_range.xyz;
            float atten = 1.0, shadow_max = max_dist;
            if (src.position_kind.w > 0.5) {
                float3 delta = src.position_kind.xyz - hit_p;
                float d2 = dot(delta, delta), r2 = src.direction_range.w * src.direction_range.w;
                if (d2 < 1e-10 || d2 >= r2) continue;
                float d = sqrt(d2); ldir = delta / d;
                float rel2 = d2 / r2, edge = max(0.0, 1.0 - rel2 * rel2);
                atten = edge * edge / max(d2, 0.0001);
                if (src.position_kind.w > 1.5) {
                    float cos_a = dot(src.direction_range.xyz, -ldir);
                    float sp = clamp((cos_a - src.cone.x) / max(src.radiance_inner.w - src.cone.x, 1e-6), 0.0, 1.0);
                    atten *= sp * sp * (3.0 - 2.0 * sp);
                }
                shadow_max = max(d - bias * 2.0, 0.002);
            } else ldir = normalize(ldir);
            float nl = max(dot(n, ldir), 0.0);
            if (nl <= 0.0 || trace_any_hit(shadow_ro, ldir, 0.001, shadow_max, node_count, tri_count)) continue;
            rad += (diffuse_albedo / 3.14159265359) * src.radiance_inner.xyz * atten * nl * dir_scale;
        }
    }

    if (rot_row0.w > 0.5 && counts.w > 0.0) {
        rad += diffuse_albedo * sample_prev_sh_valid(hit_p + n * 0.05, n) * counts.w;
    }
    ray_results[gid] = float4(clamp(rad, float3(0.0, 0.0, 0.0), float3(32.0, 32.0, 32.0)), hit_t);
}

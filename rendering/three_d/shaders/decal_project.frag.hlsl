static const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu { float4 position_kind; float4 direction_range; float4 radiance_inner; float4 cone; };
struct ProbeShGpu { float4 dc; float4 px; float4 py; float4 pz; };

cbuffer DecalFragUniform : register(b0, space3) {
    column_major float4x4 inv_vp;
    column_major float4x4 inv_model;
    float4 decal_up_angle;
    float4 albedo_opacity;
    float4 emission_rough;
    float4 meta0;
    float4 viewport_shape;
    float4 view_row2;
};

cbuffer LightingBlock : register(b1, space3) {
    float4 ambient_count; float4 eye_exposure; float4 screen_depth; float4 grid_mode; float4 log_info;
};

cbuffer IrrBlock : register(b2, space3) {
    float4 origin_nx; float4 spacing_ny; float4 dims_mode;
};

Texture2D<float4> albedo_tex : register(t0, space2);
Texture2D<float> scene_depth_tex : register(t1, space2);
Texture2D<float4> scene_normal_tex : register(t2, space2);
SamplerState albedo_samp : register(s0, space2);
SamplerState depth_samp : register(s1, space2);
SamplerState norm_samp : register(s2, space2);

StructuredBuffer<LightGpu> lights : register(t3, space2);
StructuredBuffer<uint> cluster_counts : register(t4, space2);
StructuredBuffer<uint> cluster_indices : register(t5, space2);
StructuredBuffer<ProbeShGpu> probes : register(t6, space2);

float3 unit_safe(float3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (!isfinite(largest) || largest == 0.0) return float3(0.0, 1.0, 0.0);
    float3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}

float3 eval_probe(uint idx, float3 n) {
    ProbeShGpu sh = probes[idx];
    return max(sh.dc.xyz + sh.px.xyz * n.x + sh.py.xyz * n.y + sh.pz.xyz * n.z, float3(0.0, 0.0, 0.0));
}

float3 sample_irradiance(float3 wpos, float3 n) {
    int nx = int(origin_nx.w), ny = int(spacing_ny.w), nz = int(dims_mode.x);
    if (nx <= 0 || ny <= 0 || nz <= 0) return float3(0.0, 0.0, 0.0);
    float3 rel = (wpos - origin_nx.xyz) / max(spacing_ny.xyz, float3(1e-4, 1e-4, 1e-4));
    float fx = clamp(rel.x, 0.0, float(max(nx - 1, 0))), fy = clamp(rel.y, 0.0, float(max(ny - 1, 0))), fz = clamp(rel.z, 0.0, float(max(nz - 1, 0)));
    int x0 = min(int(floor(fx)), max(nx - 1, 0)), y0 = min(int(floor(fy)), max(ny - 1, 0)), z0 = min(int(floor(fz)), max(nz - 1, 0));
    int x1 = min(x0 + 1, max(nx - 1, 0)), y1 = min(y0 + 1, max(ny - 1, 0)), z1 = min(z0 + 1, max(nz - 1, 0));
    float tx = fx - float(x0), ty = fy - float(y0), tz = fz - float(z0);
    uint nxy = uint(nx * ny), ux = uint(nx);
    float3 c000 = eval_probe(uint(z0) * nxy + uint(y0) * ux + uint(x0), n), c100 = eval_probe(uint(z0) * nxy + uint(y0) * ux + uint(x1), n);
    float3 c010 = eval_probe(uint(z0) * nxy + uint(y1) * ux + uint(x0), n), c110 = eval_probe(uint(z0) * nxy + uint(y1) * ux + uint(x1), n);
    float3 c001 = eval_probe(uint(z1) * nxy + uint(y0) * ux + uint(x0), n), c101 = eval_probe(uint(z1) * nxy + uint(y0) * ux + uint(x1), n);
    float3 c011 = eval_probe(uint(z1) * nxy + uint(y1) * ux + uint(x0), n), c111 = eval_probe(uint(z1) * nxy + uint(y1) * ux + uint(x1), n);
    float3 c00 = lerp(c000, c100, tx), c10 = lerp(c010, c110, tx), c01 = lerp(c001, c101, tx), c11 = lerp(c011, c111, tx);
    return lerp(lerp(c00, c10, ty), lerp(c01, c11, ty), tz);
}

float3 pbr_direct(float3 base, float metallic, float roughness, float3 normal, float3 position, float3 eye, float3 light, float3 radiance) {
    float3 n = unit_safe(normal), v = unit_safe(eye - position), l = unit_safe(light), h = unit_safe(v + l);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, l), 0.0), nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha, denom = (nh * a2 - nh) * nh + 1.0;
    float d = a2 / (3.14159265359 * max(denom * denom, 1e-12));
    float vis = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) + nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    float3 f0 = lerp(float3(0.04, 0.04, 0.04), base, metallic), f = f0 + (float3(1.0, 1.0, 1.0) - f0) * pow(1.0 - vh, 5.0);
    float3 diff = (float3(1.0, 1.0, 1.0) - f) * (1.0 - metallic) * base / 3.14159265359;
    return (diff + d * vis * f) * radiance * nl;
}

float3 light_contrib(float3 base, float metallic, float roughness, float3 normal, float3 position, float3 eye, LightGpu src) {
    float3 light = src.direction_range.xyz;
    float atten = 1.0;
    if (src.position_kind.w > 0.5) {
        float3 delta = src.position_kind.xyz - position;
        float d2 = dot(delta, delta), r2 = src.direction_range.w * src.direction_range.w;
        if (d2 < 1e-12 || d2 >= r2) return float3(0.0, 0.0, 0.0);
        light = delta / sqrt(d2);
        float rel2 = d2 / r2, edge = max(0.0, 1.0 - rel2 * rel2);
        atten = edge * edge / max(d2, 0.0001);
        if (src.position_kind.w > 1.5) {
            float cos_a = dot(src.direction_range.xyz, -light);
            float t = clamp((cos_a - src.cone.x) / max(src.radiance_inner.w - src.cone.x, 1e-6), 0.0, 1.0);
            atten *= t * t * (3.0 - 2.0 * t);
        }
    }
    return pbr_direct(base, metallic, roughness, normal, position, eye, light, src.radiance_inner.xyz * atten);
}

float4 main(float4 pos : SV_Position) : SV_Target0 {
    float2 screen_uv = clamp(pos.xy / max(viewport_shape.xy, float2(1.0, 1.0)), float2(0.0, 0.0), float2(1.0, 1.0));
    float scene_d = scene_depth_tex.SampleLevel(depth_samp, screen_uv, 0.0).r;
    if (scene_d <= 1e-6) discard;

    float ndc_x = screen_uv.x * 2.0 - 1.0;
    float ndc_y = 1.0 - screen_uv.y * 2.0;
    float4 wp4 = mul(inv_vp, float4(ndc_x, ndc_y, scene_d, 1.0));
    float3 world_pos = wp4.xyz / max(wp4.w, 1e-6);

    float3 local = mul(inv_model, float4(world_pos, 1.0)).xyz;
    if (abs(local.x) > 0.5 || abs(local.y) > 0.5 || abs(local.z) > 0.5) discard;

    float2 duv = float2(local.x + 0.5, local.z + 0.5);
    float3 scene_n_raw = scene_normal_tex.SampleLevel(norm_samp, screen_uv, 0.0).xyz;
    float3 decal_up = unit_safe(decal_up_angle.xyz);
    float3 n = length(scene_n_raw) > 1e-4 ? unit_safe(scene_n_raw) : decal_up;

    float angle_min = decal_up_angle.w, afade = 1.0;
    if (angle_min > 0.0) {
        float ndot = abs(dot(n, decal_up));
        afade = smoothstep(angle_min, min(angle_min + 0.15, 0.999), ndot);
        if (afade <= 1e-4) discard;
    }

    float edge_fade = meta0.w, yfade = 1.0;
    if (edge_fade > 0.0) {
        yfade = 1.0 - smoothstep(max(0.0, 0.5 - edge_fade), 0.5, abs(local.y));
        if (yfade <= 1e-4) discard;
    }

    int smode = int(meta0.z + 0.5);
    float shape_a = 1.0;
    float2 centered = duv * 2.0 - 1.0;
    float r2 = dot(centered, centered);
    if (smode == 1) shape_a = pow(clamp(1.0 - r2, 0.0, 1.0), max(viewport_shape.w, 0.25));
    else if (smode == 2) {
        float r = sqrt(r2), inner = clamp(viewport_shape.z, 0.05, 0.9);
        shape_a = smoothstep(inner, inner + 0.10, r) * (1.0 - smoothstep(0.88, 1.0, r));
    }

    float4 texel = albedo_tex.Sample(albedo_samp, duv);
    float alpha = clamp(albedo_opacity.w * texel.a * shape_a * afade * yfade, 0.0, 1.0);
    if (alpha <= 1e-4) discard;

    float3 base = albedo_opacity.rgb * texel.rgb;
    float3 emission = emission_rough.rgb;
    int bmode = int(meta0.y + 0.5);
    if (bmode == 1) return float4((base + emission) * alpha, 0.0);
    if (bmode == 2) return float4(base * 0.15 * alpha, alpha);

    float roughness = max(0.045, emission_rough.w), metallic = clamp(meta0.x, 0.0, 1.0);
    float3 indirect_ambient = ambient_count.xyz;
    if (dims_mode.y > 0.5) indirect_ambient += sample_irradiance(world_pos, n) * dims_mode.z;
    float3 linear_color = indirect_ambient * base * (1.0 - metallic) + emission;

    uint total_clusters = uint(grid_mode.x) * uint(grid_mode.y) * uint(grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += light_contrib(base, metallic, roughness, n, world_pos, eye_exposure.xyz, lights[li]);
    }
    if (ambient_count.w > 0.5) {
        uint cx = uint(grid_mode.x), cy = uint(grid_mode.y), cz = uint(grid_mode.z);
        uint tx = min(uint(max(0.0, floor(pos.x / screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(pos.y / screen_depth.y * float(cy)))), cy - 1u);
        float z_near = screen_depth.z, z_far = screen_depth.w;
        float view_depth = -(dot(view_row2.xyz, world_pos) + view_row2.w);
        float vd = clamp(view_depth, z_near, z_far);
        float norm_z = grid_mode.w < 0.5 ? (log(vd / z_near) / log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u), cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER), base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += light_contrib(base, metallic, roughness, n, world_pos, eye_exposure.xyz, lights[li]);
        }
    }

    return float4(max(linear_color, float3(0.0, 0.0, 0.0)) * alpha, alpha);
}

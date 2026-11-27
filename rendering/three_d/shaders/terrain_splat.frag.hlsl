static const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    float4 position_kind;
    float4 direction_range;
    float4 radiance_inner;
    float4 cone;
};

struct ProbeShGpu {
    float4 dc;
    float4 px;
    float4 py;
    float4 pz;
};

cbuffer TerrainMatUniform : register(b0, space3) {
    float4 layer_albedo[4];
    float4 layer_pbr[4];
    float4 terrain_info0;
    float4 terrain_info1;
};

cbuffer LightingBlock : register(b1, space3) {
    float4 ambient_count;
    float4 eye_exposure;
    float4 screen_depth;
    float4 grid_mode;
    float4 log_info;
};

cbuffer IrrBlock : register(b2, space3) {
    float4 origin_nx;
    float4 spacing_ny;
    float4 dims_mode;
};

Texture2D<float4> splat_tex : register(t0, space2);
Texture2D<float4> layer0_tex : register(t1, space2);
Texture2D<float4> layer1_tex : register(t2, space2);
Texture2D<float4> layer2_tex : register(t3, space2);
Texture2D<float4> layer3_tex : register(t4, space2);

SamplerState splat_samp : register(s0, space2);
SamplerState layer0_samp : register(s1, space2);
SamplerState layer1_samp : register(s2, space2);
SamplerState layer2_samp : register(s3, space2);
SamplerState layer3_samp : register(s4, space2);

StructuredBuffer<LightGpu> lights : register(t5, space2);
StructuredBuffer<uint> cluster_counts : register(t6, space2);
StructuredBuffer<uint> cluster_indices : register(t7, space2);
StructuredBuffer<ProbeShGpu> probes : register(t8, space2);

struct Input {
    float4 position : SV_Position;
    float4 vertex_color : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 world_normal : TEXCOORD2;
    float2 splat_uv : TEXCOORD3;
    float view_depth : TEXCOORD4;
};

struct Output {
    float4 hdr_color : SV_Target0;
    float4 normal_roughness : SV_Target1;
};

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

float3 aces_srgb(float3 hdr_rgb, float exposure) {
    float3 c = max(hdr_rgb * exposure, float3(0.0, 0.0, 0.0));
    float3 mapped = clamp((c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14), 0.0, 1.0);
    float inv_g = 1.0 / 2.2;
    return pow(mapped, float3(inv_g, inv_g, inv_g));
}

Output main(Input input) {
    float2 suv = terrain_info1.y > 0.5 ? clamp((input.world.xz - terrain_info0.xy) * terrain_info0.zw, float2(0.0, 0.0), float2(1.0, 1.0)) : input.splat_uv;
    float4 w = max(splat_tex.Sample(splat_samp, suv), float4(0.0, 0.0, 0.0, 0.0));
    float3 a0 = layer_albedo[0].rgb * layer0_tex.Sample(layer0_samp, input.world.xz * layer_albedo[0].w).rgb;
    float3 a1 = layer_albedo[1].rgb * layer1_tex.Sample(layer1_samp, input.world.xz * layer_albedo[1].w).rgb;
    float3 a2 = layer_albedo[2].rgb * layer2_tex.Sample(layer2_samp, input.world.xz * layer_albedo[2].w).rgb;
    float3 a3 = layer_albedo[3].rgb * layer3_tex.Sample(layer3_samp, input.world.xz * layer_albedo[3].w).rgb;

    if (terrain_info1.x > 0.0) {
        float sharpness = terrain_info1.x;
        float4 h = float4(
            dot(a0, float3(0.3, 0.6, 0.1)) + layer_pbr[0].z,
            dot(a1, float3(0.3, 0.6, 0.1)) + layer_pbr[1].z,
            dot(a2, float3(0.3, 0.6, 0.1)) + layer_pbr[2].z,
            dot(a3, float3(0.3, 0.6, 0.1)) + layer_pbr[3].z
        );
        float4 weighted = w * (0.25 + h * 0.75);
        float max_w = max(max(weighted.x, weighted.y), max(weighted.z, weighted.w));
        float depth = max(0.02, 0.25 / (1.0 + sharpness * 0.5));
        w = max(weighted - (max_w - depth), float4(0.0, 0.0, 0.0, 0.0));
    }

    float wsum = w.x + w.y + w.z + w.w;
    w = (wsum <= 1e-5) ? float4(1.0, 0.0, 0.0, 0.0) : (w / wsum);

    float3 base = (a0 * w.x + a1 * w.y + a2 * w.z + a3 * w.w) * input.vertex_color.rgb;
    float roughness = clamp(layer_pbr[0].x * w.x + layer_pbr[1].x * w.y + layer_pbr[2].x * w.z + layer_pbr[3].x * w.w, 0.045, 1.0);
    float metallic = clamp(layer_pbr[0].y * w.x + layer_pbr[1].y * w.y + layer_pbr[2].y * w.z + layer_pbr[3].y * w.w, 0.0, 1.0);
    float3 shading_normal = unit_safe(input.world_normal);

    float3 indirect_ambient = ambient_count.xyz;
    if (dims_mode.y > 0.5) indirect_ambient += sample_irradiance(input.world, shading_normal) * dims_mode.z;
    float3 linear_color = indirect_ambient * base * (1.0 - metallic);

    uint total_clusters = uint(grid_mode.x) * uint(grid_mode.y) * uint(grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += light_contrib(base, metallic, roughness, shading_normal, input.world, eye_exposure.xyz, lights[li]);
    }
    if (ambient_count.w > 0.5) {
        uint cx = uint(grid_mode.x), cy = uint(grid_mode.y), cz = uint(grid_mode.z);
        uint tx = min(uint(max(0.0, floor(input.position.x / screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(input.position.y / screen_depth.y * float(cy)))), cy - 1u);
        float z_near = screen_depth.z, z_far = screen_depth.w, vd = clamp(input.view_depth, z_near, z_far);
        float norm_z = grid_mode.w < 0.5 ? (log(vd / z_near) / log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u);
        uint cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER), base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += light_contrib(base, metallic, roughness, shading_normal, input.world, eye_exposure.xyz, lights[li]);
        }
    }

    Output output;
    output.hdr_color = (terrain_info1.w > 0.5)
        ? float4(aces_srgb(linear_color, max(terrain_info1.z, 0.01)), 1.0)
        : float4(max(linear_color, float3(0.0, 0.0, 0.0)), 1.0);
    output.normal_roughness = float4(shading_normal, roughness);
    return output;
}

static const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu { float4 position_kind; float4 direction_range; float4 radiance_inner; float4 cone; };
struct ProbeShGpu { float4 dc; float4 px; float4 py; float4 pz; };

cbuffer FoliageMatUniform : register(b0, space3) {
    float4 base_rough;
    float4 tip_sss;
    float4 params;
};

cbuffer LightingBlock : register(b1, space3) {
    float4 ambient_count; float4 eye_exposure; float4 screen_depth; float4 grid_mode; float4 log_info;
};

cbuffer IrrBlock : register(b2, space3) {
    float4 origin_nx; float4 spacing_ny; float4 dims_mode;
};

Texture2D<float4> albedo_tex : register(t0, space2);
SamplerState albedo_samp : register(s0, space2);
StructuredBuffer<LightGpu> lights : register(t1, space2);
StructuredBuffer<uint> cluster_counts : register(t2, space2);
StructuredBuffer<uint> cluster_indices : register(t3, space2);
StructuredBuffer<ProbeShGpu> probes : register(t4, space2);

struct Input {
    float4 position : SV_Position;
    float4 vertex_color : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 world_normal : TEXCOORD2;
    float2 texture_uv : TEXCOORD3;
    float3 instance_tint : TEXCOORD4;
    float height_frac : TEXCOORD5;
    float fade : TEXCOORD6;
    float view_depth : TEXCOORD7;
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

float3 foliage_light(float3 base, float roughness, float translucency, float h_frac,
    float3 normal, float3 position, float3 eye, LightGpu src) {
    float3 ldir = src.direction_range.xyz;
    float atten = 1.0;
    if (src.position_kind.w > 0.5) {
        float3 delta = src.position_kind.xyz - position;
        float d2 = dot(delta, delta), r2 = src.direction_range.w * src.direction_range.w;
        if (d2 < 1e-12 || d2 >= r2) return float3(0.0, 0.0, 0.0);
        ldir = delta / sqrt(d2);
        float rel2 = d2 / r2, edge = max(0.0, 1.0 - rel2 * rel2);
        atten = edge * edge / max(d2, 0.0001);
        if (src.position_kind.w > 1.5) {
            float cos_a = dot(src.direction_range.xyz, -ldir);
            float t = clamp((cos_a - src.cone.x) / max(src.radiance_inner.w - src.cone.x, 1e-6), 0.0, 1.0);
            atten *= t * t * (3.0 - 2.0 * t);
        }
    }
    float3 n = unit_safe(normal), v = unit_safe(eye - position), l = unit_safe(ldir), h = unit_safe(v + l);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, l), 0.0), nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha, denom = (nh * a2 - nh) * nh + 1.0;
    float d = a2 / (3.14159265359 * max(denom * denom, 1e-12));
    float vis = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) + nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    float3 f = float3(0.04, 0.04, 0.04) + float3(0.96, 0.96, 0.96) * pow(1.0 - vh, 5.0);
    float3 diff = (float3(1.0, 1.0, 1.0) - f) * base / 3.14159265359;
    float3 direct = (diff + d * vis * f) * src.radiance_inner.xyz * atten * nl;
    float back_dot = clamp(dot(v, -l), 0.0, 1.0);
    float sss = pow(back_dot, 2.2) * translucency * (0.35 + 0.65 * h_frac);
    float3 translucent = base * src.radiance_inner.xyz * atten * sss * 0.45;
    return direct + translucent;
}

float bayer4x4(uint2 pt) {
    uint idx = (pt.y & 3u) * 4u + (pt.x & 3u);
    static const float tbl[16] = {
        0.0/16.0, 8.0/16.0, 2.0/16.0, 10.0/16.0,
       12.0/16.0, 4.0/16.0, 14.0/16.0, 6.0/16.0,
        3.0/16.0, 11.0/16.0, 1.0/16.0, 9.0/16.0,
       15.0/16.0, 7.0/16.0, 13.0/16.0, 5.0/16.0
    };
    return tbl[idx];
}

float3 aces_srgb(float3 hdr_rgb, float exposure) {
    float3 c = max(hdr_rgb * exposure, float3(0.0, 0.0, 0.0));
    float3 mapped = clamp((c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14), 0.0, 1.0);
    float inv_g = 1.0 / 2.2;
    return pow(mapped, float3(inv_g, inv_g, inv_g));
}

Output main(Input input, bool is_front : SV_IsFrontFace) {
    if (input.fade <= 0.001) discard;
    if (params.z > 0.5 && input.fade < 0.999) {
        if (input.fade < bayer4x4(uint2(input.position.xy))) discard;
    }

    float4 texel = albedo_tex.Sample(albedo_samp, input.texture_uv);
    float alpha = texel.a * input.vertex_color.a;
    if (params.x > 0.0) clip(alpha - params.x);

    float3 gradient_tint = lerp(base_rough.rgb, tip_sss.rgb, clamp(input.height_frac, 0.0, 1.0));
    float ao = lerp(params.y, 1.0, clamp(input.height_frac, 0.0, 1.0));
    float3 base = texel.rgb * input.vertex_color.rgb * input.instance_tint * gradient_tint * ao;
    float roughness = clamp(base_rough.w, 0.045, 1.0);
    float translucency = max(tip_sss.w, 0.0);

    float3 n = unit_safe(input.world_normal);
    if (!is_front) n = -n;

    float3 indirect_ambient = ambient_count.xyz;
    if (dims_mode.y > 0.5) indirect_ambient += sample_irradiance(input.world, n) * dims_mode.z;
    float3 linear_color = indirect_ambient * base;

    uint total_clusters = uint(grid_mode.x) * uint(grid_mode.y) * uint(grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += foliage_light(base, roughness, translucency, input.height_frac, n, input.world, eye_exposure.xyz, lights[li]);
    }
    if (ambient_count.w > 0.5) {
        uint cx = uint(grid_mode.x), cy = uint(grid_mode.y), cz = uint(grid_mode.z);
        uint tx = min(uint(max(0.0, floor(input.position.x / screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(input.position.y / screen_depth.y * float(cy)))), cy - 1u);
        float z_near = screen_depth.z, z_far = screen_depth.w, vd = clamp(input.view_depth, z_near, z_far);
        float norm_z = grid_mode.w < 0.5 ? (log(vd / z_near) / log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u), cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER), base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += foliage_light(base, roughness, translucency, input.height_frac, n, input.world, eye_exposure.xyz, lights[li]);
        }
    }

    Output output;
    output.hdr_color = (params.w > 0.5)
        ? float4(aces_srgb(linear_color, eye_exposure.w), 1.0)
        : float4(max(linear_color, float3(0.0, 0.0, 0.0)), 1.0);
    output.normal_roughness = float4(n, roughness);
    return output;
}

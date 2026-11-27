static const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    float4 position_kind;
    float4 direction_range;
    float4 radiance_inner;
    float4 cone;
};

struct Material {
    float4 base_metallic;
    float4 emission_roughness;
    float4 maps_normal;
    float4 surface;
    float4 uv_rect;
    float4 pbr_ext0;
    float4 pbr_ext1;
};

struct ClusteredLighting {
    float4 ambient_count;
    float4 eye_exposure;
    float4 screen_depth;
    float4 grid_mode;
    float4 log_info;
};

struct Shadow {
    column_major float4x4 mvp[4];
    float4 direction_bias;
    float4 shadow_filter;
    float4 depth;
    float4 camera_depth;
    float4 ranges[4];
    float4 limits;
    float4 gradient_scales;
};

struct IrradianceUniform {
    float4 origin_nx;
    float4 spacing_ny;
    float4 dims_mode;
};

struct ProbeShGpu {
    float4 dc;
    float4 px;
    float4 py;
    float4 pz;
};

struct Input {
    float4 position : SV_Position;
    float4 vertex_color : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 world_normal : TEXCOORD2;
    float2 texture_uv : TEXCOORD3;
    float3 world_tangent : TEXCOORD4;
    float3 world_bitangent : TEXCOORD5;
    float view_depth : TEXCOORD6;
};

struct Output {
    float4 hdr_color : SV_Target0;
    float4 normal_roughness : SV_Target1;
};

Texture2D<float4> base_texture : register(t0, space2);
SamplerState base_sampler : register(s0, space2);
Texture2D<float4> orm_texture : register(t1, space2);
SamplerState orm_sampler : register(s1, space2);
Texture2D<float4> emission_texture : register(t2, space2);
SamplerState emission_sampler : register(s2, space2);
Texture2D<float4> normal_texture : register(t3, space2);
SamplerState normal_sampler : register(s3, space2);
Texture2D<float4> occlusion_texture : register(t4, space2);
SamplerState occlusion_sampler : register(s4, space2);
Texture2D<float4> shadow_texture : register(t5, space2);
SamplerState shadow_sampler : register(s5, space2);

StructuredBuffer<LightGpu> lights : register(t6, space2);
StructuredBuffer<uint> cluster_counts : register(t7, space2);
StructuredBuffer<uint> cluster_indices : register(t8, space2);
StructuredBuffer<ProbeShGpu> probes : register(t9, space2);

cbuffer MaterialBlock : register(b0, space3) { Material p; };
cbuffer LightingBlock : register(b1, space3) { ClusteredLighting l; };
cbuffer ShadowBlock : register(b2, space3) { Shadow s; };
cbuffer IrrBlock : register(b3, space3) { IrradianceUniform irr; };

float3 unit_safe(float3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (!isfinite(largest) || largest == 0.0) return float3(0.0, 0.0, 0.0);
    float3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}

float3 material_direct(float3 base, float metallic, float roughness,
    float clearcoat, float clearcoat_roughness, float ior,
    float3 sheen_color, float sheen_roughness,
    float3 normal, float3 position, float3 eye, float3 light, float3 radiance) {
    float3 n = unit_safe(normal), v = unit_safe(eye - position), lvec = unit_safe(light), h = unit_safe(v + lvec);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, lvec), 0.0);
    float nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha;
    float denominator = (nh * a2 - nh) * nh + 1.0;
    float distribution = a2 / (3.14159265359 * max(denominator * denominator, 1e-12));
    float visibility = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) +
        nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    float ior_ratio = (ior - 1.0) / max(ior + 1.0, 1e-4);
    float f0_dielectric = ior_ratio * ior_ratio;
    float3 f0 = lerp(float3(f0_dielectric, f0_dielectric, f0_dielectric), base, metallic);
    float factor = pow(1.0 - vh, 5.0);
    float3 fresnel = f0 + (float3(1.0, 1.0, 1.0) - f0) * factor;
    // Fdez-Aguera analytical GGX multi-scattering energy compensation.
    float4 r_ms = roughness * float4(-1.0, -0.0275, -0.572, 0.022) + float4(1.0, 0.0425, 1.04, -0.04);
    float a004 = min(r_ms.x * r_ms.x, exp2(-9.28 * nv)) * r_ms.x + r_ms.y;
    float2 ab_ms = float2(-1.04, 1.04) * a004 + r_ms.zw;
    float ess = clamp(ab_ms.x + ab_ms.y, 0.05, 1.0);
    float3 ms_comp = float3(1.0, 1.0, 1.0) + f0 * (1.0 / ess - 1.0);
    float3 diffuse = (float3(1.0, 1.0, 1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    float3 brdf = diffuse + distribution * visibility * fresnel * ms_comp;

    float max_sheen = max(sheen_color.x, max(sheen_color.y, sheen_color.z));
    if (max_sheen > 0.0) {
        float inv_r = 1.0 / max(sheen_roughness * sheen_roughness, 0.002);
        float sin2h = max(1.0 - nh * nh, 1e-6);
        float d_charlie = (2.0 + inv_r) * pow(sin2h, inv_r * 0.5) / (2.0 * 3.14159265359);
        float v_sheen = 1.0 / max(4.0 * (nl + nv - nl * nv), 1e-4);
        float3 sheen_brdf = sheen_color * d_charlie * v_sheen;
        float sheen_scale = max(0.0, 1.0 - max_sheen * pow(1.0 - nv, 3.0) * 0.5);
        brdf = brdf * sheen_scale + sheen_brdf;
    }

    if (clearcoat > 0.0) {
        float cc_alpha = clearcoat_roughness * clearcoat_roughness;
        float cc_a2 = cc_alpha * cc_alpha;
        float cc_denom = (nh * cc_a2 - nh) * nh + 1.0;
        float cc_d = cc_a2 / (3.14159265359 * max(cc_denom * cc_denom, 1e-12));
        float cc_v = 0.5 / max(nl * sqrt(nv * nv * (1.0 - cc_a2) + cc_a2) +
            nv * sqrt(nl * nl * (1.0 - cc_a2) + cc_a2), 0.000001);
        float cc_f = 0.04 + 0.96 * factor;
        float cc_v3 = clearcoat * cc_d * cc_v * cc_f;
        brdf = brdf * (1.0 - clearcoat * cc_f) + float3(cc_v3, cc_v3, cc_v3);
    }
    return brdf * radiance * nl;
}

float3 source_direct(float3 base, float metallic, float roughness,
    float clearcoat, float clearcoat_roughness, float ior,
    float3 sheen_color, float sheen_roughness,
    float3 normal, float3 position, float3 eye, LightGpu src) {
    float3 light = src.direction_range.xyz;
    float attenuation = 1.0;
    if (src.position_kind.w > 0.5) {
        float3 delta = src.position_kind.xyz - position;
        float distance2 = dot(delta, delta), radius2 = src.direction_range.w * src.direction_range.w;
        if (distance2 < 1e-12 || distance2 >= radius2) return float3(0.0, 0.0, 0.0);
        light = delta / sqrt(distance2);
        float relative2 = distance2 / radius2;
        float edge = max(0.0, 1.0 - relative2 * relative2);
        attenuation = edge * edge / max(distance2, 0.0001);
        if (src.position_kind.w > 1.5) {
            float cosine = dot(src.direction_range.xyz, -light);
            float transition = clamp((cosine - src.cone.x) / max(src.radiance_inner.w - src.cone.x, 0.000001), 0.0, 1.0);
            attenuation *= transition * transition * (3.0 - 2.0 * transition);
        }
    }
    return material_direct(base, metallic, roughness, clearcoat, clearcoat_roughness, ior,
        sheen_color, sheen_roughness, normal, position, eye, light, src.radiance_inner.xyz * attenuation);
}

float3 eval_probe(uint idx, float3 n) {
    ProbeShGpu sh = probes[idx];
    return max(sh.dc.xyz + sh.px.xyz * n.x + sh.py.xyz * n.y + sh.pz.xyz * n.z, float3(0.0, 0.0, 0.0));
}

float3 sample_irradiance(float3 wpos, float3 n) {
    int nx = int(irr.origin_nx.w);
    int ny = int(irr.spacing_ny.w);
    int nz = int(irr.dims_mode.x);
    float3 f = (wpos - irr.origin_nx.xyz) / irr.spacing_ny.xyz;
    int x0 = clamp(int(floor(f.x)), 0, nx - 1);
    int y0 = clamp(int(floor(f.y)), 0, ny - 1);
    int z0 = clamp(int(floor(f.z)), 0, nz - 1);
    int x1 = min(x0 + 1, nx - 1);
    int y1 = min(y0 + 1, ny - 1);
    int z1 = min(z0 + 1, nz - 1);
    float tx = clamp(f.x - float(x0), 0.0, 1.0);
    float ty = clamp(f.y - float(y0), 0.0, 1.0);
    float tz = clamp(f.z - float(z0), 0.0, 1.0);
    float3 c000 = eval_probe(uint((z0 * ny + y0) * nx + x0), n);
    float3 c100 = eval_probe(uint((z0 * ny + y0) * nx + x1), n);
    float3 c010 = eval_probe(uint((z0 * ny + y1) * nx + x0), n);
    float3 c110 = eval_probe(uint((z0 * ny + y1) * nx + x1), n);
    float3 c001 = eval_probe(uint((z1 * ny + y0) * nx + x0), n);
    float3 c101 = eval_probe(uint((z1 * ny + y0) * nx + x1), n);
    float3 c011 = eval_probe(uint((z1 * ny + y1) * nx + x0), n);
    float3 c111 = eval_probe(uint((z1 * ny + y1) * nx + x1), n);
    float3 c00 = lerp(c000, c100, tx);
    float3 c10 = lerp(c010, c110, tx);
    float3 c01 = lerp(c001, c101, tx);
    float3 c11 = lerp(c011, c111, tx);
    return lerp(lerp(c00, c10, ty), lerp(c01, c11, ty), tz);
}

float3 normal_map_direction(float3 normal, float3 tangent, float3 bitangent, float3 texel, float scale) {
    float3 n = unit_safe(normal);
    if (scale == 0.0) return n;
    float3 t = unit_safe(tangent);
    t = unit_safe(t - n * dot(n, t));
    float3 b = unit_safe(cross(n, t));
    if (dot(b, unit_safe(bitangent)) < 0.0) b = -b;
    float3 mapped = texel * 2.0 - float3(1.0, 1.0, 1.0);
    mapped.x *= scale; mapped.y *= scale;
    mapped = unit_safe(mapped);
    float3 result = unit_safe(t * mapped.x + b * mapped.y + n * mapped.z);
    if (dot(result, result) == 0.0) return n;
    return result;
}

Output main(Input input, bool is_front : SV_IsFrontFace) {
    Output output;
    int mask = int(p.maps_normal.x);
    float2 sample_uv = p.uv_rect.xy + input.texture_uv * p.uv_rect.zw;
    float3 base = p.base_metallic.xyz * input.vertex_color.xyz;
    float alpha = input.vertex_color.a;
    if ((mask & 1) != 0) {
        float4 base_texel = base_texture.Sample(base_sampler, sample_uv);
        base *= base_texel.rgb;
        alpha *= base_texel.a;
    }
    alpha *= p.pbr_ext0.x;
    if (p.surface.w > 0.0) clip(alpha - p.surface.w);

    float clearcoat = clamp(p.pbr_ext0.y, 0.0, 1.0);
    float clearcoat_roughness = max(0.045, p.pbr_ext0.z);
    float ior = max(1.0, p.pbr_ext0.w);
    float3 sheen_color = max(p.pbr_ext1.xyz, float3(0.0, 0.0, 0.0));
    float sheen_roughness = max(0.045, p.pbr_ext1.w);

    float3 shading_normal = unit_safe(input.world_normal);
    if ((mask & 8) != 0) {
        float3 adj_tangent = p.uv_rect.z < 0.0 ? -input.world_tangent : input.world_tangent;
        float3 adj_bitangent = p.uv_rect.w < 0.0 ? -input.world_bitangent : input.world_bitangent;
        shading_normal = normal_map_direction(input.world_normal, adj_tangent, adj_bitangent,
            normal_texture.Sample(normal_sampler, sample_uv).rgb, p.maps_normal.z);
    }
    bool surface_front = is_front;
    if (p.surface.x < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;

    float3 orm = float3(1.0, 1.0, 1.0);
    if ((mask & 2) != 0) orm = orm_texture.Sample(orm_sampler, sample_uv).rgb;
    float ao_strength = p.maps_normal.y;
    if ((mask & 16) != 0) {
        orm.x = occlusion_texture.Sample(occlusion_sampler, sample_uv).r;
        ao_strength = p.surface.y;
    }
    float metallic = p.base_metallic.w * orm.z;
    float roughness = max(0.045, p.emission_roughness.w * orm.y);
    float occlusion = 1.0 + ao_strength * (orm.x - 1.0);
    float3 emission = p.emission_roughness.xyz;
    if ((mask & 4) != 0) emission *= emission_texture.Sample(emission_sampler, sample_uv).rgb;

    if (p.surface.z < 0.5) {
        output.hdr_color = float4(input.vertex_color.rgb, alpha);
        output.normal_roughness = float4(shading_normal, roughness);
        return output;
    }
    if (p.surface.z > 1.5) {
        output.hdr_color = float4(max(base + emission, float3(0.0, 0.0, 0.0)), alpha);
        output.normal_roughness = float4(shading_normal, roughness);
        return output;
    }

    float3 indirect_ambient = l.ambient_count.xyz;
    if (irr.dims_mode.y > 0.5) {
        indirect_ambient += sample_irradiance(input.world, shading_normal) * irr.dims_mode.z;
    }
    float3 linear_color = indirect_ambient * occlusion * base * (1.0 - metallic) + emission;
    float max_sheen_ind = max(sheen_color.x, max(sheen_color.y, sheen_color.z));
    if (max_sheen_ind > 0.0) {
        float3 v_dir = unit_safe(l.eye_exposure.xyz - input.world);
        float nv_ind = max(dot(shading_normal, v_dir), 0.0001);
        linear_color += indirect_ambient * occlusion * sheen_color * pow(1.0 - nv_ind, 2.0) * 0.35;
    }

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += source_direct(base, metallic, roughness, clearcoat, clearcoat_roughness, ior,
            sheen_color, sheen_roughness, shading_normal, input.world, l.eye_exposure.xyz, lights[li]);
    }

    if (l.ambient_count.w > 0.5) {
        uint cx = uint(l.grid_mode.x);
        uint cy = uint(l.grid_mode.y);
        uint cz = uint(l.grid_mode.z);
        uint tx = min(uint(max(0.0, floor(input.position.x / l.screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(input.position.y / l.screen_depth.y * float(cy)))), cy - 1u);
        float z_near = l.screen_depth.z;
        float z_far = l.screen_depth.w;
        float vd = clamp(input.view_depth, z_near, z_far);
        float norm_z = l.grid_mode.w < 0.5 ? (log(vd / z_near) / l.log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u);
        uint cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER);
        uint base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += source_direct(base, metallic, roughness, clearcoat, clearcoat_roughness, ior,
                sheen_color, sheen_roughness, shading_normal, input.world, l.eye_exposure.xyz, lights[li]);
        }
    }

    output.hdr_color = float4(max(linear_color, float3(0.0, 0.0, 0.0)), alpha);
    output.normal_roughness = float4(shading_normal, roughness);
    return output;
}

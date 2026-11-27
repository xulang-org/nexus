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

cbuffer MaterialBlock : register(b0, space3) { Material p; };
cbuffer LightingBlock : register(b1, space3) { ClusteredLighting l; };
cbuffer ShadowBlock : register(b2, space3) { Shadow s; };

float3 unit_safe(float3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (!isfinite(largest) || largest == 0.0) return float3(0.0, 0.0, 0.0);
    float3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}

float srgb_channel(float value) {
    return value <= 0.0031308 ? 12.92 * value : 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

float3 material_direct(float3 base, float metallic, float roughness,
    float3 normal, float3 position, float3 eye, float3 light, float3 radiance) {
    float3 n = unit_safe(normal), v = unit_safe(eye - position), lvec = unit_safe(light), h = unit_safe(v + lvec);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, lvec), 0.0);
    float nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha;
    float denominator = (nh * a2 - nh) * nh + 1.0;
    float distribution = a2 / (3.14159265359 * max(denominator * denominator, 1e-12));
    float visibility = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) +
        nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    float3 f0 = lerp(float3(0.04, 0.04, 0.04), base, metallic);
    float factor = pow(1.0 - vh, 5.0);
    float3 fresnel = f0 + (float3(1.0, 1.0, 1.0) - f0) * factor;
    // Fdez-Aguera analytical GGX multi-scattering energy compensation.
    float4 r_ms = roughness * float4(-1.0, -0.0275, -0.572, 0.022) + float4(1.0, 0.0425, 1.04, -0.04);
    float a004 = min(r_ms.x * r_ms.x, exp2(-9.28 * nv)) * r_ms.x + r_ms.y;
    float2 ab_ms = float2(-1.04, 1.04) * a004 + r_ms.zw;
    float ess = clamp(ab_ms.x + ab_ms.y, 0.05, 1.0);
    float3 ms_comp = float3(1.0, 1.0, 1.0) + f0 * (1.0 / ess - 1.0);
    float3 diffuse = (float3(1.0, 1.0, 1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    return (diffuse + distribution * visibility * fresnel * ms_comp) * radiance * nl;
}

float3 source_direct(float3 base, float metallic, float roughness,
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
    return material_direct(base, metallic, roughness, normal, position, eye, light, src.radiance_inner.xyz * attenuation);
}

float3 finish_lighting(float3 linear_color, float exposure) {
    float3 exposed = max(linear_color * exposure, float3(0.0, 0.0, 0.0));
    float3 mapped = exposed / (float3(1.0, 1.0, 1.0) + exposed);
    return float3(srgb_channel(mapped.x), srgb_channel(mapped.y), srgb_channel(mapped.z));
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

int point_shadow_face(float3 d) {
    float3 a = abs(d);
    if (a.x >= a.y && a.x >= a.z) return d.x >= 0.0 ? 0 : 1;
    if (a.y >= a.z) return d.y >= 0.0 ? 2 : 3;
    return d.z >= 0.0 ? 4 : 5;
}

float2 point_shadow_uv(float3 d, int face) {
    float2 pt;
    if (face == 0) pt = float2(d.z, d.y) / abs(d.x);
    else if (face == 1) pt = float2(-d.z, d.y) / abs(d.x);
    else if (face == 2) pt = float2(d.x, d.z) / abs(d.y);
    else if (face == 3) pt = float2(-d.x, d.z) / abs(d.y);
    else if (face == 4) pt = float2(-d.x, d.y) / abs(d.z);
    else pt = float2(d.x, d.y) / abs(d.z);
    return pt * float2(0.5, -0.5) + float2(0.5, 0.5);
}

float3 point_shadow_ray(float2 uv, int face) {
    float2 pt = uv * float2(2.0, -2.0) + float2(-1.0, 1.0);
    if (face == 0) return float3(1.0, pt.y, pt.x);
    if (face == 1) return float3(-1.0, pt.y, -pt.x);
    if (face == 2) return float3(pt.x, 1.0, pt.y);
    if (face == 3) return float3(-pt.x, -1.0, pt.y);
    if (face == 4) return float3(-pt.x, pt.y, 1.0);
    return float3(pt.x, pt.y, -1.0);
}

float point_shadow_visibility(float3 wpos, float3 nrm, float4 light_bias, float4 shadow_filter, float4 depth) {
    float3 n = unit_safe(cross(ddx(wpos), ddy(wpos)));
    if (dot(n, n) == 0.0) n = unit_safe(nrm);
    float3 delta = wpos - light_bias.xyz;
    float major = max(abs(delta.x), max(abs(delta.y), abs(delta.z)));
    float receiver_z = depth.x / max(major, 0.000001) - depth.y;
    if (major <= 0.000001 || receiver_z < 0.0 || receiver_z > 1.0) return 1.0;
    int face = point_shadow_face(delta);
    float2 uv = point_shadow_uv(delta, face);
    float plane_distance = dot(n, delta);
    float bias = light_bias.w + shadow_filter.y * (1.0 - max(0.0, dot(unit_safe(nrm), unit_safe(-delta))));
    float visibility = 0.0;
    float weight_sum = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            float2 tap = (floor(uv / shadow_filter.x) + float2(float(x), float(y)) + float2(0.5, 0.5)) * shadow_filter.x;
            float2 dist_tex = tap / shadow_filter.x - uv / shadow_filter.x;
            float2 weights = max(float2(1.5, 1.5) - abs(dist_tex), float2(0.0, 0.0));
            float weight = weights.x * weights.y;
            weight_sum += weight;
            if (weight <= 0.0) continue;
            float3 ray = point_shadow_ray(tap, face);
            int adjacent = point_shadow_face(ray);
            float2 at = (clamp(floor(point_shadow_uv(ray, adjacent) / shadow_filter.x), float2(0.0, 0.0), float2(1.0 / shadow_filter.x - 1.0, 1.0 / shadow_filter.x - 1.0)) + float2(0.5, 0.5)) * shadow_filter.x;
            ray = point_shadow_ray(at, adjacent);
            float denominator = dot(n, ray);
            if (abs(denominator) <= 0.000001) { visibility += weight; continue; }
            float dist = plane_distance / denominator;
            if (dist <= 0.0) { visibility += weight; continue; }
            float reference = depth.x / dist - depth.y;
            if (reference < 0.0 || reference > 1.0) { visibility += weight; continue; }
            float2 atlas = (at + float2(float(adjacent % 3), float(adjacent / 3))) / depth.zw;
            visibility += (reference + bias >= shadow_texture.SampleLevel(shadow_sampler, atlas, 0.0).r ? 1.0 : 0.0) * weight;
        }
    }
    return visibility / weight_sum;
}

float2 cascade_gradient(float3 pt) {
    float3 n = unit_safe(cross(ddx(pt), ddy(pt)));
    if (abs(n.z) <= 0.00001) return float2(0.0, 0.0);
    return float2(-2.0 * n.x, 2.0 * n.y) / n.z;
}

float pcss_fract(float x) { return x - floor(x); }
float pcss_contact_hardened(float2 uv, float receiver_z, float2 gradient, float bias,
    float texel, float2 atlas_offset, float2 atlas_size, float pcss_radius) {
    float2 cell = floor(uv / texel);
    float ign = pcss_fract(52.9829189 * pcss_fract(dot(cell, float2(0.06711056, 0.00583715))));
    float ang = 6.2831853 * ign;
    float search_r = pcss_radius * texel;
    float blocker_sum = 0.0;
    float blocker_count = 0.0;
    for (int k = 0; k < 16; ++k) {
        float r = sqrt((float(k) + 0.5) / 16.0);
        float theta = float(k) * 2.39996323 + ang;
        float2 at = clamp(uv + float2(cos(theta), sin(theta)) * (r * search_r), float2(0.5 * texel, 0.5 * texel), float2(1.0 - 0.5 * texel, 1.0 - 0.5 * texel));
        float2 atlas = (at + atlas_offset) / atlas_size;
        float sample_d = shadow_texture.SampleLevel(shadow_sampler, atlas, 0.0).r;
        if (sample_d > receiver_z + dot(gradient, at - uv) + bias) {
            blocker_sum += sample_d;
            blocker_count += 1.0;
        }
    }
    if (blocker_count < 0.5) return 1.0;
    float avg_blocker = blocker_sum / blocker_count;
    float blocker_gap = max(0.0, avg_blocker - receiver_z);
    float penumbra_texels = clamp(0.75 + blocker_gap * pcss_radius * 18.0, 0.75, pcss_radius * 2.5);
    float filter_r = penumbra_texels * texel;
    float vis = 0.0;
    for (int k = 0; k < 16; ++k) {
        float r = sqrt((float(k) + 0.5) / 16.0);
        float theta = float(k) * 2.39996323 + ang;
        float2 at = uv + float2(cos(theta), sin(theta)) * (r * filter_r);
        if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) { vis += 1.0; continue; }
        float2 atlas = (at + atlas_offset) / atlas_size;
        vis += (receiver_z + dot(gradient, at - uv) + bias >= shadow_texture.SampleLevel(shadow_sampler, atlas, 0.0).r) ? 1.0 : 0.0;
    }
    return vis / 16.0;
}

float cascade_sample(float3 pt, float2 gradient, int layer, float bias, float texel, float2 atlas_size, float raster_bias, float pcss_radius) {
    if (pt.x < -1.0 || pt.x > 1.0 || pt.y < -1.0 || pt.y > 1.0 || pt.z < 0.0 || pt.z > 1.0) return 1.0;
    bias += max(abs(gradient.x), abs(gradient.y)) * texel * raster_bias;
    float2 uv = float2(pt.x * 0.5 + 0.5, 0.5 - pt.y * 0.5);
    if (pcss_radius > 0.0001) {
        return pcss_contact_hardened(uv, pt.z, gradient, bias, texel, float2(float(layer % 2), float(layer / 2)), atlas_size, pcss_radius);
    }
    float visible = 0.0, total = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            float2 at = (floor(uv / texel) + float2(float(x), float(y)) + float2(0.5, 0.5)) * texel;
            float2 weights = max(float2(1.5, 1.5) - abs((at - uv) / texel), float2(0.0, 0.0));
            float weight = weights.x * weights.y;
            total += weight;
            if (weight <= 0.0) continue;
            if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) { visible += weight; continue; }
            float2 atlas = (at + float2(float(layer % 2), float(layer / 2))) / atlas_size;
            visible += (pt.z + dot(gradient, at - uv) + bias >= shadow_texture.SampleLevel(shadow_sampler, atlas, 0.0).r ? 1.0 : 0.0) * weight;
        }
    }
    return visible / total;
}

float cascade_shadow_visibility(float3 wpos, float3 nrm) {
    float3 p0 = mul(s.mvp[0], float4(wpos, 1.0)).xyz;
    float3 p1 = mul(s.mvp[1], float4(wpos, 1.0)).xyz;
    float3 p2 = mul(s.mvp[2], float4(wpos, 1.0)).xyz;
    float3 p3 = mul(s.mvp[3], float4(wpos, 1.0)).xyz;
    float2 g0 = cascade_gradient(p0);
    float2 g1 = g0 * s.gradient_scales.y, g2 = g0 * s.gradient_scales.z, g3 = g0 * s.gradient_scales.w;
    float dist = dot(s.camera_depth, float4(wpos, 1.0));
    if (dist < s.limits.x || dist > s.limits.y) return 1.0;
    int layer = 0;
    if (dist > s.ranges[0].y && s.limits.z > 1.5) layer = 1;
    if (dist > s.ranges[1].y && s.limits.z > 2.5) layer = 2;
    if (dist > s.ranges[2].y && s.limits.z > 3.5) layer = 3;
    float3 pt = p0; float2 g = g0; float4 range = s.ranges[0];
    float3 next_p = p1; float2 next_g = g1; float4 next_range = s.ranges[1];
    if (layer == 1) { pt = p1; g = g1; range = s.ranges[1]; next_p = p2; next_g = g2; next_range = s.ranges[2]; }
    if (layer == 2) { pt = p2; g = g2; range = s.ranges[2]; next_p = p3; next_g = g3; next_range = s.ranges[3]; }
    if (layer == 3) { pt = p3; g = g3; range = s.ranges[3]; }
    float pcss_radius = max(0.0, -s.gradient_scales.x);
    float bias = s.direction_bias.w + s.shadow_filter.y * (1.0 - max(0.0, dot(unit_safe(nrm), s.direction_bias.xyz)));
    float current = cascade_sample(pt, g, layer, bias * range.w, s.shadow_filter.x, s.depth.zw, s.limits.w, pcss_radius);
    if (range.y > range.z && dist > range.z) {
        float next = 1.0;
        if (float(layer + 1) < s.limits.z) next = cascade_sample(next_p, next_g, layer + 1, bias * next_range.w, s.shadow_filter.x, s.depth.zw, s.limits.w, pcss_radius);
        float alpha = clamp((dist - range.z) / (range.y - range.z), 0.0, 1.0);
        alpha = alpha * alpha * (3.0 - 2.0 * alpha);
        current = lerp(current, next, alpha);
    }
    return current;
}

float shadow_visibility(float3 wpos, float3 nrm) {
    if (s.shadow_filter.w > 2.5) return point_shadow_visibility(wpos, nrm, s.direction_bias, s.shadow_filter, s.depth);
    float4 projected = mul(s.mvp[0], float4(wpos, 1.0));
    float3 pt = projected.xyz / max(projected.w, 0.000001);
    float3 n = unit_safe(cross(ddx(pt), ddy(pt)));
    float2 gradient = float2(0.0, 0.0);
    if (abs(n.z) > 0.00001) gradient = float2(-2.0 * n.x, 2.0 * n.y) / n.z;
    if (projected.w <= 0.000001 || pt.x < -1.0 || pt.x > 1.0 || pt.y < -1.0 || pt.y > 1.0 || pt.z < 0.0 || pt.z > 1.0) return 1.0;
    float2 uv = float2(pt.x * 0.5 + 0.5, 0.5 - pt.y * 0.5);
    float3 toward_light = s.direction_bias.xyz;
    if (s.shadow_filter.w > 1.5) toward_light = unit_safe(s.direction_bias.xyz - wpos);
    float bias = s.direction_bias.w + s.shadow_filter.y * (1.0 - max(0.0, dot(unit_safe(nrm), toward_light)));
    float pcss_radius = max(0.0, -s.gradient_scales.x);
    if (pcss_radius > 0.0001) {
        return pcss_contact_hardened(uv, pt.z, gradient, bias, s.shadow_filter.x, float2(0.0, 0.0), float2(1.0, 1.0), pcss_radius);
    }
    float visibility = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            float2 at = (floor(uv / s.shadow_filter.x) + float2(float(x), float(y)) + float2(0.5, 0.5)) * s.shadow_filter.x;
            if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) visibility += 1.0;
            else visibility += (pt.z + dot(gradient, at - uv) + bias >= shadow_texture.SampleLevel(shadow_sampler, at, 0.0).r) ? 1.0 : 0.0;
        }
    }
    return visibility / 9.0;
}

float4 main(Input input, bool is_front : SV_IsFrontFace) : SV_Target0 {
    if (p.surface.z < 0.5) return input.vertex_color;
    int mask = int(p.maps_normal.x);
    float2 sample_uv = p.uv_rect.xy + input.texture_uv * p.uv_rect.zw;
    float3 base = p.base_metallic.xyz * input.vertex_color.xyz;
    float alpha = input.vertex_color.a;
    if ((mask & 1) != 0) {
        float4 base_texel = base_texture.Sample(base_sampler, sample_uv);
        base *= base_texel.rgb;
        alpha *= base_texel.a;
    }
    if (p.surface.w > 0.0) clip(alpha - p.surface.w);
    if (p.surface.z > 1.5) {
        float3 clamped = saturate(base);
        return float4(srgb_channel(clamped.x), srgb_channel(clamped.y), srgb_channel(clamped.z), 1.0);
    }
    float3 orm = float3(1.0, 1.0, 1.0);
    if ((mask & 2) != 0) orm = orm_texture.Sample(orm_sampler, sample_uv).rgb;
    float ao_strength = p.maps_normal.y;
    if ((mask & 16) != 0) {
        orm.x = occlusion_texture.Sample(occlusion_sampler, sample_uv).r;
        ao_strength = p.surface.y;
    }
    float3 emission = p.emission_roughness.xyz;
    if ((mask & 4) != 0) emission *= emission_texture.Sample(emission_sampler, sample_uv).rgb;
    float3 shading_normal = input.world_normal;
    if ((mask & 8) != 0) {
        float3 adj_tangent = p.uv_rect.z < 0.0 ? -input.world_tangent : input.world_tangent;
        float3 adj_bitangent = p.uv_rect.w < 0.0 ? -input.world_bitangent : input.world_bitangent;
        shading_normal = normal_map_direction(input.world_normal, adj_tangent, adj_bitangent,
            normal_texture.Sample(normal_sampler, sample_uv).rgb, p.maps_normal.z);
    }
    bool surface_front = is_front;
    if (p.surface.x < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;
    float metallic = p.base_metallic.w * orm.z;
    float roughness = max(0.045, p.emission_roughness.w * orm.y);
    float occlusion = 1.0 + ao_strength * (orm.x - 1.0);
    float3 linear_color = l.ambient_count.xyz * occlusion * base * (1.0 - metallic) + emission;

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        float visibility = 1.0;
        if (s.shadow_filter.w > 0.5 && li == uint(s.shadow_filter.z)) {
            if (s.shadow_filter.w > 3.5) visibility = cascade_shadow_visibility(input.world, input.world_normal);
            else visibility = shadow_visibility(input.world, input.world_normal);
        }
        linear_color += source_direct(base, metallic, roughness, shading_normal, input.world, l.eye_exposure.xyz, lights[li]) * visibility;
    }

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
        float visibility = 1.0;
        if (s.shadow_filter.w > 0.5 && li == uint(s.shadow_filter.z)) {
            if (s.shadow_filter.w > 3.5) visibility = cascade_shadow_visibility(input.world, input.world_normal);
            else visibility = shadow_visibility(input.world, input.world_normal);
        }
        linear_color += source_direct(base, metallic, roughness, shading_normal, input.world, l.eye_exposure.xyz, lights[li]) * visibility;
    }

    return float4(finish_lighting(linear_color, l.eye_exposure.w), 1.0);
}

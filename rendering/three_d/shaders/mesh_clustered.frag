#version 450

const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    vec4 position_kind;
    vec4 direction_range;
    vec4 radiance_inner;
    vec4 cone;
};

layout(location = 0) in vec4 vertex_color;
layout(location = 1) in vec3 world;
layout(location = 2) in vec3 world_normal;
layout(location = 3) in vec2 texture_uv;
layout(location = 4) in vec3 world_tangent;
layout(location = 5) in vec3 world_bitangent;
layout(location = 6) in float view_depth;

layout(set = 2, binding = 0) uniform sampler2D base_texture;
layout(set = 2, binding = 1) uniform sampler2D orm_texture;
layout(set = 2, binding = 2) uniform sampler2D emission_texture;
layout(set = 2, binding = 3) uniform sampler2D normal_texture;
layout(set = 2, binding = 4) uniform sampler2D occlusion_texture;
layout(set = 2, binding = 5) uniform sampler2D shadow_texture;

layout(set = 2, binding = 6, std430) readonly buffer LightsBuf { LightGpu lights[]; };
layout(set = 2, binding = 7, std430) readonly buffer CountsBuf { uint cluster_counts[]; };
layout(set = 2, binding = 8, std430) readonly buffer IndicesBuf { uint cluster_indices[]; };

layout(set = 3, binding = 0, std140) uniform Material {
    vec4 base_metallic;
    vec4 emission_roughness;
    vec4 maps_normal;
    vec4 surface;
    vec4 uv_rect;
} p;

layout(set = 3, binding = 1, std140) uniform ClusteredLighting {
    vec4 ambient_count;
    vec4 eye_exposure;
    vec4 screen_depth;
    vec4 grid_mode;
    vec4 log_info;
} l;

layout(set = 3, binding = 2, std140) uniform Shadow {
    mat4 mvp[4];
    vec4 direction_bias;
    vec4 shadow_filter;
    vec4 depth;
    vec4 camera_depth;
    vec4 ranges[4];
    vec4 limits;
    vec4 gradient_scales;
} s;

layout(location = 0) out vec4 output_color;

vec3 unit_safe(vec3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (isnan(largest) || isinf(largest) || largest == 0.0) return vec3(0.0);
    vec3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}

float srgb_channel(float value) {
    return value <= 0.0031308 ? 12.92 * value : 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

vec3 material_direct(vec3 base, float metallic, float roughness,
    vec3 normal, vec3 position, vec3 eye, vec3 light, vec3 radiance) {
    vec3 n = unit_safe(normal), v = unit_safe(eye - position), lvec = unit_safe(light), h = unit_safe(v + lvec);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, lvec), 0.0);
    float nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha;
    float denominator = (nh * a2 - nh) * nh + 1.0;
    float distribution = a2 / (3.14159265359 * max(denominator * denominator, 1e-12));
    float visibility = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) +
        nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    vec3 f0 = mix(vec3(0.04), base, metallic);
    float factor = pow(1.0 - vh, 5.0);
    vec3 fresnel = f0 + (vec3(1.0) - f0) * factor;
    // Fdez-Aguera analytical GGX multi-scattering energy compensation.
    vec4 r_ms = roughness * vec4(-1.0, -0.0275, -0.572, 0.022) + vec4(1.0, 0.0425, 1.04, -0.04);
    float a004 = min(r_ms.x * r_ms.x, exp2(-9.28 * nv)) * r_ms.x + r_ms.y;
    vec2 ab_ms = vec2(-1.04, 1.04) * a004 + r_ms.zw;
    float ess = clamp(ab_ms.x + ab_ms.y, 0.05, 1.0);
    vec3 ms_comp = vec3(1.0) + f0 * (1.0 / ess - 1.0);
    vec3 diffuse = (vec3(1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    return (diffuse + distribution * visibility * fresnel * ms_comp) * radiance * nl;
}

vec3 source_direct(vec3 base, float metallic, float roughness,
    vec3 normal, vec3 position, vec3 eye, LightGpu src) {
    vec3 light = src.direction_range.xyz;
    float attenuation = 1.0;
    if (src.position_kind.w > 0.5) {
        vec3 delta = src.position_kind.xyz - position;
        float distance2 = dot(delta, delta), radius2 = src.direction_range.w * src.direction_range.w;
        if (distance2 < 1e-12 || distance2 >= radius2) return vec3(0.0);
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

vec3 finish_lighting(vec3 linear_color, float exposure) {
    vec3 exposed = max(linear_color * exposure, vec3(0.0));
    vec3 mapped = exposed / (vec3(1.0) + exposed);
    return vec3(srgb_channel(mapped.x), srgb_channel(mapped.y), srgb_channel(mapped.z));
}

vec3 normal_map_direction(vec3 normal, vec3 tangent, vec3 bitangent, vec3 texel, float scale) {
    vec3 n = unit_safe(normal);
    if (scale == 0.0) return n;
    vec3 t = unit_safe(tangent);
    t = unit_safe(t - n * dot(n, t));
    vec3 b = unit_safe(cross(n, t));
    if (dot(b, unit_safe(bitangent)) < 0.0) b = -b;
    vec3 mapped = texel * 2.0 - vec3(1.0);
    mapped.x *= scale; mapped.y *= scale;
    mapped = unit_safe(mapped);
    vec3 result = unit_safe(t * mapped.x + b * mapped.y + n * mapped.z);
    if (dot(result, result) == 0.0) return n;
    return result;
}

int point_shadow_face(vec3 d) {
    vec3 a = abs(d);
    if (a.x >= a.y && a.x >= a.z) return d.x >= 0.0 ? 0 : 1;
    if (a.y >= a.z) return d.y >= 0.0 ? 2 : 3;
    return d.z >= 0.0 ? 4 : 5;
}

vec2 point_shadow_uv(vec3 d, int face) {
    vec2 pt;
    if (face == 0) pt = vec2(d.z, d.y) / abs(d.x);
    else if (face == 1) pt = vec2(-d.z, d.y) / abs(d.x);
    else if (face == 2) pt = vec2(d.x, d.z) / abs(d.y);
    else if (face == 3) pt = vec2(-d.x, d.z) / abs(d.y);
    else if (face == 4) pt = vec2(-d.x, d.y) / abs(d.z);
    else pt = vec2(d.x, d.y) / abs(d.z);
    return pt * vec2(0.5, -0.5) + vec2(0.5, 0.5);
}

vec3 point_shadow_ray(vec2 uv, int face) {
    vec2 pt = uv * vec2(2.0, -2.0) + vec2(-1.0, 1.0);
    if (face == 0) return vec3(1.0, pt.y, pt.x);
    if (face == 1) return vec3(-1.0, pt.y, -pt.x);
    if (face == 2) return vec3(pt.x, 1.0, pt.y);
    if (face == 3) return vec3(-pt.x, -1.0, pt.y);
    if (face == 4) return vec3(-pt.x, pt.y, 1.0);
    return vec3(pt.x, pt.y, -1.0);
}

float point_shadow_visibility(vec3 wpos, vec3 nrm, vec4 light_bias, vec4 shadow_filter, vec4 depth) {
    vec3 n = unit_safe(cross(dFdx(wpos), dFdy(wpos)));
    if (dot(n, n) == 0.0) n = unit_safe(nrm);
    vec3 delta = wpos - light_bias.xyz;
    float major = max(abs(delta.x), max(abs(delta.y), abs(delta.z)));
    float receiver_z = depth.x / max(major, 0.000001) - depth.y;
    if (major <= 0.000001 || receiver_z < 0.0 || receiver_z > 1.0) return 1.0;
    int face = point_shadow_face(delta);
    vec2 uv = point_shadow_uv(delta, face);
    float plane_distance = dot(n, delta);
    float bias = light_bias.w + shadow_filter.y * (1.0 - max(0.0, dot(unit_safe(nrm), unit_safe(-delta))));
    float visibility = 0.0;
    float weight_sum = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            vec2 tap = (floor(uv / shadow_filter.x) + vec2(float(x), float(y)) + vec2(0.5)) * shadow_filter.x;
            vec2 dist_tex = tap / shadow_filter.x - uv / shadow_filter.x;
            vec2 weights = max(vec2(1.5) - abs(dist_tex), vec2(0.0));
            float weight = weights.x * weights.y;
            weight_sum += weight;
            if (weight <= 0.0) continue;
            vec3 ray = point_shadow_ray(tap, face);
            int adjacent = point_shadow_face(ray);
            vec2 at = (clamp(floor(point_shadow_uv(ray, adjacent) / shadow_filter.x), vec2(0.0), vec2(1.0 / shadow_filter.x - 1.0)) + vec2(0.5)) * shadow_filter.x;
            ray = point_shadow_ray(at, adjacent);
            float denominator = dot(n, ray);
            if (abs(denominator) <= 0.000001) { visibility += weight; continue; }
            float dist = plane_distance / denominator;
            if (dist <= 0.0) { visibility += weight; continue; }
            float reference = depth.x / dist - depth.y;
            if (reference < 0.0 || reference > 1.0) { visibility += weight; continue; }
            vec2 atlas = (at + vec2(float(adjacent % 3), float(adjacent / 3))) / depth.zw;
            visibility += (reference + bias >= textureLod(shadow_texture, atlas, 0.0).r ? 1.0 : 0.0) * weight;
        }
    }
    return visibility / weight_sum;
}

vec2 cascade_gradient(vec3 pt) {
    vec3 n = unit_safe(cross(dFdx(pt), dFdy(pt)));
    if (abs(n.z) <= 0.00001) return vec2(0.0);
    return vec2(-2.0 * n.x, 2.0 * n.y) / n.z;
}

float pcss_fract(float x) { return x - floor(x); }
float pcss_contact_hardened(vec2 uv, float receiver_z, vec2 gradient, float bias,
    float texel, vec2 atlas_offset, vec2 atlas_size, float pcss_radius) {
    vec2 cell = floor(uv / texel);
    float ign = pcss_fract(52.9829189 * pcss_fract(dot(cell, vec2(0.06711056, 0.00583715))));
    float ang = 6.2831853 * ign;
    float search_r = pcss_radius * texel;
    float blocker_sum = 0.0;
    float blocker_count = 0.0;
    for (int k = 0; k < 16; ++k) {
        float r = sqrt((float(k) + 0.5) / 16.0);
        float theta = float(k) * 2.39996323 + ang;
        vec2 at = clamp(uv + vec2(cos(theta), sin(theta)) * (r * search_r), vec2(0.5 * texel), vec2(1.0 - 0.5 * texel));
        vec2 atlas = (at + atlas_offset) / atlas_size;
        float sample_d = textureLod(shadow_texture, atlas, 0.0).r;
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
        vec2 at = uv + vec2(cos(theta), sin(theta)) * (r * filter_r);
        if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) { vis += 1.0; continue; }
        vec2 atlas = (at + atlas_offset) / atlas_size;
        vis += (receiver_z + dot(gradient, at - uv) + bias >= textureLod(shadow_texture, atlas, 0.0).r) ? 1.0 : 0.0;
    }
    return vis / 16.0;
}

float cascade_sample(vec3 pt, vec2 gradient, int layer, float bias, float texel, vec2 atlas_size, float raster_bias, float pcss_radius) {
    if (pt.x < -1.0 || pt.x > 1.0 || pt.y < -1.0 || pt.y > 1.0 || pt.z < 0.0 || pt.z > 1.0) return 1.0;
    bias += max(abs(gradient.x), abs(gradient.y)) * texel * raster_bias;
    vec2 uv = vec2(pt.x * 0.5 + 0.5, 0.5 - pt.y * 0.5);
    if (pcss_radius > 0.0001) {
        return pcss_contact_hardened(uv, pt.z, gradient, bias, texel, vec2(float(layer % 2), float(layer / 2)), atlas_size, pcss_radius);
    }
    float visible = 0.0, total = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            vec2 at = (floor(uv / texel) + vec2(float(x), float(y)) + vec2(0.5)) * texel;
            vec2 weights = max(vec2(1.5) - abs((at - uv) / texel), vec2(0.0));
            float weight = weights.x * weights.y;
            total += weight;
            if (weight <= 0.0) continue;
            if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) { visible += weight; continue; }
            vec2 atlas = (at + vec2(float(layer % 2), float(layer / 2))) / atlas_size;
            visible += (pt.z + dot(gradient, at - uv) + bias >= textureLod(shadow_texture, atlas, 0.0).r ? 1.0 : 0.0) * weight;
        }
    }
    return visible / total;
}

float cascade_shadow_visibility(vec3 wpos, vec3 nrm) {
    vec3 p0 = (s.mvp[0] * vec4(wpos, 1.0)).xyz;
    vec3 p1 = (s.mvp[1] * vec4(wpos, 1.0)).xyz;
    vec3 p2 = (s.mvp[2] * vec4(wpos, 1.0)).xyz;
    vec3 p3 = (s.mvp[3] * vec4(wpos, 1.0)).xyz;
    vec2 g0 = cascade_gradient(p0);
    vec2 g1 = g0 * s.gradient_scales.y, g2 = g0 * s.gradient_scales.z, g3 = g0 * s.gradient_scales.w;
    float dist = dot(s.camera_depth, vec4(wpos, 1.0));
    if (dist < s.limits.x || dist > s.limits.y) return 1.0;
    int layer = 0;
    if (dist > s.ranges[0].y && s.limits.z > 1.5) layer = 1;
    if (dist > s.ranges[1].y && s.limits.z > 2.5) layer = 2;
    if (dist > s.ranges[2].y && s.limits.z > 3.5) layer = 3;
    vec3 pt = p0; vec2 g = g0; vec4 range = s.ranges[0];
    vec3 next_p = p1; vec2 next_g = g1; vec4 next_range = s.ranges[1];
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
        current = mix(current, next, alpha);
    }
    return current;
}

float shadow_visibility(vec3 wpos, vec3 nrm) {
    if (s.shadow_filter.w > 2.5) return point_shadow_visibility(wpos, nrm, s.direction_bias, s.shadow_filter, s.depth);
    vec4 projected = s.mvp[0] * vec4(wpos, 1.0);
    vec3 pt = projected.xyz / max(projected.w, 0.000001);
    vec3 n = unit_safe(cross(dFdx(pt), dFdy(pt)));
    vec2 gradient = vec2(0.0);
    if (abs(n.z) > 0.00001) gradient = vec2(-2.0 * n.x, 2.0 * n.y) / n.z;
    if (projected.w <= 0.000001 || pt.x < -1.0 || pt.x > 1.0 || pt.y < -1.0 || pt.y > 1.0 || pt.z < 0.0 || pt.z > 1.0) return 1.0;
    vec2 uv = vec2(pt.x * 0.5 + 0.5, 0.5 - pt.y * 0.5);
    vec3 toward_light = s.direction_bias.xyz;
    if (s.shadow_filter.w > 1.5) toward_light = unit_safe(s.direction_bias.xyz - wpos);
    float bias = s.direction_bias.w + s.shadow_filter.y * (1.0 - max(0.0, dot(unit_safe(nrm), toward_light)));
    float pcss_radius = max(0.0, -s.gradient_scales.x);
    if (pcss_radius > 0.0001) {
        return pcss_contact_hardened(uv, pt.z, gradient, bias, s.shadow_filter.x, vec2(0.0), vec2(1.0), pcss_radius);
    }
    float visibility = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            vec2 at = (floor(uv / s.shadow_filter.x) + vec2(float(x), float(y)) + vec2(0.5)) * s.shadow_filter.x;
            if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) visibility += 1.0;
            else visibility += (pt.z + dot(gradient, at - uv) + bias >= textureLod(shadow_texture, at, 0.0).r) ? 1.0 : 0.0;
        }
    }
    return visibility / 9.0;
}

void main() {
    if (p.surface.z < 0.5) { output_color = vertex_color; return; }
    int mask = int(p.maps_normal.x);
    vec2 sample_uv = p.uv_rect.xy + texture_uv * p.uv_rect.zw;
    vec3 base = p.base_metallic.xyz * vertex_color.xyz;
    float alpha = vertex_color.a;
    if ((mask & 1) != 0) {
        vec4 base_texel = texture(base_texture, sample_uv);
        base *= base_texel.rgb;
        alpha *= base_texel.a;
    }
    if (p.surface.w > 0.0 && alpha < p.surface.w) discard;
    if (p.surface.z > 1.5) {
        vec3 clamped = clamp(base, vec3(0.0), vec3(1.0));
        output_color = vec4(srgb_channel(clamped.x), srgb_channel(clamped.y), srgb_channel(clamped.z), 1.0);
        return;
    }
    vec3 orm = vec3(1.0);
    if ((mask & 2) != 0) orm = texture(orm_texture, sample_uv).rgb;
    float ao_strength = p.maps_normal.y;
    if ((mask & 16) != 0) {
        orm.x = texture(occlusion_texture, sample_uv).r;
        ao_strength = p.surface.y;
    }
    vec3 emission = p.emission_roughness.xyz;
    if ((mask & 4) != 0) emission *= texture(emission_texture, sample_uv).rgb;
    vec3 shading_normal = world_normal;
    if ((mask & 8) != 0) {
        vec3 adj_tangent = p.uv_rect.z < 0.0 ? -world_tangent : world_tangent;
        vec3 adj_bitangent = p.uv_rect.w < 0.0 ? -world_bitangent : world_bitangent;
        shading_normal = normal_map_direction(world_normal, adj_tangent, adj_bitangent,
            texture(normal_texture, sample_uv).rgb, p.maps_normal.z);
    }
    bool surface_front = gl_FrontFacing;
    if (p.surface.x < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;
    float metallic = p.base_metallic.w * orm.z;
    float roughness = max(0.045, p.emission_roughness.w * orm.y);
    float occlusion = 1.0 + ao_strength * (orm.x - 1.0);
    vec3 linear_color = l.ambient_count.xyz * occlusion * base * (1.0 - metallic) + emission;

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        float visibility = 1.0;
        if (s.shadow_filter.w > 0.5 && li == uint(s.shadow_filter.z)) {
            if (s.shadow_filter.w > 3.5) visibility = cascade_shadow_visibility(world, world_normal);
            else visibility = shadow_visibility(world, world_normal);
        }
        linear_color += source_direct(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]) * visibility;
    }

    uint cx = uint(l.grid_mode.x);
    uint cy = uint(l.grid_mode.y);
    uint cz = uint(l.grid_mode.z);
    uint tx = min(uint(max(0.0, floor(gl_FragCoord.x / l.screen_depth.x * float(cx)))), cx - 1u);
    uint ty = min(uint(max(0.0, floor(gl_FragCoord.y / l.screen_depth.y * float(cy)))), cy - 1u);
    float z_near = l.screen_depth.z;
    float z_far = l.screen_depth.w;
    float vd = clamp(view_depth, z_near, z_far);
    float norm_z = l.grid_mode.w < 0.5 ? (log(vd / z_near) / l.log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
    uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u);
    uint cid = (tz * cy + ty) * cx + tx;

    uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER);
    uint base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
    for (uint ci = 0u; ci < local_count; ++ci) {
        uint li = cluster_indices[base_idx + ci];
        float visibility = 1.0;
        if (s.shadow_filter.w > 0.5 && li == uint(s.shadow_filter.z)) {
            if (s.shadow_filter.w > 3.5) visibility = cascade_shadow_visibility(world, world_normal);
            else visibility = shadow_visibility(world, world_normal);
        }
        linear_color += source_direct(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]) * visibility;
    }

    output_color = vec4(finish_lighting(linear_color, l.eye_exposure.w), 1.0);
}

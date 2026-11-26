#version 450

const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    vec4 position_kind;
    vec4 direction_range;
    vec4 radiance_inner;
    vec4 cone;
};

struct ProbeShGpu {
    vec4 dc;
    vec4 px;
    vec4 py;
    vec4 pz;
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
layout(set = 2, binding = 9, std430) readonly buffer ProbesBuf { ProbeShGpu probes[]; };

layout(set = 3, binding = 0, std140) uniform Material {
    vec4 base_metallic;
    vec4 emission_roughness;
    vec4 maps_normal;
    vec4 surface;
    vec4 uv_rect;
    vec4 pbr_ext0;
    vec4 pbr_ext1;
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

layout(set = 3, binding = 3, std140) uniform IrradianceUniform {
    vec4 origin_nx;
    vec4 spacing_ny;
    vec4 dims_mode;
} irr;

layout(location = 0) out vec4 hdr_color;
layout(location = 1) out vec4 normal_roughness;

vec3 unit_safe(vec3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (isnan(largest) || isinf(largest) || largest == 0.0) return vec3(0.0);
    vec3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}

vec3 material_direct(vec3 base, float metallic, float roughness,
    float clearcoat, float clearcoat_roughness, float ior,
    vec3 sheen_color, float sheen_roughness,
    vec3 normal, vec3 position, vec3 eye, vec3 light, vec3 radiance) {
    vec3 n = unit_safe(normal), v = unit_safe(eye - position), lvec = unit_safe(light), h = unit_safe(v + lvec);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, lvec), 0.0);
    float nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha;
    float denominator = (nh * a2 - nh) * nh + 1.0;
    float distribution = a2 / (3.14159265359 * max(denominator * denominator, 1e-12));
    float visibility = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) +
        nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    float ior_ratio = (ior - 1.0) / max(ior + 1.0, 1e-4);
    float f0_dielectric = ior_ratio * ior_ratio;
    vec3 f0 = mix(vec3(f0_dielectric), base, metallic);
    float factor = pow(1.0 - vh, 5.0);
    vec3 fresnel = f0 + (vec3(1.0) - f0) * factor;
    vec3 diffuse = (vec3(1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    vec3 brdf = diffuse + distribution * visibility * fresnel;

    float max_sheen = max(sheen_color.x, max(sheen_color.y, sheen_color.z));
    if (max_sheen > 0.0) {
        float inv_r = 1.0 / max(sheen_roughness * sheen_roughness, 0.002);
        float sin2h = max(1.0 - nh * nh, 1e-6);
        float d_charlie = (2.0 + inv_r) * pow(sin2h, inv_r * 0.5) / (2.0 * 3.14159265359);
        float v_sheen = 1.0 / max(4.0 * (nl + nv - nl * nv), 1e-4);
        vec3 sheen_brdf = sheen_color * d_charlie * v_sheen;
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
        brdf = brdf * (1.0 - clearcoat * cc_f) + vec3(clearcoat * cc_d * cc_v * cc_f);
    }
    return brdf * radiance * nl;
}

vec3 source_direct(vec3 base, float metallic, float roughness,
    float clearcoat, float clearcoat_roughness, float ior,
    vec3 sheen_color, float sheen_roughness,
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
    return material_direct(base, metallic, roughness, clearcoat, clearcoat_roughness, ior,
        sheen_color, sheen_roughness, normal, position, eye, light, src.radiance_inner.xyz * attenuation);
}

vec3 eval_probe(uint idx, vec3 n) {
    ProbeShGpu sh = probes[idx];
    return max(sh.dc.xyz + sh.px.xyz * n.x + sh.py.xyz * n.y + sh.pz.xyz * n.z, vec3(0.0));
}

vec3 sample_irradiance(vec3 wpos, vec3 n) {
    int nx = int(irr.origin_nx.w);
    int ny = int(irr.spacing_ny.w);
    int nz = int(irr.dims_mode.x);
    vec3 f = (wpos - irr.origin_nx.xyz) / irr.spacing_ny.xyz;
    int x0 = clamp(int(floor(f.x)), 0, nx - 1);
    int y0 = clamp(int(floor(f.y)), 0, ny - 1);
    int z0 = clamp(int(floor(f.z)), 0, nz - 1);
    int x1 = min(x0 + 1, nx - 1);
    int y1 = min(y0 + 1, ny - 1);
    int z1 = min(z0 + 1, nz - 1);
    float tx = clamp(f.x - float(x0), 0.0, 1.0);
    float ty = clamp(f.y - float(y0), 0.0, 1.0);
    float tz = clamp(f.z - float(z0), 0.0, 1.0);
    vec3 c000 = eval_probe(uint((z0 * ny + y0) * nx + x0), n);
    vec3 c100 = eval_probe(uint((z0 * ny + y0) * nx + x1), n);
    vec3 c010 = eval_probe(uint((z0 * ny + y1) * nx + x0), n);
    vec3 c110 = eval_probe(uint((z0 * ny + y1) * nx + x1), n);
    vec3 c001 = eval_probe(uint((z1 * ny + y0) * nx + x0), n);
    vec3 c101 = eval_probe(uint((z1 * ny + y0) * nx + x1), n);
    vec3 c011 = eval_probe(uint((z1 * ny + y1) * nx + x0), n);
    vec3 c111 = eval_probe(uint((z1 * ny + y1) * nx + x1), n);
    vec3 c00 = mix(c000, c100, tx);
    vec3 c10 = mix(c010, c110, tx);
    vec3 c01 = mix(c001, c101, tx);
    vec3 c11 = mix(c011, c111, tx);
    return mix(mix(c00, c10, ty), mix(c01, c11, ty), tz);
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

void main() {
    float dummy_s = s.direction_bias.w + textureLod(shadow_texture, vec2(0.5), 0.0).r * 0.0;
    int mask = int(p.maps_normal.x);
    vec2 sample_uv = p.uv_rect.xy + texture_uv * p.uv_rect.zw;
    vec3 base = p.base_metallic.xyz * vertex_color.xyz;
    float alpha = vertex_color.a;
    if ((mask & 1) != 0) {
        vec4 base_texel = texture(base_texture, sample_uv);
        base *= base_texel.rgb;
        alpha *= base_texel.a;
    }
    alpha *= p.pbr_ext0.x;
    if (p.surface.w > 0.0 && alpha < p.surface.w) discard;

    float clearcoat = clamp(p.pbr_ext0.y, 0.0, 1.0);
    float clearcoat_roughness = max(0.045, p.pbr_ext0.z);
    float ior = max(1.0, p.pbr_ext0.w);
    vec3 sheen_color = max(p.pbr_ext1.xyz, vec3(0.0));
    float sheen_roughness = max(0.045, p.pbr_ext1.w);

    vec3 shading_normal = unit_safe(world_normal);
    if ((mask & 8) != 0) {
        vec3 adj_tangent = p.uv_rect.z < 0.0 ? -world_tangent : world_tangent;
        vec3 adj_bitangent = p.uv_rect.w < 0.0 ? -world_bitangent : world_bitangent;
        shading_normal = normal_map_direction(world_normal, adj_tangent, adj_bitangent,
            texture(normal_texture, sample_uv).rgb, p.maps_normal.z);
    }
    bool surface_front = gl_FrontFacing;
    if (p.surface.x < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;

    vec3 orm = vec3(1.0);
    if ((mask & 2) != 0) orm = texture(orm_texture, sample_uv).rgb;
    float ao_strength = p.maps_normal.y;
    if ((mask & 16) != 0) {
        orm.x = texture(occlusion_texture, sample_uv).r;
        ao_strength = p.surface.y;
    }
    float metallic = p.base_metallic.w * orm.z;
    float roughness = max(0.045, p.emission_roughness.w * orm.y);
    float occlusion = 1.0 + ao_strength * (orm.x - 1.0);
    vec3 emission = p.emission_roughness.xyz;
    if ((mask & 4) != 0) emission *= texture(emission_texture, sample_uv).rgb;

    if (p.surface.z < 0.5) {
        hdr_color = vec4(vertex_color.rgb, alpha + dummy_s * 0.0);
        normal_roughness = vec4(shading_normal, roughness);
        return;
    }
    if (p.surface.z > 1.5) {
        hdr_color = vec4(max(base + emission, vec3(0.0)), alpha);
        normal_roughness = vec4(shading_normal, roughness);
        return;
    }

    vec3 indirect_ambient = l.ambient_count.xyz;
    if (irr.dims_mode.y > 0.5) {
        indirect_ambient += sample_irradiance(world, shading_normal) * irr.dims_mode.z;
    }
    vec3 linear_color = indirect_ambient * occlusion * base * (1.0 - metallic) + emission;
    float max_sheen_ind = max(sheen_color.x, max(sheen_color.y, sheen_color.z));
    if (max_sheen_ind > 0.0) {
        vec3 v_dir = unit_safe(l.eye_exposure.xyz - world);
        float nv_ind = max(dot(shading_normal, v_dir), 0.0001);
        linear_color += indirect_ambient * occlusion * sheen_color * pow(1.0 - nv_ind, 2.0) * 0.35;
    }

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += source_direct(base, metallic, roughness, clearcoat, clearcoat_roughness, ior,
            sheen_color, sheen_roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]);
    }

    if (l.ambient_count.w > 0.5) {
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
            linear_color += source_direct(base, metallic, roughness, clearcoat, clearcoat_roughness, ior,
                sheen_color, sheen_roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]);
        }
    }

    hdr_color = vec4(max(linear_color, vec3(0.0)), alpha);
    normal_roughness = vec4(shading_normal, roughness);
}

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
layout(location = 3) in vec2 splat_uv;
layout(location = 4) in float view_depth;

layout(set = 2, binding = 0) uniform sampler2D splat_tex;
layout(set = 2, binding = 1) uniform sampler2D layer0_tex;
layout(set = 2, binding = 2) uniform sampler2D layer1_tex;
layout(set = 2, binding = 3) uniform sampler2D layer2_tex;
layout(set = 2, binding = 4) uniform sampler2D layer3_tex;

layout(set = 2, binding = 5, std430) readonly buffer LightsBuf { LightGpu lights[]; };
layout(set = 2, binding = 6, std430) readonly buffer CountsBuf { uint cluster_counts[]; };
layout(set = 2, binding = 7, std430) readonly buffer IndicesBuf { uint cluster_indices[]; };
layout(set = 2, binding = 8, std430) readonly buffer ProbesBuf { ProbeShGpu probes[]; };

layout(set = 3, binding = 0, std140) uniform TerrainMatUniform {
    vec4 layer_albedo[4];
    vec4 layer_pbr[4];
    vec4 terrain_info0;
    vec4 terrain_info1;
} tm;

layout(set = 3, binding = 1, std140) uniform ClusteredLighting {
    vec4 ambient_count;
    vec4 eye_exposure;
    vec4 screen_depth;
    vec4 grid_mode;
    vec4 log_info;
} l;

layout(set = 3, binding = 2, std140) uniform IrradianceUniform {
    vec4 origin_nx;
    vec4 spacing_ny;
    vec4 dims_mode;
} irr;

layout(location = 0) out vec4 hdr_color;
layout(location = 1) out vec4 normal_roughness;

vec3 unit_safe(vec3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (isnan(largest) || isinf(largest) || largest == 0.0) return vec3(0.0, 1.0, 0.0);
    vec3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}

vec3 eval_probe(uint idx, vec3 n) {
    ProbeShGpu sh = probes[idx];
    return max(sh.dc.xyz + sh.px.xyz * n.x + sh.py.xyz * n.y + sh.pz.xyz * n.z, vec3(0.0));
}

vec3 sample_irradiance(vec3 wpos, vec3 n) {
    int nx = int(irr.origin_nx.w), ny = int(irr.spacing_ny.w), nz = int(irr.dims_mode.x);
    if (nx <= 0 || ny <= 0 || nz <= 0) return vec3(0.0);
    vec3 rel = (wpos - irr.origin_nx.xyz) / max(irr.spacing_ny.xyz, vec3(1e-4));
    float fx = clamp(rel.x, 0.0, float(max(nx - 1, 0))), fy = clamp(rel.y, 0.0, float(max(ny - 1, 0))), fz = clamp(rel.z, 0.0, float(max(nz - 1, 0)));
    int x0 = min(int(floor(fx)), max(nx - 1, 0)), y0 = min(int(floor(fy)), max(ny - 1, 0)), z0 = min(int(floor(fz)), max(nz - 1, 0));
    int x1 = min(x0 + 1, max(nx - 1, 0)), y1 = min(y0 + 1, max(ny - 1, 0)), z1 = min(z0 + 1, max(nz - 1, 0));
    float tx = fx - float(x0), ty = fy - float(y0), tz = fz - float(z0);
    uint nxy = uint(nx * ny), ux = uint(nx);
    vec3 c000 = eval_probe(uint(z0) * nxy + uint(y0) * ux + uint(x0), n), c100 = eval_probe(uint(z0) * nxy + uint(y0) * ux + uint(x1), n);
    vec3 c010 = eval_probe(uint(z0) * nxy + uint(y1) * ux + uint(x0), n), c110 = eval_probe(uint(z0) * nxy + uint(y1) * ux + uint(x1), n);
    vec3 c001 = eval_probe(uint(z1) * nxy + uint(y0) * ux + uint(x0), n), c101 = eval_probe(uint(z1) * nxy + uint(y0) * ux + uint(x1), n);
    vec3 c011 = eval_probe(uint(z1) * nxy + uint(y1) * ux + uint(x0), n), c111 = eval_probe(uint(z1) * nxy + uint(y1) * ux + uint(x1), n);
    vec3 c00 = mix(c000, c100, tx), c10 = mix(c010, c110, tx), c01 = mix(c001, c101, tx), c11 = mix(c011, c111, tx);
    return mix(mix(c00, c10, ty), mix(c01, c11, ty), tz);
}

vec3 pbr_direct(vec3 base, float metallic, float roughness, vec3 normal, vec3 position, vec3 eye, vec3 light, vec3 radiance) {
    vec3 n = unit_safe(normal), v = unit_safe(eye - position), lvec = unit_safe(light), h = unit_safe(v + lvec);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, lvec), 0.0), nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha, denom = (nh * a2 - nh) * nh + 1.0;
    float d = a2 / (3.14159265359 * max(denom * denom, 1e-12));
    float vis = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) + nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    vec3 f0 = mix(vec3(0.04), base, metallic), f = f0 + (vec3(1.0) - f0) * pow(1.0 - vh, 5.0);
    vec3 diff = (vec3(1.0) - f) * (1.0 - metallic) * base / 3.14159265359;
    return (diff + d * vis * f) * radiance * nl;
}

vec3 light_contrib(vec3 base, float metallic, float roughness, vec3 normal, vec3 position, vec3 eye, LightGpu src) {
    vec3 light = src.direction_range.xyz;
    float atten = 1.0;
    if (src.position_kind.w > 0.5) {
        vec3 delta = src.position_kind.xyz - position;
        float d2 = dot(delta, delta), r2 = src.direction_range.w * src.direction_range.w;
        if (d2 < 1e-12 || d2 >= r2) return vec3(0.0);
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

vec3 aces_srgb(vec3 hdr_rgb, float exposure) {
    vec3 c = max(hdr_rgb * exposure, vec3(0.0));
    vec3 mapped = clamp((c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14), 0.0, 1.0);
    return pow(mapped, vec3(1.0 / 2.2));
}

void main() {
    vec2 suv = tm.terrain_info1.y > 0.5 ? clamp((world.xz - tm.terrain_info0.xy) * tm.terrain_info0.zw, vec2(0.0), vec2(1.0)) : splat_uv;
    vec4 w = max(texture(splat_tex, suv), vec4(0.0));
    vec3 a0 = tm.layer_albedo[0].rgb * texture(layer0_tex, world.xz * tm.layer_albedo[0].w).rgb;
    vec3 a1 = tm.layer_albedo[1].rgb * texture(layer1_tex, world.xz * tm.layer_albedo[1].w).rgb;
    vec3 a2 = tm.layer_albedo[2].rgb * texture(layer2_tex, world.xz * tm.layer_albedo[2].w).rgb;
    vec3 a3 = tm.layer_albedo[3].rgb * texture(layer3_tex, world.xz * tm.layer_albedo[3].w).rgb;

    if (tm.terrain_info1.x > 0.0) {
        float sharpness = tm.terrain_info1.x;
        vec4 h = vec4(
            dot(a0, vec3(0.3, 0.6, 0.1)) + tm.layer_pbr[0].z,
            dot(a1, vec3(0.3, 0.6, 0.1)) + tm.layer_pbr[1].z,
            dot(a2, vec3(0.3, 0.6, 0.1)) + tm.layer_pbr[2].z,
            dot(a3, vec3(0.3, 0.6, 0.1)) + tm.layer_pbr[3].z
        );
        vec4 weighted = w * (0.25 + h * 0.75);
        float max_w = max(max(weighted.x, weighted.y), max(weighted.z, weighted.w));
        float depth = max(0.02, 0.25 / (1.0 + sharpness * 0.5));
        w = max(weighted - (max_w - depth), vec4(0.0));
    }

    float wsum = w.x + w.y + w.z + w.w;
    w = (wsum <= 1e-5) ? vec4(1.0, 0.0, 0.0, 0.0) : (w / wsum);

    vec3 base = (a0 * w.x + a1 * w.y + a2 * w.z + a3 * w.w) * vertex_color.rgb;
    float roughness = clamp(tm.layer_pbr[0].x * w.x + tm.layer_pbr[1].x * w.y + tm.layer_pbr[2].x * w.z + tm.layer_pbr[3].x * w.w, 0.045, 1.0);
    float metallic = clamp(tm.layer_pbr[0].y * w.x + tm.layer_pbr[1].y * w.y + tm.layer_pbr[2].y * w.z + tm.layer_pbr[3].y * w.w, 0.0, 1.0);
    vec3 shading_normal = unit_safe(world_normal);

    vec3 indirect_ambient = l.ambient_count.xyz;
    if (irr.dims_mode.y > 0.5) indirect_ambient += sample_irradiance(world, shading_normal) * irr.dims_mode.z;
    vec3 linear_color = indirect_ambient * base * (1.0 - metallic);

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += light_contrib(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]);
    }
    if (l.ambient_count.w > 0.5) {
        uint cx = uint(l.grid_mode.x), cy = uint(l.grid_mode.y), cz = uint(l.grid_mode.z);
        uint tx = min(uint(max(0.0, floor(gl_FragCoord.x / l.screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(gl_FragCoord.y / l.screen_depth.y * float(cy)))), cy - 1u);
        float z_near = l.screen_depth.z, z_far = l.screen_depth.w, vd = clamp(view_depth, z_near, z_far);
        float norm_z = l.grid_mode.w < 0.5 ? (log(vd / z_near) / l.log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u);
        uint cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER), base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += light_contrib(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]);
        }
    }

    hdr_color = (tm.terrain_info1.w > 0.5)
        ? vec4(aces_srgb(linear_color, max(tm.terrain_info1.z, 0.01)), 1.0)
        : vec4(max(linear_color, vec3(0.0)), 1.0);
    normal_roughness = vec4(shading_normal, roughness);
}

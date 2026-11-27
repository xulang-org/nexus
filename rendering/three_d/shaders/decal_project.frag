#version 450

const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu { vec4 position_kind; vec4 direction_range; vec4 radiance_inner; vec4 cone; };
struct ProbeShGpu { vec4 dc; vec4 px; vec4 py; vec4 pz; };

layout(set = 2, binding = 0) uniform sampler2D albedo_tex;
layout(set = 2, binding = 1) uniform sampler2D scene_depth_tex;
layout(set = 2, binding = 2) uniform sampler2D scene_normal_tex;

layout(set = 2, binding = 3, std430) readonly buffer LightsBuf { LightGpu lights[]; };
layout(set = 2, binding = 4, std430) readonly buffer CountsBuf { uint cluster_counts[]; };
layout(set = 2, binding = 5, std430) readonly buffer IndicesBuf { uint cluster_indices[]; };
layout(set = 2, binding = 6, std430) readonly buffer ProbesBuf { ProbeShGpu probes[]; };

layout(set = 3, binding = 0, std140) uniform DecalFragUniform {
    mat4 inv_vp;
    mat4 inv_model;
    vec4 decal_up_angle;
    vec4 albedo_opacity;
    vec4 emission_rough;
    vec4 meta0;
    vec4 viewport_shape;
    vec4 view_row2;
} u;

layout(set = 3, binding = 1, std140) uniform ClusteredLighting {
    vec4 ambient_count; vec4 eye_exposure; vec4 screen_depth; vec4 grid_mode; vec4 log_info;
} l;

layout(set = 3, binding = 2, std140) uniform IrradianceUniform {
    vec4 origin_nx; vec4 spacing_ny; vec4 dims_mode;
} irr;

layout(location = 0) out vec4 output_color;

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

void main() {
    vec2 screen_uv = clamp(gl_FragCoord.xy / max(u.viewport_shape.xy, vec2(1.0)), vec2(0.0), vec2(1.0));
    float scene_d = textureLod(scene_depth_tex, screen_uv, 0.0).r;
    if (scene_d <= 1e-6) discard;

    float ndc_x = screen_uv.x * 2.0 - 1.0;
    float ndc_y = 1.0 - screen_uv.y * 2.0;
    vec4 wp4 = u.inv_vp * vec4(ndc_x, ndc_y, scene_d, 1.0);
    vec3 world_pos = wp4.xyz / max(wp4.w, 1e-6);

    vec3 local = (u.inv_model * vec4(world_pos, 1.0)).xyz;
    if (abs(local.x) > 0.5 || abs(local.y) > 0.5 || abs(local.z) > 0.5) discard;

    vec2 duv = vec2(local.x + 0.5, local.z + 0.5);
    vec3 scene_n_raw = textureLod(scene_normal_tex, screen_uv, 0.0).xyz;
    vec3 decal_up = unit_safe(u.decal_up_angle.xyz);
    vec3 n = length(scene_n_raw) > 1e-4 ? unit_safe(scene_n_raw) : decal_up;

    float angle_min = u.decal_up_angle.w, afade = 1.0;
    if (angle_min > 0.0) {
        float ndot = abs(dot(n, decal_up));
        afade = smoothstep(angle_min, min(angle_min + 0.15, 0.999), ndot);
        if (afade <= 1e-4) discard;
    }

    float edge_fade = u.meta0.w, yfade = 1.0;
    if (edge_fade > 0.0) {
        yfade = 1.0 - smoothstep(max(0.0, 0.5 - edge_fade), 0.5, abs(local.y));
        if (yfade <= 1e-4) discard;
    }

    int smode = int(u.meta0.z + 0.5);
    float shape_a = 1.0;
    vec2 centered = duv * 2.0 - 1.0;
    float r2 = dot(centered, centered);
    if (smode == 1) shape_a = pow(clamp(1.0 - r2, 0.0, 1.0), max(u.viewport_shape.w, 0.25));
    else if (smode == 2) {
        float r = sqrt(r2), inner = clamp(u.viewport_shape.z, 0.05, 0.9);
        shape_a = smoothstep(inner, inner + 0.10, r) * (1.0 - smoothstep(0.88, 1.0, r));
    }

    vec4 texel = texture(albedo_tex, duv);
    float alpha = clamp(u.albedo_opacity.w * texel.a * shape_a * afade * yfade, 0.0, 1.0);
    if (alpha <= 1e-4) discard;

    vec3 base = u.albedo_opacity.rgb * texel.rgb;
    vec3 emission = u.emission_rough.rgb;
    int bmode = int(u.meta0.y + 0.5);
    if (bmode == 1) { output_color = vec4((base + emission) * alpha, 0.0); return; }
    if (bmode == 2) { output_color = vec4(base * 0.15 * alpha, alpha); return; }

    float roughness = max(0.045, u.emission_rough.w), metallic = clamp(u.meta0.x, 0.0, 1.0);
    vec3 indirect_ambient = l.ambient_count.xyz;
    if (irr.dims_mode.y > 0.5) indirect_ambient += sample_irradiance(world_pos, n) * irr.dims_mode.z;
    vec3 linear_color = indirect_ambient * base * (1.0 - metallic) + emission;

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += light_contrib(base, metallic, roughness, n, world_pos, l.eye_exposure.xyz, lights[li]);
    }
    if (l.ambient_count.w > 0.5) {
        uint cx = uint(l.grid_mode.x), cy = uint(l.grid_mode.y), cz = uint(l.grid_mode.z);
        uint tx = min(uint(max(0.0, floor(gl_FragCoord.x / l.screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(gl_FragCoord.y / l.screen_depth.y * float(cy)))), cy - 1u);
        float z_near = l.screen_depth.z, z_far = l.screen_depth.w;
        float view_depth = -(dot(u.view_row2.xyz, world_pos) + u.view_row2.w);
        float vd = clamp(view_depth, z_near, z_far);
        float norm_z = l.grid_mode.w < 0.5 ? (log(vd / z_near) / l.log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u), cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER), base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += light_contrib(base, metallic, roughness, n, world_pos, l.eye_exposure.xyz, lights[li]);
        }
    }

    output_color = vec4(max(linear_color, vec3(0.0)) * alpha, alpha);
}

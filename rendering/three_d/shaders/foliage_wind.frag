#version 450

const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu { vec4 position_kind; vec4 direction_range; vec4 radiance_inner; vec4 cone; };
struct ProbeShGpu { vec4 dc; vec4 px; vec4 py; vec4 pz; };

layout(location = 0) in vec4 vertex_color;
layout(location = 1) in vec3 world;
layout(location = 2) in vec3 world_normal;
layout(location = 3) in vec2 texture_uv;
layout(location = 4) in vec3 instance_tint;
layout(location = 5) in float height_frac;
layout(location = 6) in float fade;
layout(location = 7) in float view_depth;

layout(set = 2, binding = 0) uniform sampler2D albedo_tex;
layout(set = 2, binding = 1, std430) readonly buffer LightsBuf { LightGpu lights[]; };
layout(set = 2, binding = 2, std430) readonly buffer CountsBuf { uint cluster_counts[]; };
layout(set = 2, binding = 3, std430) readonly buffer IndicesBuf { uint cluster_indices[]; };
layout(set = 2, binding = 4, std430) readonly buffer ProbesBuf { ProbeShGpu probes[]; };

layout(set = 3, binding = 0, std140) uniform FoliageMatUniform {
    vec4 base_rough;
    vec4 tip_sss;
    vec4 params;
} fm_u;

layout(set = 3, binding = 1, std140) uniform ClusteredLighting {
    vec4 ambient_count; vec4 eye_exposure; vec4 screen_depth; vec4 grid_mode; vec4 log_info;
} l;

layout(set = 3, binding = 2, std140) uniform IrradianceUniform {
    vec4 origin_nx; vec4 spacing_ny; vec4 dims_mode;
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

vec3 foliage_light(vec3 base, float roughness, float translucency, float h_frac,
    vec3 normal, vec3 position, vec3 eye, LightGpu src) {
    vec3 ldir = src.direction_range.xyz;
    float atten = 1.0;
    if (src.position_kind.w > 0.5) {
        vec3 delta = src.position_kind.xyz - position;
        float d2 = dot(delta, delta), r2 = src.direction_range.w * src.direction_range.w;
        if (d2 < 1e-12 || d2 >= r2) return vec3(0.0);
        ldir = delta / sqrt(d2);
        float rel2 = d2 / r2, edge = max(0.0, 1.0 - rel2 * rel2);
        atten = edge * edge / max(d2, 0.0001);
        if (src.position_kind.w > 1.5) {
            float cos_a = dot(src.direction_range.xyz, -ldir);
            float t = clamp((cos_a - src.cone.x) / max(src.radiance_inner.w - src.cone.x, 1e-6), 0.0, 1.0);
            atten *= t * t * (3.0 - 2.0 * t);
        }
    }
    vec3 n = unit_safe(normal), v = unit_safe(eye - position), lvec = unit_safe(ldir), h = unit_safe(v + lvec);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, lvec), 0.0), nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha, denom = (nh * a2 - nh) * nh + 1.0;
    float d = a2 / (3.14159265359 * max(denom * denom, 1e-12));
    float vis = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) + nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    vec3 f = vec3(0.04) + vec3(0.96) * pow(1.0 - vh, 5.0);
    vec3 diff = (vec3(1.0) - f) * base / 3.14159265359;
    vec3 direct = (diff + d * vis * f) * src.radiance_inner.xyz * atten * nl;
    float back_dot = clamp(dot(v, -lvec), 0.0, 1.0);
    float sss = pow(back_dot, 2.2) * translucency * (0.35 + 0.65 * h_frac);
    vec3 translucent = base * src.radiance_inner.xyz * atten * sss * 0.45;
    return direct + translucent;
}

float bayer4x4(uvec2 pt) {
    uint idx = (pt.y & 3u) * 4u + (pt.x & 3u);
    float tbl[16] = float[16](
        0.0/16.0, 8.0/16.0, 2.0/16.0, 10.0/16.0,
       12.0/16.0, 4.0/16.0, 14.0/16.0, 6.0/16.0,
        3.0/16.0, 11.0/16.0, 1.0/16.0, 9.0/16.0,
       15.0/16.0, 7.0/16.0, 13.0/16.0, 5.0/16.0
    );
    return tbl[idx];
}

vec3 aces_srgb(vec3 hdr_rgb, float exposure) {
    vec3 c = max(hdr_rgb * exposure, vec3(0.0));
    vec3 mapped = clamp((c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14), 0.0, 1.0);
    return pow(mapped, vec3(1.0 / 2.2));
}

void main() {
    if (fade <= 0.001) discard;
    if (fm_u.params.z > 0.5 && fade < 0.999) {
        if (fade < bayer4x4(uvec2(gl_FragCoord.xy))) discard;
    }

    vec4 texel = texture(albedo_tex, texture_uv);
    float alpha = texel.a * vertex_color.a;
    if (fm_u.params.x > 0.0 && alpha < fm_u.params.x) discard;

    vec3 gradient_tint = mix(fm_u.base_rough.rgb, fm_u.tip_sss.rgb, clamp(height_frac, 0.0, 1.0));
    float ao = mix(fm_u.params.y, 1.0, clamp(height_frac, 0.0, 1.0));
    vec3 base = texel.rgb * vertex_color.rgb * instance_tint * gradient_tint * ao;
    float roughness = clamp(fm_u.base_rough.w, 0.045, 1.0);
    float translucency = max(fm_u.tip_sss.w, 0.0);

    vec3 n = unit_safe(world_normal);
    if (!gl_FrontFacing) n = -n;

    vec3 indirect_ambient = l.ambient_count.xyz;
    if (irr.dims_mode.y > 0.5) indirect_ambient += sample_irradiance(world, n) * irr.dims_mode.z;
    vec3 linear_color = indirect_ambient * base;

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += foliage_light(base, roughness, translucency, height_frac, n, world, l.eye_exposure.xyz, lights[li]);
    }
    if (l.ambient_count.w > 0.5) {
        uint cx = uint(l.grid_mode.x), cy = uint(l.grid_mode.y), cz = uint(l.grid_mode.z);
        uint tx = min(uint(max(0.0, floor(gl_FragCoord.x / l.screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(gl_FragCoord.y / l.screen_depth.y * float(cy)))), cy - 1u);
        float z_near = l.screen_depth.z, z_far = l.screen_depth.w, vd = clamp(view_depth, z_near, z_far);
        float norm_z = l.grid_mode.w < 0.5 ? (log(vd / z_near) / l.log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u), cid = (tz * cy + ty) * cx + tx;
        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER), base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += foliage_light(base, roughness, translucency, height_frac, n, world, l.eye_exposure.xyz, lights[li]);
        }
    }

    hdr_color = (fm_u.params.w > 0.5)
        ? vec4(aces_srgb(linear_color, l.eye_exposure.w), 1.0)
        : vec4(max(linear_color, vec3(0.0)), 1.0);
    normal_roughness = vec4(n, roughness);
}

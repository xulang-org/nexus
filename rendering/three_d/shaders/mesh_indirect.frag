#version 450

const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    vec4 position_kind;
    vec4 direction_range;
    vec4 radiance_inner;
    vec4 cone;
};

struct MaterialGpu {
    vec4 base_metallic;
    vec4 emission_roughness;
    vec4 maps_normal;
    vec4 surface;
    vec4 uv_rect;
};

layout(location = 0) in vec4 vertex_color;
layout(location = 1) in vec3 world;
layout(location = 2) in vec3 world_normal;
layout(location = 3) in vec2 texture_uv;
layout(location = 4) in vec3 world_tangent;
layout(location = 5) in vec3 world_bitangent;
layout(location = 6) in float view_depth;
layout(location = 7) flat in uint material_id;
layout(location = 8) flat in float orientation;

layout(set = 2, binding = 0, std430) readonly buffer MaterialsBuf { MaterialGpu materials[]; };
layout(set = 2, binding = 1, std430) readonly buffer LightsBuf { LightGpu lights[]; };
layout(set = 2, binding = 2, std430) readonly buffer CountsBuf { uint cluster_counts[]; };
layout(set = 2, binding = 3, std430) readonly buffer IndicesBuf { uint cluster_indices[]; };

layout(set = 3, binding = 0, std140) uniform ClusteredLighting {
    vec4 ambient_count;
    vec4 eye_exposure;
    vec4 screen_depth;
    vec4 grid_mode;
    vec4 log_info;
} l;

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
    vec3 diffuse = (vec3(1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    return (diffuse + distribution * visibility * fresnel) * radiance * nl;
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

void main() {
    MaterialGpu p = materials[material_id];
    if (p.surface.z < 0.5) { output_color = vertex_color; return; }
    vec3 base = p.base_metallic.xyz * vertex_color.xyz;
    float alpha = vertex_color.a;
    if (p.surface.w > 0.0 && alpha < p.surface.w) discard;
    if (p.surface.z > 1.5) {
        vec3 clamped = clamp(base, vec3(0.0), vec3(1.0));
        output_color = vec4(srgb_channel(clamped.x), srgb_channel(clamped.y), srgb_channel(clamped.z), 1.0);
        return;
    }

    vec3 shading_normal = world_normal;
    bool surface_front = gl_FrontFacing;
    if (orientation < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;

    float metallic = p.base_metallic.w;
    float roughness = max(0.045, p.emission_roughness.w);
    vec3 linear_color = l.ambient_count.xyz * base * (1.0 - metallic) + p.emission_roughness.xyz;

    uint total_clusters = uint(l.grid_mode.x) * uint(l.grid_mode.y) * uint(l.grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += source_direct(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]);
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
            linear_color += source_direct(base, metallic, roughness, shading_normal, world, l.eye_exposure.xyz, lights[li]);
        }
    }

    output_color = vec4(finish_lighting(linear_color, l.eye_exposure.w), 1.0);
}

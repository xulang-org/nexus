static const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    float4 position_kind;
    float4 direction_range;
    float4 radiance_inner;
    float4 cone;
};

struct MaterialGpu {
    float4 base_metallic;
    float4 emission_roughness;
    float4 maps_normal;
    float4 surface;
    float4 uv_rect;
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
    nointerpolation uint material_id : TEXCOORD7;
    nointerpolation float orientation : TEXCOORD8;
};

StructuredBuffer<MaterialGpu> materials : register(t0, space2);
StructuredBuffer<LightGpu> lights : register(t1, space2);
StructuredBuffer<uint> cluster_counts : register(t2, space2);
StructuredBuffer<uint> cluster_indices : register(t3, space2);

cbuffer LightingBlock : register(b0, space3) {
    float4 ambient_count;
    float4 eye_exposure;
    float4 screen_depth;
    float4 grid_mode;
    float4 log_info;
};

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
    float3 diffuse = (float3(1.0, 1.0, 1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    return (diffuse + distribution * visibility * fresnel) * radiance * nl;
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

float4 main(Input input, bool is_front : SV_IsFrontFace) : SV_Target0 {
    MaterialGpu p = materials[input.material_id];
    if (p.surface.z < 0.5) return input.vertex_color;
    float3 base = p.base_metallic.xyz * input.vertex_color.xyz;
    float alpha = input.vertex_color.a;
    if (p.surface.w > 0.0) clip(alpha - p.surface.w);
    if (p.surface.z > 1.5) {
        float3 clamped = saturate(base);
        return float4(srgb_channel(clamped.x), srgb_channel(clamped.y), srgb_channel(clamped.z), 1.0);
    }

    float3 shading_normal = input.world_normal;
    bool surface_front = is_front;
    if (input.orientation < 0.0) surface_front = !surface_front;
    if (p.maps_normal.w == 1.0 && !surface_front) shading_normal = -shading_normal;

    float metallic = p.base_metallic.w;
    float roughness = max(0.045, p.emission_roughness.w);
    float3 linear_color = ambient_count.xyz * base * (1.0 - metallic) + p.emission_roughness.xyz;

    uint total_clusters = uint(grid_mode.x) * uint(grid_mode.y) * uint(grid_mode.z);
    uint dir_count = min(cluster_counts[total_clusters], MAX_LIGHTS_PER_CLUSTER);
    for (uint di = 0u; di < dir_count; ++di) {
        uint li = cluster_indices[total_clusters * MAX_LIGHTS_PER_CLUSTER + di];
        linear_color += source_direct(base, metallic, roughness, shading_normal, input.world, eye_exposure.xyz, lights[li]);
    }

    if (ambient_count.w > 0.5) {
        uint cx = uint(grid_mode.x);
        uint cy = uint(grid_mode.y);
        uint cz = uint(grid_mode.z);
        uint tx = min(uint(max(0.0, floor(input.position.x / screen_depth.x * float(cx)))), cx - 1u);
        uint ty = min(uint(max(0.0, floor(input.position.y / screen_depth.y * float(cy)))), cy - 1u);
        float z_near = screen_depth.z;
        float z_far = screen_depth.w;
        float vd = clamp(input.view_depth, z_near, z_far);
        float norm_z = grid_mode.w < 0.5 ? (log(vd / z_near) / log_info.x) : ((vd - z_near) / max(z_far - z_near, 1e-6));
        uint tz = min(uint(max(0.0, floor(norm_z * float(cz)))), cz - 1u);
        uint cid = (tz * cy + ty) * cx + tx;

        uint local_count = min(cluster_counts[cid], MAX_LIGHTS_PER_CLUSTER);
        uint base_idx = cid * MAX_LIGHTS_PER_CLUSTER;
        for (uint ci = 0u; ci < local_count; ++ci) {
            uint li = cluster_indices[base_idx + ci];
            linear_color += source_direct(base, metallic, roughness, shading_normal, input.world, eye_exposure.xyz, lights[li]);
        }
    }

    return float4(finish_lighting(linear_color, eye_exposure.w), 1.0);
}

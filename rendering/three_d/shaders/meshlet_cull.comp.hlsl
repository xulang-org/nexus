struct MeshletGpu {
    float4 bound_sphere;
    float4 cone;
    uint4 info;
};

struct MeshletInstanceGpu {
    column_major float4x4 model;
    column_major float4x4 normals;
    float4 scale_info;
    float4 base_metallic;
    float4 emission_roughness;
    float4 maps_normal;
    float4 surface;
    float4 uv_rect;
};

struct IndexedIndirectCmd {
    uint num_indices;
    uint num_instances;
    uint first_index;
    int vertex_offset;
    uint first_instance;
};

cbuffer CullMeshletParams : register(b0, space2) {
    column_major float4x4 view_proj;
    float4 eye_info;
    float4 hiz_info;
    float4 mip_sizes[8];
};

Texture2D<float> hiz0 : register(t0, space0);
Texture2D<float> hiz1 : register(t1, space0);
Texture2D<float> hiz2 : register(t2, space0);
Texture2D<float> hiz3 : register(t3, space0);
Texture2D<float> hiz4 : register(t4, space0);
Texture2D<float> hiz5 : register(t5, space0);
Texture2D<float> hiz6 : register(t6, space0);
Texture2D<float> hiz7 : register(t7, space0);

SamplerState s0 : register(s0, space0);
SamplerState s1 : register(s1, space0);
SamplerState s2 : register(s2, space0);
SamplerState s3 : register(s3, space0);
SamplerState s4 : register(s4, space0);
SamplerState s5 : register(s5, space0);
SamplerState s6 : register(s6, space0);
SamplerState s7 : register(s7, space0);

StructuredBuffer<MeshletGpu> meshlets : register(t8, space0);
StructuredBuffer<MeshletInstanceGpu> instances : register(t9, space0);
RWStructuredBuffer<IndexedIndirectCmd> commands : register(u0, space1);
RWStructuredBuffer<uint> results : register(u1, space1);

float sample_hiz_level(int lvl, float2 uv) {
    if (lvl == 0) return hiz0.SampleLevel(s0, uv, 0.0).r;
    if (lvl == 1) return hiz1.SampleLevel(s1, uv, 0.0).r;
    if (lvl == 2) return hiz2.SampleLevel(s2, uv, 0.0).r;
    if (lvl == 3) return hiz3.SampleLevel(s3, uv, 0.0).r;
    if (lvl == 4) return hiz4.SampleLevel(s4, uv, 0.0).r;
    if (lvl == 5) return hiz5.SampleLevel(s5, uv, 0.0).r;
    if (lvl == 6) return hiz6.SampleLevel(s6, uv, 0.0).r;
    return hiz7.SampleLevel(s7, uv, 0.0).r;
}

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint count = uint(eye_info.w);
    if (gid >= count) return;

    MeshletGpu m = meshlets[gid];
    MeshletInstanceGpu inst = instances[m.info.x];

    float3 center_w = mul(inst.model, float4(m.bound_sphere.xyz, 1.0)).xyz;
    float radius_w = m.bound_sphere.w * max(inst.scale_info.x, 1e-4);

    float3 bmin = center_w - float3(radius_w, radius_w, radius_w);
    float3 bmax = center_w + float3(radius_w, radius_w, radius_w);
    uint out_left = 1u, out_right = 1u, out_bottom = 1u, out_top = 1u;
    uint out_far = 1u, out_near = 1u, all_behind = 1u, any_near_straddle = 0u;
    float min_nx = 1e30, max_nx = -1e30, min_ny = 1e30, max_ny = -1e30, max_nz = -1e30;

    for (uint corner = 0u; corner < 8u; ++corner) {
        float3 p = float3(
            (corner & 1u) != 0u ? bmax.x : bmin.x,
            (corner & 2u) != 0u ? bmax.y : bmin.y,
            (corner & 4u) != 0u ? bmax.z : bmin.z
        );
        float4 c = mul(view_proj, float4(p, 1.0));
        if (c.x + c.w >= 0.0) out_left = 0u;
        if (-c.x + c.w >= 0.0) out_right = 0u;
        if (c.y + c.w >= 0.0) out_bottom = 0u;
        if (-c.y + c.w >= 0.0) out_top = 0u;
        if (c.z >= 0.0) out_far = 0u;
        if (c.w - c.z >= 0.0) out_near = 0u;
        if (c.w > 0.0) all_behind = 0u;
        if (c.w <= 1e-5) {
            any_near_straddle = 1u;
        } else {
            float inv_w = 1.0 / c.w;
            float nx = c.x * inv_w, ny = c.y * inv_w, nz = c.z * inv_w;
            min_nx = min(min_nx, nx); max_nx = max(max_nx, nx);
            min_ny = min(min_ny, ny); max_ny = max(max_ny, ny);
            max_nz = max(max_nz, nz);
        }
    }

    if ((out_left | out_right | out_bottom | out_top | out_far | out_near | all_behind) != 0u) {
        commands[gid].num_indices = 0u; commands[gid].num_instances = 0u;
        commands[gid].first_index = m.info.y; commands[gid].vertex_offset = 0; commands[gid].first_instance = gid;
        results[gid] = 2u;
        return;
    }

    if (hiz_info.w > 0.5 && m.cone.w <= 1.5 && inst.maps_normal.w < 0.5 && any_near_straddle == 0u) {
        float3 axis_w = normalize(mul(inst.normals, float4(m.cone.xyz, 0.0)).xyz);
        if (isfinite(axis_w.x) && isfinite(axis_w.y) && isfinite(axis_w.z)) {
            float3 view_vec = center_w - eye_info.xyz;
            float dist = length(view_vec);
            if (dist > radius_w + 1e-4) {
                float3 vdir = view_vec / dist;
                if (dot(vdir, axis_w) >= m.cone.w + radius_w / dist) {
                    commands[gid].num_indices = 0u; commands[gid].num_instances = 0u;
                    commands[gid].first_index = m.info.y; commands[gid].vertex_offset = 0; commands[gid].first_instance = gid;
                    results[gid] = 3u;
                    return;
                }
            }
        }
    }

    if (hiz_info.x > 0.5 && any_near_straddle == 0u && max_nz <= 1.0) {
        int levels = clamp(int(hiz_info.y), 1, 8);
        float u0 = clamp(min_nx * 0.5 + 0.5, 0.0, 1.0);
        float u1 = clamp(max_nx * 0.5 + 0.5, 0.0, 1.0);
        float v0 = clamp(0.5 - max_ny * 0.5, 0.0, 1.0);
        float v1 = clamp(0.5 - min_ny * 0.5, 0.0, 1.0);

        int chosen = levels - 1;
        for (int k = 0; k < levels; ++k) {
            float mw = mip_sizes[k].x, mh = mip_sizes[k].y;
            if ((u1 - u0) * mw <= 3.0 && (v1 - v0) * mh <= 3.0) { chosen = k; break; }
        }
        float mw = mip_sizes[chosen].x, mh = mip_sizes[chosen].y;
        int tx0 = clamp(int(floor(u0 * mw)), 0, int(mw) - 1);
        int tx1 = clamp(int(floor(max(u1 * mw - 1e-5, u0 * mw))), tx0, int(mw) - 1);
        int ty0 = clamp(int(floor(v0 * mh)), 0, int(mh) - 1);
        int ty1 = clamp(int(floor(max(v1 * mh - 1e-5, v0 * mh))), ty0, int(mh) - 1);

        float hiz_min = 1.0;
        float2 inv_m = float2(1.0 / mw, 1.0 / mh);
        int max_x = min(tx1, tx0 + 15), max_y = min(ty1, ty0 + 15);
        for (int y = ty0; y <= max_y; ++y) {
            for (int x = tx0; x <= max_x; ++x) {
                float2 uv = (float2(float(x), float(y)) + 0.5) * inv_m;
                hiz_min = min(hiz_min, sample_hiz_level(chosen, uv));
            }
        }
        float obj_nearest_z = clamp(max_nz, 0.0, 1.0);
        if (obj_nearest_z + hiz_info.z < hiz_min) {
            commands[gid].num_indices = 0u; commands[gid].num_instances = 0u;
            commands[gid].first_index = m.info.y; commands[gid].vertex_offset = 0; commands[gid].first_instance = gid;
            results[gid] = 4u;
            return;
        }
    }

    commands[gid].num_indices = m.info.z;
    commands[gid].num_instances = 1u;
    commands[gid].first_index = m.info.y;
    commands[gid].vertex_offset = 0;
    commands[gid].first_instance = gid;
    results[gid] = 1u;
}

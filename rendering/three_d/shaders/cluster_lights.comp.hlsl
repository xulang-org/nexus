static const uint CLUSTER_X = 16u;
static const uint CLUSTER_Y = 16u;
static const uint CLUSTER_Z = 24u;
static const uint TOTAL_CLUSTERS = CLUSTER_X * CLUSTER_Y * CLUSTER_Z;
static const uint MAX_LIGHTS_PER_CLUSTER = 64u;

struct LightGpu {
    float4 position_kind;
    float4 direction_range;
    float4 radiance_inner;
    float4 cone;
};

cbuffer ClusterParams : register(b0, space2) {
    column_major float4x4 view;
    column_major float4x4 inv_proj;
    float4 grid;
    float4 screen_depth;
    float4 mode_log;
};

StructuredBuffer<LightGpu> lights : register(t0, space0);
RWStructuredBuffer<uint> cluster_counts : register(u0, space1);
RWStructuredBuffer<uint> cluster_indices : register(u1, space1);

float3 unproject_ndc(float4x4 m, float ndc_x, float ndc_y, float ndc_z) {
    float4 v = mul(m, float4(ndc_x, ndc_y, ndc_z, 1.0));
    return v.xyz / v.w;
}

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint light_count = uint(grid.w);

    if (gid == TOTAL_CLUSTERS) {
        uint dir_count = 0u;
        for (uint li = 0u; li < light_count; ++li) {
            if (lights[li].position_kind.w < 0.5) {
                if (dir_count < MAX_LIGHTS_PER_CLUSTER) {
                    cluster_indices[TOTAL_CLUSTERS * MAX_LIGHTS_PER_CLUSTER + dir_count] = li;
                    dir_count += 1u;
                }
            }
        }
        cluster_counts[TOTAL_CLUSTERS] = dir_count;
        return;
    }

    if (gid > TOTAL_CLUSTERS) return;

    uint tx = gid % CLUSTER_X;
    uint ty = (gid / CLUSTER_X) % CLUSTER_Y;
    uint tz = gid / (CLUSTER_X * CLUSTER_Y);

    float ndc_x0 = (float(tx) / float(CLUSTER_X)) * 2.0 - 1.0;
    float ndc_x1 = (float(tx + 1u) / float(CLUSTER_X)) * 2.0 - 1.0;
    float ndc_y1 = 1.0 - (float(ty) / float(CLUSTER_Y)) * 2.0;
    float ndc_y0 = 1.0 - (float(ty + 1u) / float(CLUSTER_Y)) * 2.0;

    float z_near = screen_depth.z;
    float z_far = screen_depth.w;
    float d0 = z_near;
    float d1 = z_far;
    if (mode_log.x < 0.5) {
        d0 = z_near * exp(mode_log.y * (float(tz) / float(CLUSTER_Z)));
        d1 = z_near * exp(mode_log.y * (float(tz + 1u) / float(CLUSTER_Z)));
    } else {
        d0 = lerp(z_near, z_far, float(tz) / float(CLUSTER_Z));
        d1 = lerp(z_near, z_far, float(tz + 1u) / float(CLUSTER_Z));
    }

    float2 corners[4] = {
        float2(ndc_x0, ndc_y0),
        float2(ndc_x1, ndc_y0),
        float2(ndc_x0, ndc_y1),
        float2(ndc_x1, ndc_y1)
    };

    float3 box_min = float3(1e30, 1e30, 1e30);
    float3 box_max = float3(-1e30, -1e30, -1e30);

    for (int i = 0; i < 4; ++i) {
        float3 p_near = unproject_ndc(inv_proj, corners[i].x, corners[i].y, 1.0);
        float3 p_far = unproject_ndc(inv_proj, corners[i].x, corners[i].y, 0.0);
        float3 a = p_near;
        float3 b = p_far;
        if (mode_log.x < 0.5) {
            float3 ray = unproject_ndc(inv_proj, corners[i].x, corners[i].y, 0.5);
            float rz = max(-ray.z, 1e-6);
            a = ray * (d0 / rz);
            b = ray * (d1 / rz);
        } else {
            float zn = -p_near.z;
            float zf = -p_far.z;
            float span = max(abs(zf - zn), 1e-6);
            float t0 = (d0 - zn) / span;
            float t1 = (d1 - zn) / span;
            a = lerp(p_near, p_far, t0);
            b = lerp(p_near, p_far, t1);
        }
        box_min = min(box_min, min(a, b));
        box_max = max(box_max, max(a, b));
    }

    uint local_count = 0u;
    uint out_base = gid * MAX_LIGHTS_PER_CLUSTER;
    for (uint li = 0u; li < light_count; ++li) {
        float4 pk = lights[li].position_kind;
        if (pk.w < 0.5) continue;
        float radius = lights[li].direction_range.w;
        float3 lv = mul(view, float4(pk.xyz, 1.0)).xyz;
        float3 closest = clamp(lv, box_min, box_max);
        float3 diff = lv - closest;
        if (dot(diff, diff) <= radius * radius) {
            if (local_count < MAX_LIGHTS_PER_CLUSTER) {
                cluster_indices[out_base + local_count] = li;
                local_count += 1u;
            }
        }
    }
    cluster_counts[gid] = local_count;
}

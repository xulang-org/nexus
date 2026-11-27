struct FoliageInstanceGpu {
    float4 pos_scale;
    float4 rot_wind;
    float4 tint_var;
};

cbuffer FoliageCullParams : register(b0, space2) {
    column_major float4x4 view_proj;
    float4 camera_pos_count;
    float4 dist_params;
    float4 extra;
};

StructuredBuffer<FoliageInstanceGpu> instances : register(t0, space0);
RWStructuredBuffer<uint> visible_indices : register(u0, space1);
RWByteAddressBuffer state : register(u1, space1);

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint count = uint(camera_pos_count.w);
    if (gid >= count) return;

    FoliageInstanceGpu inst = instances[gid];
    float s = inst.pos_scale.w;
    float sy = s * inst.rot_wind.w;
    float half_y = dist_params.w * sy;
    float radius = max(s, sy) * dist_params.z + extra.x;
    float3 center = inst.pos_scale.xyz + float3(0.0, half_y, 0.0);

    float dist = length(center - camera_pos_count.xyz);
    if (dist - radius > dist_params.x) {
        uint prev;
        state.InterlockedAdd(24u, 1u, prev);
        return;
    }

    float3 bmin = center - float3(radius, half_y + extra.x, radius);
    float3 bmax = center + float3(radius, half_y + extra.x, radius);
    uint out_left = 1u, out_right = 1u, out_bottom = 1u, out_top = 1u, out_far = 1u, out_near = 1u, all_behind = 1u;

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
    }

    if ((out_left | out_right | out_bottom | out_top | out_far | out_near | all_behind) != 0u) {
        uint prev;
        state.InterlockedAdd(20u, 1u, prev);
        return;
    }

    uint slot;
    state.InterlockedAdd(4u, 1u, slot);
    visible_indices[slot] = gid;
}

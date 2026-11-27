cbuffer FroxelAccumParams : register(b0, space2) {
    column_major float4x4 inv_vp;
    float4 eye_near;
    float4 cam_fwd_far;
    float4 grid_pad;
};

StructuredBuffer<float4> froxel_scatter : register(t0, space0);
RWStructuredBuffer<float4> froxel_accum : register(u0, space1);

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint fx_n = uint(grid_pad.x), fy_n = uint(grid_pad.y), fz_n = uint(grid_pad.z);
    uint slice_xy = fx_n * fy_n;
    if (gid >= slice_xy) return;

    uint fy = gid / fx_n, fx = gid - fy * fx_n;
    float2 uv = float2((float(fx) + 0.5) / float(fx_n), (float(fy) + 0.5) / float(fy_n));
    float ndc_x = uv.x * 2.0 - 1.0, ndc_y = 1.0 - uv.y * 2.0;
    float4 far4 = mul(inv_vp, float4(ndc_x, ndc_y, 0.001, 1.0));
    float3 far_p = far4.xyz / max(far4.w, 1e-6);
    float3 ray_dir = normalize(far_p - eye_near.xyz), cam_fwd = normalize(cam_fwd_far.xyz);
    float cos_ang = max(dot(ray_dir, cam_fwd), 0.1);

    float fog_near = eye_near.w, fog_far = cam_fwd_far.w, ratio = fog_far / max(fog_near, 1e-4);
    float3 accum_rgb = float3(0.0, 0.0, 0.0);
    float trans = 1.0;

    for (uint fz = 0u; fz < fz_n; ++fz) {
        float z0 = fog_near * pow(ratio, float(fz) / float(fz_n)), z1 = fog_near * pow(ratio, float(fz + 1u) / float(fz_n));
        float ds = (z1 - z0) / cos_ang;
        uint idx = fz * slice_xy + gid;
        float4 scat_ext = froxel_scatter[idx];
        float ext = max(scat_ext.w, 1e-6), slice_t = exp(-ext * ds);
        float3 slice_s = (scat_ext.rgb - scat_ext.rgb * slice_t) / ext;
        accum_rgb += trans * slice_s;
        trans *= slice_t;
        froxel_accum[idx] = float4(accum_rgb, trans);
    }
}

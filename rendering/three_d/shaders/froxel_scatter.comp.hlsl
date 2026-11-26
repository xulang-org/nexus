struct LightGpu { float4 position_kind; float4 direction_range; float4 radiance_inner; float4 cone; };

cbuffer FroxelScatterParams : register(b0, space2) {
    column_major float4x4 inv_vp;
    float4 eye_time;
    float4 cam_fwd_count;
    float4 grid_near;
    float4 fog_far_dens;
    float4 fog_phase_ext;
    float4 fog_albedo_scat;
    float4 fog_ambient_lboost;
    float4 sun_dir_en;
    float4 sun_rad_boost;
    float4 wind_vel_pad;
    float4 pad0;
};

StructuredBuffer<LightGpu> lights : register(t0, space0);
RWStructuredBuffer<float4> froxel_scatter : register(u0, space1);

float hg_phase(float cos_theta, float g) {
    float g2 = g * g;
    float denom = max(1.0 + g2 - 2.0 * g * cos_theta, 1e-4);
    return (1.0 - g2) / (4.0 * 3.14159265359 * pow(denom, 1.5));
}

float hash31(float3 pt) {
    pt = frac(pt * 0.1031);
    pt += dot(pt, pt.yzx + 33.33);
    return frac((pt.x + pt.y) * pt.z);
}

float noise3d(float3 x) {
    float3 i = floor(x), f = frac(x);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(
        lerp(lerp(hash31(i + float3(0,0,0)), hash31(i + float3(1,0,0)), f.x),
             lerp(hash31(i + float3(0,1,0)), hash31(i + float3(1,1,0)), f.x), f.y),
        lerp(lerp(hash31(i + float3(0,0,1)), hash31(i + float3(1,0,1)), f.x),
             lerp(hash31(i + float3(0,1,1)), hash31(i + float3(1,1,1)), f.x), f.y),
        f.z
    );
}

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint fx_n = uint(grid_near.x), fy_n = uint(grid_near.y), fz_n = uint(grid_near.z);
    uint total = fx_n * fy_n * fz_n;
    if (gid >= total) return;

    if (sun_dir_en.w < 0.5) {
        froxel_scatter[gid] = float4(0.0, 0.0, 0.0, 0.0);
        return;
    }

    uint slice_xy = fx_n * fy_n;
    uint fz = gid / slice_xy, rem = gid - fz * slice_xy, fy = rem / fx_n, fx = rem - fy * fx_n;

    float2 uv = float2((float(fx) + 0.5) / float(fx_n), (float(fy) + 0.5) / float(fy_n));
    float ndc_x = uv.x * 2.0 - 1.0, ndc_y = 1.0 - uv.y * 2.0;
    float4 far4 = mul(inv_vp, float4(ndc_x, ndc_y, 0.001, 1.0));
    float3 far_p = far4.xyz / max(far4.w, 1e-6);
    float3 eye = eye_time.xyz, ray_dir = normalize(far_p - eye), cam_fwd = normalize(cam_fwd_count.xyz);
    float cos_ang = max(dot(ray_dir, cam_fwd), 0.1);

    float fog_near = grid_near.w, fog_far = fog_far_dens.x, ratio = fog_far / max(fog_near, 1e-4);
    float z0 = fog_near * pow(ratio, float(fz) / float(fz_n)), z1 = fog_near * pow(ratio, float(fz + 1u) / float(fz_n));
    float3 world_pos = eye + ray_dir * (0.5 * (z0 + z1) / cos_ang);

    float h_above = max(world_pos.y - fog_far_dens.w, 0.0);
    float dens = fog_far_dens.y * exp(-h_above * fog_far_dens.z);
    if (fog_phase_ext.z > 0.0) {
        float3 sample_p = (world_pos + wind_vel_pad.xyz * eye_time.w) * fog_phase_ext.w;
        dens *= max(0.0, lerp(1.0, 0.35 + 1.3 * noise3d(sample_p), fog_phase_ext.z));
    }

    float g = fog_phase_ext.x;
    float3 albedo = fog_albedo_scat.rgb, sun_dir = normalize(sun_dir_en.xyz);
    float sun_phase = hg_phase(dot(ray_dir, sun_dir), g);
    float3 in_scatter = fog_ambient_lboost.rgb * albedo + sun_rad_boost.rgb * albedo * sun_phase * sun_rad_boost.w;

    uint lcount = min(uint(cam_fwd_count.w), 64u);
    float lboost = fog_ambient_lboost.w;
    if (lboost > 0.0) {
        for (uint li = 0u; li < lcount; ++li) {
            LightGpu src = lights[li];
            if (src.position_kind.w < 0.5) continue;
            float3 delta = src.position_kind.xyz - world_pos;
            float d2 = dot(delta, delta), r2 = src.direction_range.w * src.direction_range.w;
            if (d2 >= r2) continue;
            float3 ldir = delta / sqrt(max(d2, 1e-6));
            float rel2 = d2 / r2, edge = max(0.0, 1.0 - rel2 * rel2);
            float atten = edge * edge / max(d2, 0.25);
            if (src.position_kind.w > 1.5) {
                float cos_a = dot(src.direction_range.xyz, -ldir);
                float sp = clamp((cos_a - src.cone.x) / max(src.radiance_inner.w - src.cone.x, 1e-6), 0.0, 1.0);
                atten *= sp * sp * (3.0 - 2.0 * sp);
            }
            float lphase = hg_phase(dot(ray_dir, ldir), g * 0.65);
            in_scatter += src.radiance_inner.xyz * atten * albedo * lphase * lboost;
        }
    }

    float3 scat = in_scatter * (dens * fog_albedo_scat.w);
    float ext = dens * fog_phase_ext.y;
    froxel_scatter[gid] = float4(max(scat, float3(0.0, 0.0, 0.0)), max(ext, 0.0));
}

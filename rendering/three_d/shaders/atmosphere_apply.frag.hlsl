cbuffer AtmosphereApplyUniform : register(b0, space3) {
    column_major float4x4 inv_vp;
    column_major float4x4 view;
    float4 eye_flags;
    float4 sun_dir_fog;
    float4 sun_rad_disc;
    float4 sky_rayleigh;
    float4 sky_mie;
    float4 ground_near;
    float4 grid_far;
};

Texture2D<float> scene_depth_tex : register(t0, space2);
SamplerState depth_samp : register(s0, space2);
StructuredBuffer<float4> froxel_accum : register(t1, space2);

struct Input {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

float ray_sphere_exit(float3 ro, float3 rd, float radius) {
    float b = dot(ro, rd), c = dot(ro, ro) - radius * radius, disc = b * b - c;
    if (disc < 0.0) return -1.0;
    return -b + sqrt(disc);
}

float3 compute_physical_sky(float3 rd) {
    static const float Re = 6360000.0, Ra = 6420000.0;
    float3 sun_dir = normalize(sun_dir_fog.xyz);
    float mu = dot(rd, sun_dir);
    float3 ray_dir = rd;
    float horizon_ground_mix = 0.0;
    if (ray_dir.y < 0.02) {
        horizon_ground_mix = smoothstep(0.02, -0.18, ray_dir.y);
        ray_dir = normalize(float3(ray_dir.x, max(ray_dir.y, 0.02), ray_dir.z));
    }
    float3 ro = float3(0.0, Re + 120.0, 0.0);
    float t_max = ray_sphere_exit(ro, ray_dir, Ra);
    if (t_max <= 0.0) return float3(0.0, 0.0, 0.0);

    static const int STEPS_V = 8, STEPS_L = 4;
    float seg_v = t_max / float(STEPS_V);
    float3 beta_r = sky_rayleigh.rgb;
    float h_r = max(sky_rayleigh.w, 100.0), beta_m = sky_mie.x, g = clamp(sky_mie.y, -0.95, 0.95), h_m = max(sky_mie.z, 50.0);
    float opt_r = 0.0, opt_m = 0.0;
    float3 sum_r = float3(0.0, 0.0, 0.0), sum_m = float3(0.0, 0.0, 0.0);

    for (int i = 0; i < STEPS_V; ++i) {
        float3 pos = ro + ray_dir * ((float(i) + 0.5) * seg_v);
        float alt = max(length(pos) - Re, 0.0), hr = exp(-alt / h_r) * seg_v, hm = exp(-alt / h_m) * seg_v;
        opt_r += hr; opt_m += hm;
        float t_light = ray_sphere_exit(pos, sun_dir, Ra);
        if (t_light <= 0.0) continue;
        float seg_l = t_light / float(STEPS_L), opt_lr = 0.0, opt_lm = 0.0;
        bool blocked = false;
        for (int j = 0; j < STEPS_L; ++j) {
            float3 lpos = pos + sun_dir * ((float(j) + 0.5) * seg_l);
            float lalt = length(lpos) - Re;
            if (lalt < 0.0) { blocked = true; break; }
            opt_lr += exp(-lalt / h_r) * seg_l; opt_lm += exp(-lalt / h_m) * seg_l;
        }
        if (blocked) continue;
        float bm11 = beta_m * 1.1;
        float3 tau = beta_r * (opt_r + opt_lr) + float3(bm11, bm11, bm11) * (opt_m + opt_lm), atten = exp(-tau);
        sum_r += atten * hr; sum_m += atten * hm;
    }

    float phase_r = 3.0 / (16.0 * 3.14159265359) * (1.0 + mu * mu), g2 = g * g;
    float phase_m = 3.0 / (8.0 * 3.14159265359) * ((1.0 - g2) * (1.0 + mu * mu)) /
        max((2.0 + g2) * pow(max(1.0 + g2 - 2.0 * g * mu, 1e-4), 1.5), 1e-4);
    float3 sky = (sun_rad_disc.rgb * 8.5) * (sum_r * beta_r * phase_r + sum_m * beta_m * phase_m);

    if (rd.y >= -0.02 && sun_rad_disc.w > 0.0) {
        float cos_r = sky_mie.w, disc = smoothstep(cos_r - 0.0005, cos_r + 0.0004, mu);
        float bm11 = beta_m * 1.1;
        float3 limb_tau = beta_r * opt_r + float3(bm11, bm11, bm11) * opt_m;
        sky += sun_rad_disc.rgb * sun_rad_disc.w * exp(-limb_tau * 0.45) * disc;
    }
    if (horizon_ground_mix > 0.0) {
        float sun_up = clamp(sun_dir.y * 2.0 + 0.25, 0.05, 1.0);
        sky = lerp(sky, ground_near.rgb * sun_rad_disc.rgb * sun_up, horizon_ground_mix);
    }
    return max(sky, float3(0.0, 0.0, 0.0));
}

float4 sample_froxel_trilinear(float2 fuv, float z_norm, uint fx_n, uint fy_n, uint fz_n) {
    float fx = clamp(fuv.x * float(fx_n) - 0.5, 0.0, float(fx_n - 1u));
    float fy = clamp(fuv.y * float(fy_n) - 0.5, 0.0, float(fy_n - 1u));
    float fz = clamp(z_norm * float(fz_n) - 0.5, 0.0, float(fz_n - 1u));
    uint x0 = uint(floor(fx)), y0 = uint(floor(fy)), z0 = uint(floor(fz));
    uint x1 = min(x0 + 1u, fx_n - 1u), y1 = min(y0 + 1u, fy_n - 1u), z1 = min(z0 + 1u, fz_n - 1u);
    float tx = fx - float(x0), ty = fy - float(y0), tz = fz - float(z0);
    uint slice_xy = fx_n * fy_n;
    float4 c000 = froxel_accum[z0 * slice_xy + y0 * fx_n + x0], c100 = froxel_accum[z0 * slice_xy + y0 * fx_n + x1];
    float4 c010 = froxel_accum[z0 * slice_xy + y1 * fx_n + x0], c110 = froxel_accum[z0 * slice_xy + y1 * fx_n + x1];
    float4 c001 = froxel_accum[z1 * slice_xy + y0 * fx_n + x0], c101 = froxel_accum[z1 * slice_xy + y0 * fx_n + x1];
    float4 c011 = froxel_accum[z1 * slice_xy + y1 * fx_n + x0], c111 = froxel_accum[z1 * slice_xy + y1 * fx_n + x1];
    float4 c00 = lerp(c000, c100, tx), c10 = lerp(c010, c110, tx), c01 = lerp(c001, c101, tx), c11 = lerp(c011, c111, tx);
    return lerp(lerp(c00, c10, ty), lerp(c01, c11, ty), tz);
}

float4 main(Input input) : SV_Target0 {
    float scene_d = scene_depth_tex.SampleLevel(depth_samp, input.uv, 0.0).r;
    float ndc_x = input.uv.x * 2.0 - 1.0, ndc_y = 1.0 - input.uv.y * 2.0;
    if (scene_d <= 1e-6) {
        if (eye_flags.w < 0.5) return float4(0.0, 0.0, 0.0, 0.0);
        float4 far4 = mul(inv_vp, float4(ndc_x, ndc_y, 0.001, 1.0));
        float3 far_p = far4.xyz / max(far4.w, 1e-6);
        float3 rd = normalize(far_p - eye_flags.xyz);
        return float4(compute_physical_sky(rd), 1.0);
    }
    if (sun_dir_fog.w < 0.5) return float4(0.0, 0.0, 0.0, 0.0);
    float4 wp4 = mul(inv_vp, float4(ndc_x, ndc_y, scene_d, 1.0));
    float3 world_pos = wp4.xyz / max(wp4.w, 1e-6);
    float view_dist = -mul(view, float4(world_pos, 1.0)).z;
    if (view_dist <= 0.0) return float4(0.0, 0.0, 0.0, 0.0);

    float fog_near = ground_near.w, fog_far = grid_far.w, clamped_z = clamp(view_dist, fog_near, fog_far);
    float z_norm = log(clamped_z / max(fog_near, 1e-4)) / max(log(fog_far / max(fog_near, 1e-4)), 1e-4);
    float4 fog = sample_froxel_trilinear(input.uv, z_norm, uint(grid_far.x), uint(grid_far.y), uint(grid_far.z));
    float near_ramp = clamp(view_dist / max(fog_near, 0.05), 0.0, 1.0);
    float3 in_scatter = fog.rgb * near_ramp;
    float trans = lerp(1.0, clamp(fog.a, 0.0, 1.0), near_ramp);
    return float4(max(in_scatter, float3(0.0, 0.0, 0.0)), clamp(1.0 - trans, 0.0, 1.0));
}

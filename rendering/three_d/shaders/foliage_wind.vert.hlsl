struct FoliageInstanceGpu {
    float4 pos_scale;
    float4 rot_wind;
    float4 tint_var;
};

cbuffer FoliageVertUniform : register(b0, space1) {
    column_major float4x4 view_proj;
    column_major float4x4 view;
    float4 wind_dir_strength;
    float4 wind_wave;
    float4 fade_camera;
    float4 fade_extra;
};

StructuredBuffer<FoliageInstanceGpu> instances : register(t0, space0);
StructuredBuffer<uint> visible_indices : register(t1, space0);

struct Input {
    float3 position : TEXCOORD0;
    float4 color : TEXCOORD1;
    float3 normal : TEXCOORD2;
    float2 uv : TEXCOORD3;
    float4 tangent : TEXCOORD4;
};

struct Output {
    float4 position : SV_Position;
    float4 vertex_color : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 world_normal : TEXCOORD2;
    float2 texture_uv : TEXCOORD3;
    float3 instance_tint : TEXCOORD4;
    float height_frac : TEXCOORD5;
    float fade : TEXCOORD6;
    float view_depth : TEXCOORD7;
};

Output main(Input input, uint iid : SV_InstanceID) {
    uint real_idx = visible_indices[iid];
    FoliageInstanceGpu inst = instances[real_idx];

    float dist = length(inst.pos_scale.xyz - fade_camera.xyz);
    float fade_start = fade_camera.w;
    float max_dist = max(fade_extra.x, fade_start + 0.001);
    float fade_val = 1.0 - smoothstep(fade_start, max_dist, dist);

    float s_xz = inst.pos_scale.w;
    float s_y = s_xz * inst.rot_wind.w * lerp(0.35, 1.0, fade_val);

    float3 lp = float3(input.position.x * s_xz, input.position.y * s_y, input.position.z * s_xz);
    float cy = inst.rot_wind.x, sy = inst.rot_wind.y;
    float3 rot_p = float3(lp.x * cy + lp.z * sy, lp.y, -lp.x * sy + lp.z * cy);
    float3 rot_n = float3(input.normal.x * cy + input.normal.z * sy, input.normal.y, -input.normal.x * sy + input.normal.z * cy);

    float h_frac = clamp(max(input.uv.y, input.position.y * fade_extra.y), 0.0, 1.0);
    float bend = (h_frac * h_frac) / max(fade_extra.z, 0.25);

    float2 wdir = wind_dir_strength.xy;
    wdir /= max(length(wdir), 1e-5);
    float2 perp = float2(-wdir.y, wdir.x);

    float time = wind_dir_strength.w;
    float phase = dot(inst.pos_scale.xz, wdir) * wind_wave.y + inst.rot_wind.z;
    float primary = sin(time * wind_wave.x + phase);
    float gust = sin(time * wind_wave.w + dot(inst.pos_scale.xz, perp) * (wind_wave.y * 0.65) + inst.rot_wind.z * 1.7);
    float disp_main = (wind_dir_strength.z * (0.45 + 0.55 * primary) + wind_wave.z * gust) * bend;
    float disp_cross = wind_wave.z * 0.45 * cos(time * wind_wave.x * 1.3 + inst.rot_wind.z) * bend;

    float3 world_pos = inst.pos_scale.xyz + rot_p;
    world_pos.xz += wdir * disp_main + perp * disp_cross;
    world_pos.y -= min(abs(disp_main) * 0.18, s_y * 0.35 * h_frac);

    float3 bent_n = normalize(rot_n + float3(wdir.x * disp_main, 0.35, wdir.y * disp_main));

    Output output;
    output.position = mul(view_proj, float4(world_pos, 1.0));
    output.vertex_color = input.color;
    output.world = world_pos;
    output.world_normal = bent_n;
    output.texture_uv = input.uv;
    output.instance_tint = inst.tint_var.rgb;
    output.height_frac = h_frac;
    output.fade = fade_val;
    output.view_depth = -mul(view, float4(world_pos, 1.0)).z;
    return output;
}

struct ParticleGpu { float4 pos_age; float4 vel_life; float4 size_rot; float4 aux; };

cbuffer ParticleVertUniform : register(b0, space1) {
    column_major float4x4 view_proj;
    column_major float4x4 view;
    float4 cam_right_mode;
    float4 cam_up_atlas;
    float4 color_keys[4];
    float4 atlas_info;
    float4 extra;
};

StructuredBuffer<ParticleGpu> particles : register(t0, space0);
StructuredBuffer<uint> alive_indices : register(t1, space0);

struct Output {
    float4 position : SV_Position;
    float4 color : TEXCOORD0;
    float2 atlas_uv : TEXCOORD1;
    float2 local_uv : TEXCOORD2;
    float view_z : TEXCOORD3;
    float additive : TEXCOORD4;
};

float4 eval_4stop_color(float t) {
    float s = clamp(t, 0.0, 1.0) * 3.0;
    int idx = min(int(floor(s)), 2);
    float f = s - float(idx);
    return lerp(color_keys[idx], color_keys[idx + 1], f);
}

Output main(uint vid : SV_VertexID, uint iid : SV_InstanceID) {
    static const float2 corners[6] = {
        float2(-0.5, -0.5), float2(0.5, -0.5), float2(0.5, 0.5),
        float2(-0.5, -0.5), float2(0.5, 0.5), float2(-0.5, 0.5)
    };
    static const float2 uvs[6] = {
        float2(0.0, 1.0), float2(1.0, 1.0), float2(1.0, 0.0),
        float2(0.0, 1.0), float2(1.0, 0.0), float2(0.0, 0.0)
    };

    uint ci = vid % 6u;
    float2 corner = corners[ci], luv = uvs[ci];
    uint pid = alive_indices[iid];
    ParticleGpu p = particles[pid];

    float life = max(p.vel_life.w, 1e-5), t = clamp(p.pos_age.w / life, 0.0, 1.0);
    float4 col = eval_4stop_color(t);
    col.rgb *= atlas_info.z;

    float size = lerp(p.size_rot.x, p.size_rot.y, t);
    if (extra.x > 0.5) size *= sin(t * 3.14159265359);

    int mode = int(cam_right_mode.w + 0.5);
    float3 right_w = float3(0.0, 0.0, 0.0), up_w = float3(0.0, 0.0, 0.0);
    float rot = p.size_rot.z, cr = cos(rot), sr = sin(rot);
    if (mode == 2) {
        right_w = float3(cr, 0.0, sr) * size; up_w = float3(-sr, 0.0, cr) * size;
    } else if (mode == 1) {
        float3 cam_r = cam_right_mode.xyz, cam_u = cam_up_atlas.xyz, cam_f = normalize(cross(cam_r, cam_u));
        float3 vel = p.vel_life.xyz, v_ortho = vel - cam_f * dot(vel, cam_f);
        float vlen = length(vel), olen = length(v_ortho);
        float3 dir = olen > 1e-4 ? (v_ortho / olen) : (cam_r * cr + cam_u * sr), perp = normalize(cross(cam_f, dir));
        up_w = dir * (size * (1.0 + max(vlen, atlas_info.w) * p.aux.y));
        right_w = perp * (size * 0.35);
    } else {
        float3 cam_r = cam_right_mode.xyz, cam_u = cam_up_atlas.xyz;
        right_w = (cam_r * cr + cam_u * sr) * size;
        up_w = (-cam_r * sr + cam_u * cr) * size;
    }

    float3 world_pos = p.pos_age.xyz + right_w * corner.x + up_w * corner.y;
    float cols = max(floor(atlas_info.x + 0.5), 1.0), rows = max(floor(atlas_info.y + 0.5), 1.0);
    float total_frames = cols * rows;
    float frame_f = clamp(floor(frac(t * max(cam_up_atlas.w, 1.0)) * total_frames), 0.0, total_frames - 1.0);
    float cell_x = fmod(frame_f, cols), cell_y = floor(frame_f / cols);

    Output output;
    output.position = mul(view_proj, float4(world_pos, 1.0));
    output.color = col;
    output.atlas_uv = (float2(cell_x, cell_y) + luv) / float2(cols, rows);
    output.local_uv = luv;
    output.view_z = -mul(view, float4(world_pos, 1.0)).z;
    output.additive = lerp(p.aux.z, p.aux.w, t);
    return output;
}

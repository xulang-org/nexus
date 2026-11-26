#version 450

struct ParticleGpu { vec4 pos_age; vec4 vel_life; vec4 size_rot; vec4 aux; };

layout(set = 1, binding = 0, std140) uniform ParticleVertUniform {
    mat4 view_proj;
    mat4 view;
    vec4 cam_right_mode;
    vec4 cam_up_atlas;
    vec4 color_keys[4];
    vec4 atlas_info;
    vec4 extra;
} u;

layout(set = 0, binding = 0, std430) readonly buffer ParticlesBuf { ParticleGpu particles[]; };
layout(set = 0, binding = 1, std430) readonly buffer AliveBuf { uint alive_indices[]; };

layout(location = 0) out vec4 color;
layout(location = 1) out vec2 atlas_uv;
layout(location = 2) out vec2 local_uv;
layout(location = 3) out float view_z;
layout(location = 4) out float additive;

vec4 eval_4stop_color(float t) {
    float s = clamp(t, 0.0, 1.0) * 3.0;
    int idx = min(int(floor(s)), 2);
    float f = s - float(idx);
    return mix(u.color_keys[idx], u.color_keys[idx + 1], f);
}

void main() {
    const vec2 corners[6] = vec2[6](
        vec2(-0.5, -0.5), vec2(0.5, -0.5), vec2(0.5, 0.5),
        vec2(-0.5, -0.5), vec2(0.5, 0.5), vec2(-0.5, 0.5)
    );
    const vec2 uvs[6] = vec2[6](
        vec2(0.0, 1.0), vec2(1.0, 1.0), vec2(1.0, 0.0),
        vec2(0.0, 1.0), vec2(1.0, 0.0), vec2(0.0, 0.0)
    );

    uint ci = uint(gl_VertexIndex) % 6u;
    vec2 corner = corners[ci], luv = uvs[ci];
    uint pid = alive_indices[uint(gl_InstanceIndex)];
    ParticleGpu p = particles[pid];

    float life = max(p.vel_life.w, 1e-5), t = clamp(p.pos_age.w / life, 0.0, 1.0);
    vec4 col = eval_4stop_color(t);
    col.rgb *= u.atlas_info.z;

    float size = mix(p.size_rot.x, p.size_rot.y, t);
    if (u.extra.x > 0.5) size *= sin(t * 3.14159265359);

    int mode = int(u.cam_right_mode.w + 0.5);
    vec3 right_w = vec3(0.0), up_w = vec3(0.0);
    float rot = p.size_rot.z, cr = cos(rot), sr = sin(rot);
    if (mode == 2) {
        right_w = vec3(cr, 0.0, sr) * size; up_w = vec3(-sr, 0.0, cr) * size;
    } else if (mode == 1) {
        vec3 cam_r = u.cam_right_mode.xyz, cam_u = u.cam_up_atlas.xyz, cam_f = normalize(cross(cam_r, cam_u));
        vec3 vel = p.vel_life.xyz, v_ortho = vel - cam_f * dot(vel, cam_f);
        float vlen = length(vel), olen = length(v_ortho);
        vec3 dir = olen > 1e-4 ? (v_ortho / olen) : (cam_r * cr + cam_u * sr), perp = normalize(cross(cam_f, dir));
        up_w = dir * (size * (1.0 + max(vlen, u.atlas_info.w) * p.aux.y));
        right_w = perp * (size * 0.35);
    } else {
        vec3 cam_r = u.cam_right_mode.xyz, cam_u = u.cam_up_atlas.xyz;
        right_w = (cam_r * cr + cam_u * sr) * size;
        up_w = (-cam_r * sr + cam_u * cr) * size;
    }

    vec3 world_pos = p.pos_age.xyz + right_w * corner.x + up_w * corner.y;
    float cols = max(floor(u.atlas_info.x + 0.5), 1.0), rows = max(floor(u.atlas_info.y + 0.5), 1.0);
    float total_frames = cols * rows;
    float frame_f = clamp(floor(fract(t * max(u.cam_up_atlas.w, 1.0)) * total_frames), 0.0, total_frames - 1.0);
    float cell_x = mod(frame_f, cols), cell_y = floor(frame_f / cols);

    gl_Position = u.view_proj * vec4(world_pos, 1.0);
    color = col;
    atlas_uv = (vec2(cell_x, cell_y) + luv) / vec2(cols, rows);
    local_uv = luv;
    view_z = -(u.view * vec4(world_pos, 1.0)).z;
    additive = mix(p.aux.z, p.aux.w, t);
}

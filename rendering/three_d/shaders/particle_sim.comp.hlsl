struct ParticleGpu { float4 pos_age; float4 vel_life; float4 size_rot; float4 aux; };

cbuffer SimParams : register(b0, space2) {
    float4 time_counts; float4 seed_shape; float4 origin_boxz; float4 dir_spread;
    float4 base_vel_drag; float4 speed_life; float4 size_rot; float4 ang_stretch_add;
    float4 end_add_pad; float4 gravity_wind; float4 attractor; float4 vortex;
    float4 plane_eq; float4 plane_mat; float4 reserved0; float4 reserved1;
};

RWStructuredBuffer<ParticleGpu> particles : register(u0, space1);
RWStructuredBuffer<uint> alive_indices : register(u1, space1);
RWStructuredBuffer<uint> counters : register(u2, space1);

uint pcg_hash(uint v) {
    uint state = v * 747796405u + 2891336453u;
    uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

float rand_next(inout uint state) {
    state = pcg_hash(state);
    return float(state & 0x00FFFFFFu) / 16777216.0;
}

float3 vec_potential(float3 q) {
    return float3(
        sin(q.y * 1.13 + 0.7) * cos(q.z * 0.91 - 0.3) + 0.5 * sin(q.z * 2.11 + q.x * 0.67),
        sin(q.z * 1.27 - 1.1) * cos(q.x * 0.89 + 0.5) + 0.5 * sin(q.x * 2.03 + q.y * 0.71),
        sin(q.x * 1.07 + 0.4) * cos(q.y * 1.19 + 0.9) + 0.5 * sin(q.y * 1.97 + q.z * 0.61)
    );
}

float3 curl_noise_3d(float3 pos, float freq, float elapsed, float scroll) {
    float3 q = pos * freq + float3(elapsed * scroll, elapsed * scroll * 0.73, elapsed * scroll * 0.41);
    static const float eps = 0.05;
    float3 px1 = vec_potential(q + float3(eps, 0.0, 0.0)), px0 = vec_potential(q - float3(eps, 0.0, 0.0));
    float3 py1 = vec_potential(q + float3(0.0, eps, 0.0)), py0 = vec_potential(q - float3(0.0, eps, 0.0));
    float3 pz1 = vec_potential(q + float3(0.0, 0.0, eps)), pz0 = vec_potential(q - float3(0.0, 0.0, eps));
    float inv2 = 0.5 / eps;
    return float3((py1.z - py0.z - (pz1.y - pz0.y)) * inv2, (pz1.x - pz0.x - (px1.z - px0.z)) * inv2, (px1.y - px0.y - (py1.x - py0.x)) * inv2);
}

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    uint cap = uint(time_counts.z);
    if (gid >= cap) return;

    ParticleGpu p = particles[gid];
    bool alive = (p.vel_life.w > 0.0 && p.pos_age.w >= 0.0 && p.pos_age.w < p.vel_life.w);
    bool spawned = false;

    uint spawn_target = uint(time_counts.w);
    if (!alive && spawn_target > 0u) {
        if (counters[4] < spawn_target) {
            uint ticket;
            InterlockedAdd(counters[4], 1u, ticket);
            if (ticket < spawn_target) {
                uint rng = (gid + 1u) ^ (uint(seed_shape.x) * 747796405u) ^ (ticket * 2891336453u);
                float3 axis = normalize(dir_spread.xyz);
                if (!isfinite(axis.x) || !isfinite(axis.y) || !isfinite(axis.z)) axis = float3(0.0, 1.0, 0.0);
                float3 up_ref = abs(axis.y) < 0.99 ? float3(0.0, 1.0, 0.0) : float3(1.0, 0.0, 0.0);
                float3 tang = normalize(cross(up_ref, axis)), bitang = cross(axis, tang);
                int shape_kind = int(seed_shape.y + 0.5);
                float sp0 = seed_shape.z, sp1 = seed_shape.w;
                float3 spawn_offset = float3(0.0, 0.0, 0.0), emit_dir = axis;

                if (shape_kind == 1) {
                    float u = rand_next(rng) * 2.0 - 1.0, phi = rand_next(rng) * 6.283185307, rr = sqrt(max(0.0, 1.0 - u * u));
                    float3 radial = float3(rr * cos(phi), u, rr * sin(phi));
                    float r_frac = lerp(clamp(sp1, 0.0, 1.0), 1.0, pow(rand_next(rng), 0.33333334));
                    spawn_offset = radial * (sp0 * r_frac);
                    emit_dir = length(radial) > 1e-4 ? normalize(radial) : axis;
                } else if (shape_kind == 2) {
                    spawn_offset = float3((rand_next(rng) * 2.0 - 1.0) * sp0, (rand_next(rng) * 2.0 - 1.0) * sp1, (rand_next(rng) * 2.0 - 1.0) * origin_boxz.w);
                } else if (shape_kind == 3) {
                    float phi = rand_next(rng) * 6.283185307, r = sqrt(rand_next(rng)) * sp0;
                    spawn_offset = (tang * cos(phi) + bitang * sin(phi)) * r;
                    float cos_t = lerp(cos(clamp(sp1, 0.0, 1.56)), 1.0, rand_next(rng)), sin_t = sqrt(max(0.0, 1.0 - cos_t * cos_t)), phi_d = rand_next(rng) * 6.283185307;
                    emit_dir = normalize(axis * cos_t + (tang * cos(phi_d) + bitang * sin(phi_d)) * sin_t);
                } else if (shape_kind == 4) {
                    float phi = rand_next(rng) * 6.283185307;
                    spawn_offset = (tang * cos(phi) + bitang * sin(phi)) * sp0;
                }

                float3 jdir = float3(rand_next(rng) * 2.0 - 1.0, rand_next(rng) * 2.0 - 1.0, rand_next(rng) * 2.0 - 1.0);
                float speed = lerp(speed_life.x, speed_life.y, rand_next(rng));
                float life = max(0.001, lerp(speed_life.z, speed_life.w, rand_next(rng)));
                float s0 = lerp(size_rot.x, size_rot.y, rand_next(rng));
                float rot0 = (rand_next(rng) * 2.0 - 1.0) * size_rot.w;
                float ang_v = lerp(ang_stretch_add.x, ang_stretch_add.y, rand_next(rng));
                float r01 = rand_next(rng);

                p.pos_age = float4(origin_boxz.xyz + spawn_offset, 0.0);
                p.vel_life = float4(base_vel_drag.xyz + emit_dir * speed + jdir * dir_spread.w, life);
                p.size_rot = float4(s0, s0 * size_rot.z, rot0, ang_v);
                p.aux = float4(r01, ang_stretch_add.z, ang_stretch_add.w, end_add_pad.x);
                uint dummy;
                InterlockedAdd(counters[5], 1u, dummy);
                alive = true; spawned = true;
            }
        }
    }

    if (!alive) return;
    if (!spawned) {
        float dt = time_counts.x, new_age = p.pos_age.w + dt;
        if (new_age >= p.vel_life.w) { p.pos_age.w = -1.0; p.vel_life.w = 0.0; particles[gid] = p; return; }
        p.pos_age.w = new_age;
        float3 pos = p.pos_age.xyz, vel = p.vel_life.xyz + gravity_wind.xyz * dt;
        if (end_add_pad.y > 0.0) vel += curl_noise_3d(pos, end_add_pad.z, time_counts.y, end_add_pad.w) * end_add_pad.y * dt;
        if (attractor.w != 0.0) {
            float3 to_a = attractor.xyz - pos;
            float dist = max(length(to_a), 0.25);
            vel += (to_a / dist) * (attractor.w / (dist * dist + 0.5)) * dt;
        }
        if (vortex.w != 0.0) {
            float3 tang = cross(vortex.xyz, pos - attractor.xyz);
            float tlen = length(tang);
            if (tlen > 1e-4) vel += (tang / tlen) * vortex.w * dt;
        }
        if (base_vel_drag.w > 0.0) vel *= exp(-base_vel_drag.w * dt);
        pos += vel * dt;
        p.size_rot.z += p.size_rot.w * dt;
        if (plane_mat.x > 0.5) {
            float3 pn = plane_eq.xyz;
            float signed_d = dot(pos, pn) + plane_eq.w;
            if (signed_d < 0.0) {
                pos -= pn * signed_d;
                float vn = dot(vel, pn);
                if (vn < 0.0) {
                    float3 v_n = pn * vn, v_t = vel - v_n;
                    vel = v_t * max(0.0, 1.0 - plane_mat.z) - v_n * plane_mat.y;
                    uint dummy2;
                    InterlockedAdd(counters[6], 1u, dummy2);
                }
            }
        }
        p.pos_age.xyz = pos; p.vel_life.xyz = vel;
    }

    particles[gid] = p;
    uint idx;
    InterlockedAdd(counters[1], 1u, idx);
    if (idx < cap) alive_indices[idx] = gid;
}

#version 450
layout(location=0) in vec4 tint;
layout(location=1) in vec2 uv;
layout(set=2,binding=0) uniform sampler2D scene_tex;
layout(set=2,binding=1) uniform sampler2D normal_tex;
layout(set=3,binding=0,std140) uniform Lighting2DUniform {
    vec4 view_rect;
    vec4 ambient_exposure;
    vec4 counts_bias;
    vec4 lights[128];
    vec4 occluders[128];
} u;
layout(location=0) out vec4 color;

bool seg_occluded_2d(vec2 from_p, vec2 to_p, int occ_count, float bias) {
    vec2 delta = to_p - from_p;
    float dist = length(delta);
    if (dist <= bias + 1e-4) return false;
    vec2 dir = delta / dist;
    float max_t = dist - bias;
    for (int i = 0; i < 128 && i < occ_count; ++i) {
        vec4 seg = u.occluders[i];
        float sx = seg.z - seg.x;
        float sy = seg.w - seg.y;
        float denom = dir.x * sy - dir.y * sx;
        if (abs(denom) <= 1e-7) continue;
        float qx = seg.x - from_p.x;
        float qy = seg.y - from_p.y;
        float t = (qx * sy - qy * sx) / denom;
        float u_param = (qx * dir.y - qy * dir.x) / denom;
        if (t > 0.001 && t < max_t && u_param >= -1e-4 && u_param <= 1.0 + 1e-4) {
            return true;
        }
    }
    return false;
}

float shadow_factor_2d(vec2 light_pos, vec2 world_pos, float softness, int occ_count, float bias) {
    vec2 delta = world_pos - light_pos;
    float dist = length(delta);
    if (dist <= bias + 1e-4) return 1.0;
    if (softness <= 0.0001) {
        return seg_occluded_2d(light_pos, world_pos, occ_count, bias) ? 0.0 : 1.0;
    }
    vec2 perp = vec2(-delta.y / dist, delta.x / dist);
    float vis = 0.0;
    float offsets[5] = float[5](-1.0, -0.5, 0.0, 0.5, 1.0);
    for (int k = 0; k < 5; ++k) {
        vec2 tap = light_pos + perp * (offsets[k] * softness);
        if (!seg_occluded_2d(tap, world_pos, occ_count, bias)) vis += 1.0;
    }
    return vis * 0.2;
}

void main() {
    vec4 albedo = texture(scene_tex, uv);
    vec2 world_pos = u.view_rect.xy + uv * u.view_rect.zw;
    vec3 normal = vec3(0.0, 0.0, 1.0);
    if (u.counts_bias.w > 0.5) {
        vec3 n_sample = texture(normal_tex, uv).rgb * 2.0 - 1.0;
        float nlen = length(n_sample);
        if (nlen > 1e-5) normal = n_sample / nlen;
    }
    int lcount = int(u.counts_bias.x);
    int ocount = int(u.counts_bias.y);
    float bias = u.counts_bias.z;

    vec3 lit = u.ambient_exposure.xyz;
    for (int i = 0; i < 32 && i < lcount; ++i) {
        int b = i * 4;
        vec4 d0 = u.lights[b + 0];
        vec4 d1 = u.lights[b + 1];
        vec4 d2 = u.lights[b + 2];
        vec4 d3 = u.lights[b + 3];
        if (d3.w < 0.5) continue;

        int kind = int(d0.w + 0.5);
        if (kind == 2) {
            vec3 l3 = normalize(vec3(-d1.x, -d1.y, max(d0.z, 1.0) / 32.0));
            float ndotl = max(0.0, dot(normal, l3));
            lit += d2.xyz * ndotl;
            continue;
        }

        vec2 to_light = d0.xy - world_pos;
        float dist = length(to_light);
        if (dist >= d1.z) continue;
        float norm_u = clamp(1.0 - dist / d1.z, 0.0, 1.0);
        float atten = pow(max(norm_u, 1e-6), d1.w);
        if (norm_u <= 0.0) atten = 0.0;

        if (kind == 1) {
            vec2 out_dir = dist > 1e-6 ? (-to_light / dist) : vec2(1.0, 0.0);
            float cos_a = dot(d1.xy, out_dir);
            atten *= smoothstep(d3.x, d2.w, cos_a);
        }
        if (atten <= 0.0) continue;

        vec3 l3 = normalize(vec3(to_light.x, to_light.y, max(d0.z, 1.0)));
        float ndotl = max(0.0, dot(normal, l3));
        if (ndotl <= 0.0) continue;

        float vis = 1.0;
        if (d3.y > 0.5) {
            vis = shadow_factor_2d(d0.xy, world_pos, d3.z, ocount, bias);
        }
        lit += d2.xyz * (atten * ndotl * vis);
    }
    vec3 final_rgb = clamp(albedo.rgb * lit * u.ambient_exposure.w, vec3(0.0), vec3(1.0));
    color = vec4(final_rgb * tint.rgb, albedo.a * tint.a);
}

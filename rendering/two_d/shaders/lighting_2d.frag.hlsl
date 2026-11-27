Texture2D<float4> scene_tex : register(t0,space2);
SamplerState scene_sampler : register(s0,space2);
Texture2D<float4> normal_tex : register(t1,space2);
SamplerState normal_sampler : register(s1,space2);

cbuffer Lighting2DUniform : register(b0,space3) {
    float4 view_rect;
    float4 ambient_exposure;
    float4 counts_bias;
    float4 tuning;
    float4 lights[128];
    float4 occluders[128];
};

struct Input {
    float4 position : SV_Position;
    float4 color : TEXCOORD0;
    float2 uv : TEXCOORD1;
};

bool seg_occluded_2d(float2 from_p, float2 to_p, int occ_count, float bias) {
    float2 delta = to_p - from_p;
    float dist = length(delta);
    if (dist <= bias + 1e-4) return false;
    float2 dir = delta / dist;
    float max_t = dist - bias;
    for (int i = 0; i < 128 && i < occ_count; ++i) {
        float4 seg = occluders[i];
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

float shadow_factor_2d(float2 light_pos, float2 world_pos, float softness, int occ_count, float bias) {
    float2 delta = world_pos - light_pos;
    float dist = length(delta);
    if (dist <= bias + 1e-4) return 1.0;
    if (softness <= 0.0001) {
        return seg_occluded_2d(light_pos, world_pos, occ_count, bias) ? 0.0 : 1.0;
    }
    float2 perp = float2(-delta.y / dist, delta.x / dist);
    float vis = 0.0;
    static const float offsets[9] = { -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0 };
    static const float weights[9] = { 0.0190, 0.0558, 0.1209, 0.1922, 0.2242, 0.1922, 0.1209, 0.0558, 0.0190 };
    for (int k = 0; k < 9; ++k) {
        float2 tap = light_pos + perp * (offsets[k] * softness);
        if (!seg_occluded_2d(tap, world_pos, occ_count, bias)) vis += weights[k];
    }
    return vis;
}

float4 main(Input input) : SV_Target0 {
    float4 albedo = scene_tex.Sample(scene_sampler, input.uv);
    float2 world_pos = view_rect.xy + input.uv * view_rect.zw;
    float3 normal = float3(0.0, 0.0, 1.0);
    if (counts_bias.w > 0.5) {
        float3 n_sample = normal_tex.Sample(normal_sampler, input.uv).rgb * 2.0 - 1.0;
        float nlen = length(n_sample);
        if (nlen > 1e-5) normal = n_sample / nlen;
    }
    int lcount = int(counts_bias.x);
    int ocount = int(counts_bias.y);
    float bias = counts_bias.z;

    float3 lit = ambient_exposure.xyz;
    float spec_strength = tuning.y;
    float3 view_dir = float3(0.0, 0.0, 1.0);
    for (int i = 0; i < 32 && i < lcount; ++i) {
        int b = i * 4;
        float4 d0 = lights[b + 0];
        float4 d1 = lights[b + 1];
        float4 d2 = lights[b + 2];
        float4 d3 = lights[b + 3];
        if (d3.w < 0.5) continue;

        int kind = int(d0.w + 0.5);
        if (kind == 2) {
            float3 l3 = normalize(float3(-d1.x, -d1.y, max(d0.z, 1.0) / 32.0));
            float ndotl = max(0.0, dot(normal, l3));
            float term = ndotl;
            if (spec_strength > 0.0 && ndotl > 0.0) {
                float3 h = normalize(l3 + view_dir);
                term += pow(max(dot(normal, h), 0.0), 24.0) * spec_strength;
            }
            lit += d2.xyz * term;
            continue;
        }

        float2 to_light = d0.xy - world_pos;
        float dist = length(to_light);
        if (dist >= d1.z) continue;
        float norm_u = clamp(1.0 - dist / d1.z, 0.0, 1.0);
        float atten = pow(max(norm_u, 1e-6), d1.w);
        if (norm_u <= 0.0) atten = 0.0;

        if (kind == 1) {
            float2 out_dir = dist > 1e-6 ? (-to_light / dist) : float2(1.0, 0.0);
            float cos_a = dot(d1.xy, out_dir);
            atten *= smoothstep(d3.x, d2.w, cos_a);
        }
        if (atten <= 0.0) continue;

        float3 l3 = normalize(float3(to_light.x, to_light.y, max(d0.z, 1.0)));
        float ndotl = max(0.0, dot(normal, l3));
        if (ndotl <= 0.0) continue;

        float vis = 1.0;
        if (d3.y > 0.5) {
            vis = shadow_factor_2d(d0.xy, world_pos, d3.z, ocount, bias);
        }
        float term = ndotl;
        if (spec_strength > 0.0) {
            float3 h = normalize(l3 + view_dir);
            term += pow(max(dot(normal, h), 0.0), 24.0) * spec_strength;
        }
        lit += d2.xyz * (atten * term * vis);
    }
    float3 exposed = lit * ambient_exposure.w;
    if (tuning.x > 0.5) {
        exposed = exposed / (1.0 + max(exposed, float3(0.0, 0.0, 0.0)));
    }
    float3 final_rgb = clamp(albedo.rgb * exposed, float3(0.0, 0.0, 0.0), float3(1.0, 1.0, 1.0));
    return float4(final_rgb * input.color.rgb, albedo.a * input.color.a);
}

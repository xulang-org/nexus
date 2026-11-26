#version 450

layout(location = 0) in vec2 uv;
layout(set = 2, binding = 0) uniform sampler2D hdr_tex;
layout(set = 2, binding = 1) uniform sampler2D ao_tex;
layout(set = 2, binding = 2) uniform sampler2D ssr_tex;
layout(set = 2, binding = 3) uniform sampler2D bloom_tex;

layout(set = 3, binding = 0, std140) uniform CompositeParams {
    vec4 gains;
    vec4 mode;
} params;

layout(location = 0) out vec4 output_color;

float srgb_channel(float value) {
    return value <= 0.0031308 ? 12.92 * value : 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}

vec3 aces_filmic(vec3 x) {
    vec3 a = x * (2.51 * x + 0.03);
    vec3 b = x * (2.43 * x + 0.59) + 0.14;
    return clamp(a / max(b, vec3(1e-6)), vec3(0.0), vec3(1.0));
}

void main() {
    vec3 hdr = textureLod(hdr_tex, uv, 0.0).rgb;
    float ao = textureLod(ao_tex, uv, 0.0).r;
    vec4 ssr = textureLod(ssr_tex, uv, 0.0);
    vec3 bloom = textureLod(bloom_tex, uv, 0.0).rgb;

    float ao_factor = mix(1.0, ao, clamp(params.gains.x, 0.0, 1.0));
    vec3 combined = hdr * ao_factor + ssr.rgb * (ssr.a * params.gains.y) + bloom * params.gains.z;
    vec3 exposed = max(combined * params.gains.w, vec3(0.0));
    vec3 mapped = params.mode.x > 0.5 ? aces_filmic(exposed) : (exposed / (1.0 + exposed));
    output_color = vec4(srgb_channel(mapped.x), srgb_channel(mapped.y), srgb_channel(mapped.z), 1.0);
}

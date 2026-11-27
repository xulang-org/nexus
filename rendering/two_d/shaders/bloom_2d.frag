#version 450
layout(location=0) in vec4 tint;
layout(location=1) in vec2 uv;
layout(set=2,binding=0) uniform sampler2D scene_tex;
layout(set=2,binding=1) uniform sampler2D bloom_tex;
layout(set=3,binding=0,std140) uniform Bloom2DUniform {
    vec4 params0;
    vec4 params1;
} u;
layout(location=0) out vec4 color;

vec3 bright_extract(vec3 c, float threshold, float soft_knee) {
    float luma = max(c.r, max(c.g, c.b));
    float knee = max(soft_knee, 1e-4);
    float soft = clamp(luma - threshold + knee, 0.0, 2.0 * knee);
    soft = (soft * soft) / (4.0 * knee);
    float contrib = max(soft, luma - threshold) / max(luma, 1e-5);
    return c * max(contrib, 0.0);
}

void main() {
    float offsets[9] = float[9](-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0);
    float weights[9] = float[9](0.016216, 0.054054, 0.121622, 0.194595, 0.227027, 0.194595, 0.121622, 0.054054, 0.016216);
    if (u.params0.x < 0.5) {
        vec3 sum = vec3(0.0);
        for (int k = 0; k < 9; ++k) {
            vec2 suv = clamp(uv + vec2(offsets[k] * u.params1.z * u.params1.x, 0.0), vec2(0.0), vec2(1.0));
            vec3 tex = texture(scene_tex, suv).rgb;
            sum += bright_extract(tex, u.params0.y, u.params0.z) * weights[k];
        }
        color = vec4(sum, 1.0);
        return;
    }
    vec3 vblur = vec3(0.0);
    for (int k = 0; k < 9; ++k) {
        vec2 buv = clamp(uv + vec2(0.0, offsets[k] * u.params1.z * u.params1.y), vec2(0.0), vec2(1.0));
        vblur += texture(bloom_tex, buv).rgb * weights[k];
    }
    vec4 base = texture(scene_tex, uv);
    vec3 out_rgb = clamp(base.rgb + vblur * u.params0.w, vec3(0.0), vec3(1.0));
    color = vec4(out_rgb * tint.rgb, base.a * tint.a);
}

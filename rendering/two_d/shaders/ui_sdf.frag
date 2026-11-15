#version 450
layout(location=0) in vec2 local_pos;
layout(location=1) in vec4 params;
layout(location=2) in vec4 fill_color;
layout(location=3) in vec4 border_color;
layout(location=0) out vec4 color;
void main() {
    vec2 half_size = max(params.xy, vec2(0.0));
    float r = clamp(params.z, 0.0, min(half_size.x, half_size.y));
    vec2 q = abs(local_pos) - half_size + vec2(r);
    float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
    float aa = max(fwidth(d), 0.75);
    float outer_cov = 1.0 - smoothstep(-0.5 * aa, 0.5 * aa, d);
    float border_w = max(params.w, 0.0);
    vec4 fill_p = vec4(fill_color.rgb * fill_color.a, fill_color.a);
    vec4 col = fill_p;
    if (border_w > 0.0 && half_size.x > 0.0 && half_size.y > 0.0) {
        float inner_t = smoothstep(-border_w - 0.5 * aa, -border_w + 0.5 * aa, d);
        vec4 border_p = vec4(border_color.rgb * border_color.a, border_color.a);
        col = mix(fill_p, border_p, inner_t);
    }
    color = col * outer_cov;
}

#version 450
layout(location=0) in vec4 in_color;
layout(location=1) in vec2 in_uv;
layout(set=2,binding=0) uniform sampler2D mask;
layout(location=0) out vec4 color;
void main() {
    float cov = texture(mask, in_uv).r;
    float out_a = in_color.a * cov;
    color = vec4(in_color.rgb * out_a, out_a);
}

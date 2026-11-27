#version 450
layout(location=0) in vec2 texture_uv;
layout(set=2,binding=0) uniform sampler2D base_texture;
layout(set=3,binding=0,std140) uniform Cutout { vec4 params; vec4 uv_rect; } cutout;
layout(location=0) out vec4 color;
void main() {
    if (cutout.params.x > 0.0) {
        vec2 sample_uv = cutout.uv_rect.xy + texture_uv * cutout.uv_rect.zw;
        float alpha = cutout.params.y > 0.5 ? texture(base_texture, sample_uv).a : 1.0;
        if (alpha < cutout.params.x) discard;
    }
    color=vec4(gl_FragCoord.z,0.0,0.0,1.0);
}

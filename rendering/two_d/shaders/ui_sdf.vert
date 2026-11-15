#version 450
layout(location=0) in vec2 pos;
layout(location=1) in vec2 local_pos;
layout(location=2) in vec4 params;
layout(location=3) in vec4 fill_color;
layout(location=4) in vec4 border_color;
layout(set=1,binding=0) uniform Viewport { vec4 size; } viewport;
layout(location=0) out vec2 out_local_pos;
layout(location=1) out vec4 out_params;
layout(location=2) out vec4 out_fill_color;
layout(location=3) out vec4 out_border_color;
void main() {
    gl_Position = vec4(pos.x / viewport.size.x * 2.0 - 1.0, 1.0 - pos.y / viewport.size.y * 2.0, 0.0, 1.0);
    out_local_pos = local_pos;
    out_params = params;
    out_fill_color = fill_color;
    out_border_color = border_color;
}

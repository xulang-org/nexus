#version 450
layout(location=0) in vec2 point;
layout(location=1) in vec4 tint;
layout(location=2) in vec2 uv;
layout(set=1,binding=0) uniform Viewport { vec4 size; } viewport;
layout(location=0) out vec4 out_color;
layout(location=1) out vec2 out_uv;
void main() { gl_Position=vec4(point.x/viewport.size.x*2-1,1-point.y/viewport.size.y*2,0,1);out_color=tint;out_uv=uv; }

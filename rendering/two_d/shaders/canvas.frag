#version 450
layout(location=0) in vec4 tint;
layout(location=1) in vec2 uv;
layout(set=2,binding=0) uniform sampler2D image;
layout(location=0) out vec4 color;
void main() { color=tint*texture(image,uv); }

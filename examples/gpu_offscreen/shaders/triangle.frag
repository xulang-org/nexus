#version 450
layout(set=2,binding=0) uniform sampler2D image;
layout(set=3,binding=0) uniform Tint { vec4 tint; };
layout(location=0) out vec4 output_color;
void main() { output_color = texture(image,vec2(0.5,0.5)) * tint; }

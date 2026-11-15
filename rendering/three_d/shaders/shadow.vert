#version 450
layout(location=0) in vec3 position;
layout(set=1,binding=0,std140) uniform Matrix { mat4 mvp; };
void main() { gl_Position=mvp*vec4(position,1.0); }

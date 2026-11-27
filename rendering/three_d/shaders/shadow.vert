#version 450
layout(location=0) in vec3 position;
layout(location=1) in vec2 uv;
layout(set=1,binding=0,std140) uniform Matrix { mat4 mvp; };
layout(location=0) out vec2 texture_uv;
void main() {
    gl_Position=mvp*vec4(position,1.0);
    texture_uv=uv;
}

cbuffer DecalVertUniform : register(b0, space1) {
    column_major float4x4 mvp;
};

struct Input {
    float3 position : TEXCOORD0;
};

float4 main(Input input) : SV_Position {
    return mul(mvp, float4(input.position, 1.0));
}

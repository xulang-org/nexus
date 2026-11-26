cbuffer Matrices : register(b0, space1) {
    column_major float4x4 mvp;
    column_major float4x4 model;
    column_major float4x4 normals;
    column_major float4x4 view;
};

struct Input {
    float3 position : TEXCOORD0;
    float4 color : TEXCOORD1;
    float3 normal : TEXCOORD2;
    float2 uv : TEXCOORD3;
    float4 tangent : TEXCOORD4;
};

struct Output {
    float4 position : SV_Position;
    float4 vertex_color : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 world_normal : TEXCOORD2;
    float2 texture_uv : TEXCOORD3;
    float3 world_tangent : TEXCOORD4;
    float3 world_bitangent : TEXCOORD5;
    float view_depth : TEXCOORD6;
};

Output main(Input input) {
    Output output;
    output.texture_uv = input.uv;
    output.position = mul(mvp, float4(input.position, 1.0));
    output.vertex_color = input.color;
    float4 world4 = mul(model, float4(input.position, 1.0));
    output.world = world4.xyz;
    output.world_tangent = mul(model, float4(input.tangent.xyz, 0.0)).xyz;
    output.world_bitangent = mul(model, float4(cross(input.normal, input.tangent.xyz) * input.tangent.w, 0.0)).xyz;
    output.world_normal = mul(normals, float4(input.normal, 0.0)).xyz;
    output.view_depth = -mul(view, float4(world4.xyz, 1.0)).z;
    return output;
}

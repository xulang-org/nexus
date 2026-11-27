cbuffer TerrainVertUniform : register(b0, space1) {
    column_major float4x4 view_proj;
    column_major float4x4 model;
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
    float2 splat_uv : TEXCOORD3;
    float view_depth : TEXCOORD4;
};

Output main(Input input) {
    Output output;
    float4 world4 = mul(model, float4(input.position, 1.0));
    output.position = mul(view_proj, world4);
    output.vertex_color = input.color;
    output.world = world4.xyz;
    output.world_normal = normalize(mul(model, float4(input.normal, 0.0)).xyz);
    output.splat_uv = input.uv;
    output.view_depth = -mul(view, float4(world4.xyz, 1.0)).z;
    return output;
}

cbuffer Matrices : register(b0, space1) { column_major float4x4 mvp; column_major float4x4 model; column_major float4x4 normals; };
struct Input { float3 position : TEXCOORD0; float4 color : TEXCOORD1; float3 normal : TEXCOORD2; float2 uv : TEXCOORD3; float4 tangent : TEXCOORD4; };
struct Output { float4 position : SV_Position; float4 color : TEXCOORD0; float3 world : TEXCOORD1; float3 normal : TEXCOORD2; float2 uv : TEXCOORD3; float3 tangent : TEXCOORD4; float3 bitangent : TEXCOORD5; };
Output main(Input input) {
    Output output;
    output.position = mul(mvp, float4(input.position, 1.0));
    output.color = input.color; output.uv = input.uv;
    output.world = mul(model, float4(input.position, 1.0)).xyz;
    output.normal = mul(normals, float4(input.normal, 0.0)).xyz;
    output.tangent = mul(model, float4(input.tangent.xyz, 0.0)).xyz;
    output.bitangent = mul(model, float4(cross(input.normal, input.tangent.xyz) * input.tangent.w, 0.0)).xyz;
    return output;
}

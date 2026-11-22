cbuffer Matrix : register(b0,space1) { column_major float4x4 mvp; };
struct Output { float4 position : SV_Position; float2 uv : TEXCOORD0; };
Output main(float3 position : TEXCOORD0, float2 uv : TEXCOORD1) {
    Output output;
    output.position = mul(mvp,float4(position,1.0));
    output.uv = uv;
    return output;
}

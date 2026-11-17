cbuffer Transform : register(b0,space1) { column_major float4x4 transform; };
float4 main(float3 position : TEXCOORD0) : SV_Position {
    return mul(transform,float4(position,1));
}

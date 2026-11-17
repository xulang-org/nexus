cbuffer Matrix : register(b0,space1) { column_major float4x4 mvp; };
float4 main(float3 position : TEXCOORD0) : SV_Position { return mul(mvp,float4(position,1.0)); }

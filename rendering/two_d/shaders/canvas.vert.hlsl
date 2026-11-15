cbuffer Viewport : register(b0,space1) { float4 size; };
struct Input { float2 position : TEXCOORD0; float4 color : TEXCOORD1; float2 uv : TEXCOORD2; };
struct Output { float4 position : SV_Position; float4 color : TEXCOORD0; float2 uv : TEXCOORD1; };
Output main(Input input) { Output result;result.position=float4(input.position.x/size.x*2-1,1-input.position.y/size.y*2,0,1);result.color=input.color;result.uv=input.uv;return result; }

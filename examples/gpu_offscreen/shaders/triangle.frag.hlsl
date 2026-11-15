Texture2D<float4> image : register(t0,space2);
SamplerState image_sampler : register(s0,space2);
cbuffer Tint : register(b0,space3) { float4 tint; };
float4 main() : SV_Target0 { return image.Sample(image_sampler,float2(0.5,0.5)) * tint; }

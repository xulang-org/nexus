cbuffer CutoutBlock : register(b0,space3) { float4 params; float4 uv_rect; };
Texture2D<float4> base_texture : register(t0,space2);
SamplerState base_sampler : register(s0,space2);
float4 main(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target0 {
    if (params.x > 0.0) {
        float2 sample_uv = uv_rect.xy + uv * uv_rect.zw;
        float alpha = params.y > 0.5 ? base_texture.Sample(base_sampler, sample_uv).a : 1.0;
        clip(alpha - params.x);
    }
    return float4(position.z,0.0,0.0,1.0);
}

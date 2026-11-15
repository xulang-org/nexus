Texture2D<float4> mask : register(t0, space2);
SamplerState mask_sampler : register(s0, space2);
struct Input {
    float4 position : SV_Position;
    float4 color : TEXCOORD0;
    float2 uv : TEXCOORD1;
};
float4 main(Input input) : SV_Target0 {
    float cov = mask.Sample(mask_sampler, input.uv).r;
    float out_a = input.color.a * cov;
    return float4(input.color.rgb * out_a, out_a);
}

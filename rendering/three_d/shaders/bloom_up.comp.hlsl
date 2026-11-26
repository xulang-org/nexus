cbuffer BloomUpParams : register(b0, space2) {
    float4 dims;
    float4 weight;
};

Texture2D<float4> src_low : register(t0, space0);
Texture2D<float4> src_curr : register(t1, space0);
SamplerState s_low : register(s0, space0);
SamplerState s_curr : register(s1, space0);
RWTexture2D<float4> dst_tex : register(u0, space1);

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    uint dw = uint(dims.z), dh = uint(dims.w);
    if (gid.x >= dw || gid.y >= dh) return;

    float2 uv = (float2(gid) + 0.5) / float2(dims.z, dims.w);
    float2 texel = float2(1.0 / dims.x, 1.0 / dims.y);

    float3 low =
        src_low.SampleLevel(s_low, uv + float2(-texel.x, -texel.y), 0.0).rgb * 1.0 +
        src_low.SampleLevel(s_low, uv + float2( 0.0,     -texel.y), 0.0).rgb * 2.0 +
        src_low.SampleLevel(s_low, uv + float2( texel.x, -texel.y), 0.0).rgb * 1.0 +
        src_low.SampleLevel(s_low, uv + float2(-texel.x,  0.0    ), 0.0).rgb * 2.0 +
        src_low.SampleLevel(s_low, uv,                              0.0).rgb * 4.0 +
        src_low.SampleLevel(s_low, uv + float2( texel.x,  0.0    ), 0.0).rgb * 2.0 +
        src_low.SampleLevel(s_low, uv + float2(-texel.x,  texel.y), 0.0).rgb * 1.0 +
        src_low.SampleLevel(s_low, uv + float2( 0.0,      texel.y), 0.0).rgb * 2.0 +
        src_low.SampleLevel(s_low, uv + float2( texel.x,  texel.y), 0.0).rgb * 1.0;
    low *= (1.0 / 16.0);

    float3 curr = src_curr.SampleLevel(s_curr, uv, 0.0).rgb;
    dst_tex[gid] = float4(curr + low * weight.x, 1.0);
}

cbuffer HizParams : register(b0, space2) {
    uint sw;
    uint sh;
    uint dw;
    uint dh;
};

Texture2D<float> src_depth : register(t0, space0);
SamplerState src_sampler : register(s0, space0);
RWTexture2D<float4> dst_hiz : register(u0, space1);

[numthreads(8, 8, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint2 gid = dispatch_id.xy;
    if (gid.x >= dw || gid.y >= dh) return;

    float fdx = float(gid.x);
    float fdy = float(gid.y);
    float fdw = float(dw);
    float fdh = float(dh);
    float fsw = float(sw);
    float fsh = float(sh);

    int sx0 = clamp(int(floor((fdx / fdw) * fsw)), 0, int(sw) - 1);
    int sx1 = clamp(int(floor(((fdx + 1.0) / fdw) * fsw - 1e-5)), sx0, int(sw) - 1);
    int sy0 = clamp(int(floor((fdy / fdh) * fsh)), 0, int(sh) - 1);
    int sy1 = clamp(int(floor(((fdy + 1.0) / fdh) * fsh - 1e-5)), sy0, int(sh) - 1);

    float min_d = 1.0;
    float2 inv_src = float2(1.0 / fsw, 1.0 / fsh);
    for (int y = sy0; y <= sy1; ++y) {
        for (int x = sx0; x <= sx1; ++x) {
            float2 uv = (float2(float(x), float(y)) + 0.5) * inv_src;
            float d = src_depth.SampleLevel(src_sampler, uv, 0.0).r;
            min_d = min(min_d, d);
        }
    }
    dst_hiz[gid] = float4(min_d, 0.0, 0.0, 1.0);
}

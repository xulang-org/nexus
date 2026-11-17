struct Input {
    float4 position : SV_Position;
    float2 local_pos : TEXCOORD0;
    float4 params : TEXCOORD1;
    float4 fill_color : TEXCOORD2;
    float4 border_color : TEXCOORD3;
};
float4 main(Input input) : SV_Target0 {
    float2 half_size = max(input.params.xy, float2(0.0, 0.0));
    float r = clamp(input.params.z, 0.0, min(half_size.x, half_size.y));
    float2 q = abs(input.local_pos) - half_size + float2(r, r);
    float d = length(max(q, float2(0.0, 0.0))) + min(max(q.x, q.y), 0.0) - r;
    float aa = max(fwidth(d), 0.75);
    float outer_cov = 1.0 - smoothstep(-0.5 * aa, 0.5 * aa, d);
    float border_w = max(input.params.w, 0.0);
    float4 fill_p = float4(input.fill_color.rgb * input.fill_color.a, input.fill_color.a);
    float4 col = fill_p;
    if (border_w > 0.0 && half_size.x > 0.0 && half_size.y > 0.0) {
        float inner_t = smoothstep(-border_w - 0.5 * aa, -border_w + 0.5 * aa, d);
        float4 border_p = float4(input.border_color.rgb * input.border_color.a, input.border_color.a);
        col = lerp(fill_p, border_p, inner_t);
    }
    return col * outer_cov;
}

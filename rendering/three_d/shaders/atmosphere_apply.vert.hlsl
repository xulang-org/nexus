struct Output {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

Output main(uint vid : SV_VertexID) {
    static const float2 verts[3] = {
        float2(-1.0, -1.0),
        float2(3.0, -1.0),
        float2(-1.0, 3.0)
    };
    float2 p = verts[vid];
    Output output;
    output.position = float4(p, 0.0, 1.0);
    output.uv = float2(p.x * 0.5 + 0.5, 0.5 - p.y * 0.5);
    return output;
}

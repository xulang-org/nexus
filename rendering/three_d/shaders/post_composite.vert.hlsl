struct Output {
    float4 position : SV_Position;
    float2 uv : TEXCOORD0;
};

Output main(uint vid : SV_VertexID) {
    float2 pos = float2((vid == 1u) ? 3.0 : -1.0, (vid == 2u) ? 3.0 : -1.0);
    Output output;
    output.position = float4(pos, 0.0, 1.0);
    output.uv = float2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5);
    return output;
}

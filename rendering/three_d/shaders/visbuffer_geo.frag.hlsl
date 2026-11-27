struct Input {
    float4 position : SV_Position;
    nointerpolation uint meshlet_id : TEXCOORD0;
};

uint main(Input input, uint prim_id : SV_PrimitiveID) : SV_Target0 {
    return (((input.meshlet_id & 0xFFFFFFu) << 8u) | (prim_id & 0xFFu)) + 1u;
}

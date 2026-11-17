float4 main(uint id : SV_VertexID) : SV_Position {
    float2 p[3] = {float2(-1,-1), float2(3,-1), float2(-1,3)};
    return float4(p[id],0,1);
}

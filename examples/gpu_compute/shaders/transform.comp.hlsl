StructuredBuffer<uint> source_data : register(t0, space0);
RWStructuredBuffer<uint> output_data : register(u0, space1);
cbuffer Params : register(b0, space2) { uint multiplier; uint bias; uint count; uint padding; };
[numthreads(64, 1, 1)]
void main(uint3 id : SV_DispatchThreadID) {
    if (id.x < count) output_data[id.x] = source_data[id.x] * multiplier + bias;
}

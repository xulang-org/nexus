struct InstanceGpu {
    column_major float4x4 model;
    column_major float4x4 normals;
    float4 bounds_min;
    float4 bounds_max;
    uint4 draw_info;
};

cbuffer ViewUniform : register(b0, space1) {
    column_major float4x4 view_proj;
    column_major float4x4 view;
};

StructuredBuffer<InstanceGpu> instances : register(t0, space0);

struct Input {
    float3 position : TEXCOORD0;
    float4 color : TEXCOORD1;
    float3 normal : TEXCOORD2;
    float2 uv : TEXCOORD3;
    float4 tangent : TEXCOORD4;
};

struct Output {
    float4 position : SV_Position;
    float4 vertex_color : TEXCOORD0;
    float3 world : TEXCOORD1;
    float3 world_normal : TEXCOORD2;
    float2 texture_uv : TEXCOORD3;
    float3 world_tangent : TEXCOORD4;
    float3 world_bitangent : TEXCOORD5;
    float view_depth : TEXCOORD6;
    nointerpolation uint material_id : TEXCOORD7;
    nointerpolation float orientation : TEXCOORD8;
};

Output main(Input input, uint iid : SV_InstanceID) {
    InstanceGpu inst = instances[iid];
    Output output;
    output.texture_uv = input.uv;
    float4 world4 = mul(inst.model, float4(input.position, 1.0));
    output.position = mul(view_proj, world4);
    output.vertex_color = input.color;
    output.world = world4.xyz;
    output.world_tangent = mul(inst.model, float4(input.tangent.xyz, 0.0)).xyz;
    output.world_bitangent = mul(inst.model, float4(cross(input.normal, input.tangent.xyz) * input.tangent.w, 0.0)).xyz;
    output.world_normal = mul(inst.normals, float4(input.normal, 0.0)).xyz;
    output.view_depth = -mul(view, float4(world4.xyz, 1.0)).z;
    output.material_id = inst.draw_info.w;
    output.orientation = inst.bounds_min.w;
    return output;
}

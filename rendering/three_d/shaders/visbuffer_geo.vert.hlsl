struct MeshletGpu {
    float4 bound_sphere;
    float4 cone;
    uint4 info;
};

struct MeshletInstanceGpu {
    column_major float4x4 model;
    column_major float4x4 normals;
    float4 scale_info;
    float4 base_metallic;
    float4 emission_roughness;
    float4 maps_normal;
    float4 surface;
    float4 uv_rect;
};

cbuffer ViewUniform : register(b0, space1) {
    column_major float4x4 view_proj;
    column_major float4x4 view;
};

StructuredBuffer<MeshletGpu> meshlets : register(t0, space0);
StructuredBuffer<MeshletInstanceGpu> instances : register(t1, space0);

struct Input {
    float3 position : TEXCOORD0;
    float4 color : TEXCOORD1;
    float3 normal : TEXCOORD2;
    float2 uv : TEXCOORD3;
    float4 tangent : TEXCOORD4;
};

struct Output {
    float4 position : SV_Position;
    nointerpolation uint meshlet_id : TEXCOORD0;
};

Output main(Input input, uint iid : SV_InstanceID) {
    MeshletGpu m = meshlets[iid];
    MeshletInstanceGpu inst = instances[m.info.x];
    Output output;
    output.position = mul(view_proj, mul(inst.model, float4(input.position, 1.0)));
    output.meshlet_id = iid;
    return output;
}

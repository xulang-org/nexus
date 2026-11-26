struct SkinInfluence {
    uint4 joints;
    float4 weights;
};

cbuffer SkinParams : register(b0, space2) {
    uint vertex_count;
    uint bone_count;
    uint has_normals;
    uint has_tangents;
};

StructuredBuffer<float> rest_verts : register(t0, space0);
StructuredBuffer<SkinInfluence> influences : register(t1, space0);
StructuredBuffer<float4> joint_palette : register(t2, space0);
RWStructuredBuffer<float> out_verts : register(u0, space1);

[numthreads(64, 1, 1)]
void main(uint3 dispatch_id : SV_DispatchThreadID) {
    uint gid = dispatch_id.x;
    if (gid >= vertex_count) return;
    uint base = gid * 16u;
    SkinInfluence inf = influences[gid];
    float4 r0 = float4(0.0, 0.0, 0.0, 0.0);
    float4 r1 = float4(0.0, 0.0, 0.0, 0.0);
    float4 r2 = float4(0.0, 0.0, 0.0, 0.0);
    for (int k = 0; k < 4; ++k) {
        uint ji = inf.joints[k];
        float w = inf.weights[k];
        if (w > 0.0 && ji < bone_count) {
            uint b = ji * 3u;
            r0 += joint_palette[b + 0u] * w;
            r1 += joint_palette[b + 1u] * w;
            r2 += joint_palette[b + 2u] * w;
        }
    }
    float4 p4 = float4(rest_verts[base + 0u], rest_verts[base + 1u], rest_verts[base + 2u], 1.0);
    out_verts[base + 0u] = dot(r0, p4);
    out_verts[base + 1u] = dot(r1, p4);
    out_verts[base + 2u] = dot(r2, p4);
    out_verts[base + 3u] = rest_verts[base + 3u];
    out_verts[base + 4u] = rest_verts[base + 4u];
    out_verts[base + 5u] = rest_verts[base + 5u];
    out_verts[base + 6u] = rest_verts[base + 6u];

    float3 m0 = r0.xyz, m1 = r1.xyz, m2 = r2.xyz;
    float3 c0 = cross(m1, m2), c1 = cross(m2, m0), c2 = cross(m0, m1);
    float det = dot(m0, c0);
    float det_sign = det < 0.0 ? -1.0 : 1.0;

    float3 nrm = float3(rest_verts[base + 7u], rest_verts[base + 8u], rest_verts[base + 9u]);
    if (has_normals != 0u) {
        float inv_det = (abs(det) > 1e-20) ? (1.0 / det) : det_sign;
        float3 invt = float3(dot(c0, nrm), dot(c1, nrm), dot(c2, nrm)) * inv_det;
        float nlen = length(invt);
        nrm = (nlen > 0.0) ? (invt / nlen) : float3(0.0, 1.0, 0.0);
    }
    out_verts[base + 7u] = nrm.x;
    out_verts[base + 8u] = nrm.y;
    out_verts[base + 9u] = nrm.z;
    out_verts[base + 10u] = rest_verts[base + 10u];
    out_verts[base + 11u] = rest_verts[base + 11u];

    if (has_tangents != 0u) {
        float3 tin = float3(rest_verts[base + 12u], rest_verts[base + 13u], rest_verts[base + 14u]);
        float3 tw = float3(dot(m0, tin), dot(m1, tin), dot(m2, tin));
        float3 ortho = tw - nrm * dot(tw, nrm);
        float olen = length(ortho);
        float3 unit_t = (olen > 0.0) ? (ortho / olen) : float3(1.0, 0.0, 0.0);
        out_verts[base + 12u] = unit_t.x;
        out_verts[base + 13u] = unit_t.y;
        out_verts[base + 14u] = unit_t.z;
        out_verts[base + 15u] = rest_verts[base + 15u] * det_sign;
    } else {
        out_verts[base + 12u] = rest_verts[base + 12u];
        out_verts[base + 13u] = rest_verts[base + 13u];
        out_verts[base + 14u] = rest_verts[base + 14u];
        out_verts[base + 15u] = rest_verts[base + 15u];
    }
}

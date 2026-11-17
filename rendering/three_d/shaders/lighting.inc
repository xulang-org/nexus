#define XU_MAX_LIGHTS 16
// Shared equations for MSL/GLSL/HLSL. GGX distribution, height-correlated
// Smith visibility and Schlick Fresnel; reference: google.github.io/filament.
XU_VEC3 unit_safe(XU_VEC3 value) {
    float largest = max(abs(value.x), max(abs(value.y), abs(value.z)));
    if (!XU_FINITE(largest) || largest == 0.0) return XU_VEC3(0.0, 0.0, 0.0);
    XU_VEC3 scaled = value / largest;
    return scaled / sqrt(dot(scaled, scaled));
}
float srgb_channel(float value) {
    return value <= 0.0031308 ? 12.92 * value : 1.055 * pow(value, 1.0 / 2.4) - 0.055;
}
XU_VEC3 material_direct(XU_VEC3 base, float metallic, float roughness,
    XU_VEC3 normal, XU_VEC3 position, XU_VEC3 eye, XU_VEC3 light, XU_VEC3 radiance) {
    XU_VEC3 n = unit_safe(normal), v = unit_safe(eye - position), l = unit_safe(light), h = unit_safe(v + l);
    float nv = max(dot(n, v), 0.0001), nl = max(dot(n, l), 0.0);
    float nh = max(dot(n, h), 0.0), vh = clamp(dot(v, h), 0.0, 1.0);
    float alpha = roughness * roughness, a2 = alpha * alpha;
    float denominator = (nh * a2 - nh) * nh + 1.0;
    float distribution = a2 / (3.14159265359 * max(denominator * denominator, 0.000000000001));
    float visibility = 0.5 / max(nl * sqrt(nv * nv * (1.0 - a2) + a2) +
        nv * sqrt(nl * nl * (1.0 - a2) + a2), 0.000001);
    XU_VEC3 f0 = XU_MIX(XU_VEC3(0.04, 0.04, 0.04), base, metallic);
    float factor = pow(1.0 - vh, 5.0);
    XU_VEC3 fresnel = f0 + (XU_VEC3(1.0, 1.0, 1.0) - f0) * factor;
    XU_VEC3 diffuse = (XU_VEC3(1.0, 1.0, 1.0) - fresnel) * (1.0 - metallic) * base / 3.14159265359;
    return (diffuse + distribution * visibility * fresnel) * radiance * nl;
}
// Point/spot radiance is an inverse-square intensity, smoothly extinguished at
// radius. The 0.01-world-unit near clamp bounds intensity. Coincident source
// and surface have no defined incoming direction and contribute zero.
XU_VEC3 source_direct(XU_VEC3 base, float metallic, float roughness,
    XU_VEC3 normal, XU_VEC3 position, XU_VEC3 eye, XU_VEC4 position_kind,
    XU_VEC4 direction_range, XU_VEC4 radiance_inner, XU_VEC4 cone) {
    XU_VEC3 light = direction_range.xyz;
    float attenuation = 1.0;
    if (position_kind.w > 0.5) {
        XU_VEC3 delta = position_kind.xyz - position;
        float distance2 = dot(delta, delta), radius2 = direction_range.w * direction_range.w;
        if (distance2 < 0.000000000001 || distance2 >= radius2) return XU_VEC3(0.0, 0.0, 0.0);
        light = delta / sqrt(distance2);
        float relative2 = distance2 / radius2;
        float edge = max(0.0, 1.0 - relative2 * relative2);
        attenuation = edge * edge / max(distance2, 0.0001);
        if (position_kind.w > 1.5) {
            float cosine = dot(direction_range.xyz, -light);
            float transition = clamp((cosine - cone.x) / max(radiance_inner.w - cone.x, 0.000001), 0.0, 1.0);
            attenuation *= transition * transition * (3.0 - 2.0 * transition);
        }
    }
    return material_direct(base, metallic, roughness, normal, position, eye, light, radiance_inner.xyz * attenuation);
}
XU_VEC3 finish_lighting(XU_VEC3 linear_color, float exposure) {
    XU_VEC3 exposed = max(linear_color * exposure, XU_VEC3(0.0, 0.0, 0.0));
    XU_VEC3 mapped = exposed / (XU_VEC3(1.0, 1.0, 1.0) + exposed);
    return XU_VEC3(srgb_channel(mapped.x), srgb_channel(mapped.y), srgb_channel(mapped.z));
}

// Re-orthogonalize interpolated world tangents against inverse-transpose N.
// Transformed local B is an orientation reference: it includes tangent W and
// reflected model transforms without relying on an unscaled determinant.
XU_VEC3 normal_map_direction(XU_VEC3 normal, XU_VEC3 tangent, XU_VEC3 bitangent,
    XU_VEC3 texel, float scale) {
    XU_VEC3 n = unit_safe(normal);
    if (scale == 0.0) return n;
    XU_VEC3 t = unit_safe(tangent);
    t = unit_safe(t - n * dot(n, t));
    XU_VEC3 b = unit_safe(cross(n, t));
    if (dot(b, unit_safe(bitangent)) < 0.0) b = -b;
    XU_VEC3 mapped = texel * 2.0 - XU_VEC3(1.0, 1.0, 1.0);
    mapped.x *= scale; mapped.y *= scale;
    mapped = unit_safe(mapped);
    XU_VEC3 result = unit_safe(t * mapped.x + b * mapped.y + n * mapped.z);
    if (dot(result, result) == 0.0) return n;
    return result;
}

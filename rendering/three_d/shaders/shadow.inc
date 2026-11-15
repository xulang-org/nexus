// World-aligned faces match resources/shadow: +X,-X,+Y,-Y,+Z,-Z.
int point_shadow_face(XU_VEC3 d) {
    XU_VEC3 a = abs(d);
    if (a.x >= a.y && a.x >= a.z) return d.x >= 0.0 ? 0 : 1;
    if (a.y >= a.z) return d.y >= 0.0 ? 2 : 3;
    return d.z >= 0.0 ? 4 : 5;
}
XU_VEC2 point_shadow_uv(XU_VEC3 d, int face) {
    XU_VEC2 p;
    if (face == 0) p = XU_VEC2(d.z,d.y) / abs(d.x);
    else if (face == 1) p = XU_VEC2(-d.z,d.y) / abs(d.x);
    else if (face == 2) p = XU_VEC2(d.x,d.z) / abs(d.y);
    else if (face == 3) p = XU_VEC2(-d.x,d.z) / abs(d.y);
    else if (face == 4) p = XU_VEC2(-d.x,d.y) / abs(d.z);
    else p = XU_VEC2(d.x,d.y) / abs(d.z);
    return p * XU_VEC2(0.5,-0.5) + XU_VEC2(0.5,0.5);
}
XU_VEC3 point_shadow_ray(XU_VEC2 uv, int face) {
    XU_VEC2 p = uv * XU_VEC2(2.0,-2.0) + XU_VEC2(-1.0,1.0);
    if (face == 0) return XU_VEC3(1.0,p.y,p.x);
    if (face == 1) return XU_VEC3(-1.0,p.y,-p.x);
    if (face == 2) return XU_VEC3(p.x,1.0,p.y);
    if (face == 3) return XU_VEC3(-p.x,-1.0,p.y);
    if (face == 4) return XU_VEC3(-p.x,p.y,1.0);
    return XU_VEC3(p.x,p.y,-1.0);
}
float point_shadow_visibility(XU_VEC3 world, XU_VEC3 normal,
    XU_VEC4 light_bias, XU_VEC4 shadow_filter, XU_VEC4 depth, XU_SHADOW_RESOURCES) {
    // World-plane derivatives remain continuous across face selection seams.
    XU_VEC3 n = unit_safe(cross(XU_DDX(world),XU_DDY(world)));
    if (dot(n,n) == 0.0) n = unit_safe(normal);
    XU_VEC3 delta = world-light_bias.xyz;
    float major = max(abs(delta.x),max(abs(delta.y),abs(delta.z)));
    float receiver_z = depth.x / max(major,0.000001) - depth.y;
    if (major <= 0.000001 || receiver_z < 0.0 || receiver_z > 1.0) return 1.0;
    int face = point_shadow_face(delta);
    XU_VEC2 uv = point_shadow_uv(delta,face);
    float plane_distance = dot(n,delta);
    float bias = light_bias.w + shadow_filter.y * (1.0-max(0.0,dot(unit_safe(normal),unit_safe(-delta))));
    float visibility = 0.0;
    float weight_sum = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            XU_VEC2 tap = (floor(uv/shadow_filter.x) + XU_VEC2(float(x),float(y)) + XU_VEC2(0.5,0.5)) * shadow_filter.x;
            XU_VEC2 distance_in_texels = tap/shadow_filter.x-uv/shadow_filter.x;
            XU_VEC2 weights = max(XU_VEC2(1.5,1.5)-abs(distance_in_texels),XU_VEC2(0.0,0.0));
            float weight = weights.x*weights.y;
            weight_sum += weight;
            if (weight <= 0.0) continue;
            // A tap past an edge is projected onto its actual neighboring face.
            // Quantize there, then intersect the receiver plane with that texel's
            // ray; never sample across unrelated packed atlas tile boundaries.
            XU_VEC3 ray = point_shadow_ray(tap,face);
            int adjacent = point_shadow_face(ray);
            XU_VEC2 at = (clamp(floor(point_shadow_uv(ray,adjacent)/shadow_filter.x),XU_VEC2(0.0,0.0),XU_VEC2(1.0/shadow_filter.x-1.0,1.0/shadow_filter.x-1.0)) + XU_VEC2(0.5,0.5)) * shadow_filter.x;
            ray = point_shadow_ray(at,adjacent);
            float denominator = dot(n,ray);
            if (abs(denominator) <= 0.000001) { visibility += weight; continue; }
            float distance = plane_distance / denominator;
            if (distance <= 0.0) { visibility += weight; continue; }
            float reference = depth.x/distance-depth.y;
            if (reference < 0.0 || reference > 1.0) { visibility += weight; continue; }
            XU_VEC2 atlas = (at + XU_VEC2(float(adjacent%3),float(adjacent/3))) / depth.zw;
            visibility += (reference + bias >= XU_SHADOW_READ(atlas) ? 1.0 : 0.0) * weight;
        }
    }
    return visibility / weight_sum;
}
XU_VEC2 cascade_gradient(XU_VEC3 p) {
    XU_VEC3 n = unit_safe(cross(XU_DDX(p),XU_DDY(p)));
    if (abs(n.z) <= 0.00001) return XU_VEC2(0.0,0.0);
    return XU_VEC2(-2.0*n.x,2.0*n.y)/n.z;
}
float cascade_sample(XU_VEC3 p, XU_VEC2 gradient, int layer, float bias,
    float texel, XU_VEC2 atlas_size, float raster_bias, XU_SHADOW_RESOURCES) {
    if (p.x < -1.0 || p.x > 1.0 || p.y < -1.0 || p.y > 1.0 || p.z < 0.0 || p.z > 1.0) return 1.0;
    // Sub-texel raster precision needs a geometric slope bias as well as
    // the caller's normal/depth bias. Author normals can be smoothed.
    bias += max(abs(gradient.x),abs(gradient.y))*texel*raster_bias;
    XU_VEC2 uv = XU_VEC2(p.x*0.5+0.5,0.5-p.y*0.5);
    float visible = 0.0, total = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            XU_VEC2 at = (floor(uv/texel)+XU_VEC2(float(x),float(y))+XU_VEC2(0.5,0.5))*texel;
            XU_VEC2 weights = max(XU_VEC2(1.5,1.5)-abs((at-uv)/texel),XU_VEC2(0.0,0.0));
            float weight = weights.x*weights.y;
            total += weight;
            if (weight <= 0.0) continue;
            if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) { visible += weight; continue; }
            XU_VEC2 atlas = (at+XU_VEC2(float(layer%2),float(layer/2)))/atlas_size;
            visible += (p.z+dot(gradient,at-uv)+bias >= XU_SHADOW_READ(atlas) ? 1.0 : 0.0)*weight;
        }
    }
    return visible/total;
}
float cascade_shadow_visibility(XU_VEC3 world, XU_VEC3 normal,
    XU_VEC4 p0, XU_VEC4 p1, XU_VEC4 p2, XU_VEC4 p3,
    XU_VEC4 camera, XU_VEC4 r0, XU_VEC4 r1, XU_VEC4 r2, XU_VEC4 r3,
    XU_VEC4 limits, XU_VEC4 light_bias, XU_VEC4 shadow_filter, XU_VEC4 atlas, XU_VEC4 gradient_scales, XU_SHADOW_RESOURCES) {
    // All orthographic slices share their basis. Derive once in the first
    // projection and rescale; derivatives never depend on a selected branch.
    XU_VEC2 g0=cascade_gradient(p0.xyz);
    XU_VEC2 g1=g0*gradient_scales.y, g2=g0*gradient_scales.z, g3=g0*gradient_scales.w;
    float distance=dot(camera,XU_VEC4(world,1.0));
    if (distance < limits.x || distance > limits.y) return 1.0;
    int layer=0;
    if (distance > r0.y && limits.z > 1.5) layer=1;
    if (distance > r1.y && limits.z > 2.5) layer=2;
    if (distance > r2.y && limits.z > 3.5) layer=3;
    XU_VEC3 p=p0.xyz; XU_VEC2 g=g0; XU_VEC4 range=r0;
    XU_VEC3 next_p=p1.xyz; XU_VEC2 next_g=g1; XU_VEC4 next_range=r1;
    if (layer==1) { p=p1.xyz;g=g1;range=r1;next_p=p2.xyz;next_g=g2;next_range=r2; }
    if (layer==2) { p=p2.xyz;g=g2;range=r2;next_p=p3.xyz;next_g=g3;next_range=r3; }
    if (layer==3) { p=p3.xyz;g=g3;range=r3; }
    float bias=light_bias.w+shadow_filter.y*(1.0-max(0.0,dot(unit_safe(normal),light_bias.xyz)));
    float current=cascade_sample(p,g,layer,bias*range.w,shadow_filter.x,atlas.zw,limits.w,XU_SHADOW_ARGS);
    if (range.y > range.z && distance > range.z) {
        float next=1.0;
        if (float(layer+1) < limits.z) next=cascade_sample(next_p,next_g,layer+1,bias*next_range.w,shadow_filter.x,atlas.zw,limits.w,XU_SHADOW_ARGS);
        float alpha=clamp((distance-range.z)/(range.y-range.z),0.0,1.0);
        alpha=alpha*alpha*(3.0-2.0*alpha);
        current=XU_MIX(current,next,alpha);
    }
    return current;
}
// Manual nearest-depth 3x3 PCF, independent of comparison-sampler support.
float shadow_visibility(XU_VEC3 world, XU_VEC3 normal, XU_MAT4 mvp,
    XU_VEC4 direction_bias, XU_VEC4 shadow_filter, XU_VEC4 depth, XU_SHADOW_RESOURCES) {
    if (shadow_filter.w > 2.5) return point_shadow_visibility(world,normal,direction_bias,shadow_filter,depth,XU_SHADOW_ARGS);
    XU_VEC4 projected = XU_MUL(mvp, XU_VEC4(world, 1.0));
    XU_VEC3 p = projected.xyz / max(projected.w,0.000001);
    // A geometric triangle remains a plane after homogeneous projection.
    // Derive depth against NDC XY: works for orthographic AND perspective
    // projections, independently of authored normals and camera orientation.
    // Evaluate derivatives before spatially divergent early returns.
    XU_VEC3 n = unit_safe(cross(XU_DDX(p), XU_DDY(p)));
    XU_VEC2 gradient = XU_VEC2(0.0,0.0);
    if (abs(n.z) > 0.00001) gradient = XU_VEC2(-2.0*n.x,2.0*n.y) / n.z;
    if (projected.w <= 0.000001 || p.x < -1.0 || p.x > 1.0 || p.y < -1.0 || p.y > 1.0 || p.z < 0.0 || p.z > 1.0) return 1.0;
    XU_VEC2 uv = XU_VEC2(p.x * 0.5 + 0.5, 0.5 - p.y * 0.5);
    XU_VEC3 toward_light = direction_bias.xyz;
    if (shadow_filter.w > 1.5) toward_light = unit_safe(direction_bias.xyz-world);
    float bias = direction_bias.w + shadow_filter.y * (1.0 - max(0.0, dot(unit_safe(normal), toward_light)));
    // Compare at the receiver plane's depth at each actual texel center.
    // A constant reference across PCF taps self-shadows sloped surfaces.
    float visibility = 0.0;
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            XU_VEC2 at = (floor(uv / shadow_filter.x) + XU_VEC2(float(x), float(y)) + XU_VEC2(0.5,0.5)) * shadow_filter.x;
            if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) visibility += 1.0;
            else visibility += (p.z + dot(gradient,at-uv) + bias >= XU_SHADOW_READ(at)) ? 1.0 : 0.0;
        }
    }
    return visibility / 9.0;
}

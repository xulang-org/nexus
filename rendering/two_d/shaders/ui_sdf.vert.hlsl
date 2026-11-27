cbuffer Viewport : register(b0,space1) { float4 size; };
struct Input {
    float2 pos : TEXCOORD0;
    float2 local_pos : TEXCOORD1;
    float4 params : TEXCOORD2;
    float4 fill_color : TEXCOORD3;
    float4 border_color : TEXCOORD4;
};
struct Output {
    float4 position : SV_Position;
    float2 local_pos : TEXCOORD0;
    float4 params : TEXCOORD1;
    float4 fill_color : TEXCOORD2;
    float4 border_color : TEXCOORD3;
};
Output main(Input input) {
    Output output;
    output.position = float4(input.pos.x / size.x * 2.0 - 1.0, 1.0 - input.pos.y / size.y * 2.0, 0.0, 1.0);
    output.local_pos = input.local_pos;
    output.params = input.params;
    output.fill_color = input.fill_color;
    output.border_color = input.border_color;
    return output;
}

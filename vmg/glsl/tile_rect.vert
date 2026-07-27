#version 410
// Vertex shader for tile-based display of rectangular images

uniform mat3 ndc_X_opx = mat3(1);  // converts image pixels to normalized device coordinates

layout(location = 1) in vec2 vp_opx;  // input rectified image pixel coordinates
layout(location = 2) in vec2 vp_ttc;  // input tile texture coordinates

out vec2 p_opx;  // output image pixel coordinates
out vec2 p_ttc;  // output tile texture coordinates
flat out int vID;

void main()
{
    vec3 p_ndc = ndc_X_opx * vec3(vp_opx, 1);
    gl_Position = vec4(p_ndc.xy/p_ndc.z, 0.5, 1);
    p_opx = vp_opx;
    p_ttc = vp_ttc;
    vID = gl_VertexID;
}

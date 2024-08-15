#version 410
// Vertex shader for tile-based display of rectangular images

mat3 ndc_X_omp = mat3(1);  // converts image pixels to normalized device coordinates

layout(location = 1) in vec2 vp_omp;  // input rectified image pixel coordinates
layout(location = 2) in vec2 vp_tcr;  // input tile raw texture coordinates

out vec2 p_omp;  // output image pixel coordinates
out vec2 p_tcr;  // output tile raw texture coordinates

void main()
{
    vec3 p_ndc = vb.ndc_X_omp * vec3(p_omp, 1);
    gl_Position = vec4(p_ndc.xy / p_ndc.z, 0.5, 1);
    p_omp = vp_omp;
    p_tcr = vp_tcr;
}

#version 410

// vertex shader for selection box portions beyond the boundary of the image

uniform mat3 ndc_X_omp = mat3(1);  // converts image pixels to normalized device coordinates
uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);  // selection box left top right bottom
uniform float omp_scale_qwn = 1.0;  // ratio of image pixel size to window pixel size

const float line_width_qwn = 1.8;  // box outline line width in window pixels

// Create a bunch of named constants to help reason about the stream of vertices we generate

// index into sel_rect_omp
const int left = 0;
const int top = 1;
const int right = 2;
const int bottom = 3;

// masks for inner/outer boundaries of selection box edges
const int inner = -1;
const int outer = +1;

// which way is "outer" for each selection box edge
const ivec4 outer_dir = ivec4(-1, -1, +1, +1);

struct vtx_mask {
    int x;
    int y;
    int edge;
};

// values used to construct the outline vertices for a triangle strip with ten vertices
const vtx_mask outline[10] = vtx_mask[10](
    vtx_mask(left, top, outer),
    vtx_mask(left, top, inner),
    vtx_mask(right, top, outer),
    vtx_mask(right, top, inner),
    vtx_mask(right, bottom, outer),
    vtx_mask(right, bottom, inner),
    vtx_mask(left, bottom, outer),
    vtx_mask(left, bottom, inner),
    vtx_mask(left, top, outer),
    vtx_mask(left, top, inner)
);

void main()
{
    // host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 10)"
    vtx_mask vtx = outline[gl_VertexID];
    float hlw = 0.5 * omp_scale_qwn * line_width_qwn;  // half line width, in image pixels
    vec3 p_omp = vec3(  // vertex in image pixel coordinates
        sel_rect_omp[vtx.x] + outer_dir[vtx.x] * vtx.edge * hlw,
        sel_rect_omp[vtx.y] + outer_dir[vtx.y] * vtx.edge * hlw,
        1);
    // convert image pixel coordinates to opengl ndc coordinates
    vec3 p_ndc = ndc_X_omp * p_omp;
    gl_Position = vec4(p_ndc.xy / p_ndc.z, 0.5, 1);
}

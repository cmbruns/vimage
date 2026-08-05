#version 410

// vertex shader for selection box portions beyond the boundary of the image

uniform mat3 ndc_X_opx = mat3(1);  // converts image pixels to normalized device coordinates
uniform ivec4 sel_rect_opx = ivec4(100, 150, 200, 300);  // selection box left top right bottom
uniform float opx_scale_qwn = 1.0;  // ratio of image pixel size to window pixel size

const float line_width_qwn = 2.5;  // box outline line width in window pixels

// Create a bunch of named constants to help reason about the stream of vertices we generate

// index into sel_rect_opx
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

out float edge_index;

void main()
{
    // If selection box is empty, generate degenerate equal vertexes
    if (sel_rect_opx.x == 0 && sel_rect_opx.z == 0) {
        gl_Position = vec4(0);
        return;
    }

    // host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 10)"
    vtx_mask vtx = outline[gl_VertexID];
    float hlw = 0.5 * opx_scale_qwn * line_width_qwn;  // half line width, in image pixels
    vec3 p_opx = vec3(  // vertex in image pixel coordinates
        sel_rect_opx[vtx.x] + outer_dir[vtx.x] * vtx.edge * hlw,
        sel_rect_opx[vtx.y] + outer_dir[vtx.y] * vtx.edge * hlw,
        1);
    // convert image pixel coordinates to opengl ndc coordinates
    vec3 p_ndc = ndc_X_opx * p_opx;
    gl_Position = vec4(p_ndc.xy / p_ndc.z, 0.5, 1);

    edge_index = float(gl_VertexID / 2);
}

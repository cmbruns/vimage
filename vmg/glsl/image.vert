#version 410

// Vertex shader for vimage

layout(location = 1) in vec2 pos_nic;  // normalized image coordinates
layout(location = 2) in vec2 pos_txc;  // texture coordinates

// host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)"
const vec4 SCREEN_QUAD[4] = vec4[4](
    vec4( 1, -1, 0.5, 1),  // lower right
    vec4( 1,  1, 0.5, 1),  // upper right
    vec4(-1, -1, 0.5, 1),  // lower left
    vec4(-1,  1, 0.5, 1)   // upper left
);

mat2 flip_y() {
    return mat2(
        1, 0,
        0, -1);
}

mat2 scale(float s) {
    return mat2(
        s, 0,
        0, s);
}

mat2 scale2(float sx, float sy) {
    return mat2(
        sx, 0,
        0, sy);
}

uniform sampler2D image;
uniform float window_zoom = 1.0;
uniform vec2 image_center_img = vec2(0.5, 0.5);
uniform ivec2 window_size;
uniform mat2 raw_rot_omp = mat2(1);

out vec2 p_tex;
out vec2 p_omp;
out float omp_scale_qwn;

// coordinate systems:
//  ndc - normalized device coordinates ; range -1,1 ; origin at center ; positive y up
//  cwn - window ; origin at center ; units window pixels ; positive y up ; origin at center
//  ont - oriented image coordinates ; units image pixels ; positive y down ; origin at center
//  raw - raw image coordinates (before EXIF orientation correction) ; origin at center
//  ulc - raw image with origin at upper left
//  tex - texture coordinates ; range (0, 1)
//  img - image texture coordinates, but with orientation correction

void main() {
    // set position for each corner vertex
    gl_Position = SCREEN_QUAD[gl_VertexID];
    vec2 p_ndc = gl_Position.xy / gl_Position.w;

    ivec2 image_size_raw = textureSize(image, 0);
    // flip aspect if exif transform is 90 degrees
    float image_aspect_raw = image_size_raw.x / float(image_size_raw.y);
    vec2 image_size_omp = image_size_raw;
    float image_aspect_omp = image_aspect_raw;
    if (raw_rot_omp[0][0] == 0) {  // EXIF orientation is rotated 90 degrees
        image_aspect_omp = 1.0 / image_aspect_raw;
        image_size_omp = image_size_raw.yx;
    }
    float window_aspect = window_size.x / float(window_size.y);
    vec2 p_cwn = 0.5 * vec2(window_size) * p_ndc;  // centered window pixels
    // zoom value depends on relative aspect ratio of window to image
    omp_scale_qwn = image_size_omp.y / window_size.y / window_zoom;
    // compare aspect ratios to figure how to fit image in window
    if (window_aspect < image_aspect_omp)
        omp_scale_qwn = image_size_omp.x / window_size.x / window_zoom;
    vec2 p_comp = vec2(omp_scale_qwn, -omp_scale_qwn) * p_cwn;  // oriented image pixels
    vec2 p_raw = raw_rot_omp * p_comp;  // raw image pixels
    vec2 p_ulc = p_raw + 0.5 * vec2(image_size_raw);  // move origin from center to upper left corner
    // image_center is in oriented texture coordinates w/ ulc origin
    vec2 d_center_tex = raw_rot_omp * (image_center_img - vec2(0.5));

    p_tex = (1.0 / image_size_raw) * p_ulc + d_center_tex;
    p_omp = p_comp + image_center_img * image_size_omp;  // move center to ulc
}

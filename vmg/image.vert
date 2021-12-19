#version 410

// Vertex shader for vimage

// host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)"
const vec4 SCREEN_QUAD[4] = vec4[4](
    vec4( 1, -1, 0.5, 1),  // lower right
    vec4( 1,  1, 0.5, 1),  // upper right
    vec4(-1, -1, 0.5, 1),  // lower left
    vec4(-1,  1, 0.5, 1)   // upper left
);

mat3 flip_y() {
    return mat3(
        1, 0, 0,
        0, -1, 0,
        0, 0, 1);
}

mat3 scale(float s) {
    return mat3(
        s, 0, 0,
        0, s, 0,
        0, 0, 1);
}

mat3 scale2(float sx, float sy) {
    return mat3(
        sx, 0, 0,
        0, sy, 0,
        0, 0, 1);
}

mat3 translate(vec2 t) {
    return mat3(
        1, 0, 0,
        0, 1, 0,
        t.x, t.y, 1);
}

uniform sampler2D image;
uniform float window_zoom = 1.0;
uniform vec2 image_center = vec2(0.0, 0.5);
uniform ivec2 window_size;
out vec3 tex_coord;

void main() {
    // set position for each corner vertex
    vec4 ndc = SCREEN_QUAD[gl_VertexID];
    gl_Position = ndc;
    // begin building transform to convert from window ndc coordinates to image texture coordinates
    mat3 tc_X_ndc = scale(0.5) * flip_y();
    // compare aspect ratios to figure how to fit image in window
    ivec2 image_size = textureSize(image, 0);
    float image_aspect = image_size.x / float(image_size.y);
    float window_aspect = window_size.x / float(window_size.y);
    if (window_aspect > image_aspect)  // fat window, skinny image, pad at left/right
        tc_X_ndc = scale2(window_aspect / image_aspect, 1.0) * tc_X_ndc;
    else
        tc_X_ndc = scale2(1.0, image_aspect / window_aspect) * tc_X_ndc;
    //
    tc_X_ndc = scale(1.0 / window_zoom) * tc_X_ndc;
    tc_X_ndc = translate(image_center) * tc_X_ndc;
    tex_coord = tc_X_ndc * ndc.xyw;
}

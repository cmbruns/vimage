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
uniform vec2 image_center = vec2(0.0, 0.5);
uniform ivec2 window_size;
uniform float window_zoom = 1.0;

out vec3 tex_coord;

void main() {
    // set position for each corner vertex
    vec4 ndc = SCREEN_QUAD[gl_VertexID];
    gl_Position = ndc;
    float window_aspect = window_size.x / float(window_size.y);
    float wa2 = sqrt(window_aspect);
    vec2 xy = ndc.xy * vec2(wa2, 1/wa2) / window_zoom;
    tex_coord = vec3(xy, ndc.z) / ndc.w;
}

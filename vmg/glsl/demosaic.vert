#version 410 core

// host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)"
const vec4 SCREEN_QUAD[4] = vec4[4](
    vec4( 1, -1, 0.5, 1),  // lower right
    vec4( 1,  1, 0.5, 1),  // upper right
    vec4(-1, -1, 0.5, 1),  // lower left
    vec4(-1,  1, 0.5, 1)   // upper left
);

const vec2 TEX_COORD[4] = vec2[4](
    vec2( 1,  0),  // lower right
    vec2( 1,  1),  // upper right
    vec2( 0,  0),  // lower left
    vec2( 0,  1)   // upper left
);

out vec2 tex_coord;

void main() {
    gl_Position = SCREEN_QUAD[gl_VertexID];
    tex_coord = TEX_COORD[gl_VertexID];
}

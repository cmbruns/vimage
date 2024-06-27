#version 410

// Vertex shader for vimage (rectangular, not 360)

uniform mat3 omp_X_ndc = mat3(1);
uniform mat3 tex_X_ndc = mat3(1);

out vec2 p_omp;  // oriented image pixel coordinates
out vec2 p_tex;  // image normalized texture coordinates

// host side draw call should be "glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)"
const vec4 SCREEN_QUAD[4] = vec4[4](
    vec4( 1, -1, 0.5, 1),  // lower right
    vec4( 1,  1, 0.5, 1),  // upper right
    vec4(-1, -1, 0.5, 1),  // lower left
    vec4(-1,  1, 0.5, 1)   // upper left
);

void main() {
    // set position for each corner vertex
    gl_Position = SCREEN_QUAD[gl_VertexID];
    vec3 p_ndc = vec3(gl_Position.xy / gl_Position.w, 1);

    p_omp = (omp_X_ndc * p_ndc).xy;
    p_tex = (tex_X_ndc * p_ndc).xy;
}

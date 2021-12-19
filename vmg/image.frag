#version 410

uniform sampler2D image;
in vec3 tex_coord;
out vec4 color;

void main() {
    vec2 tc = tex_coord.xy / tex_coord.z;
    if (tc.x < 0 || tc.y < 0 || tc.x > 1 || tc.y > 1)
        color = vec4(0);
    else
        color = texture(image, tc);
}

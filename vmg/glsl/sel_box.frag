#pragma include "shared.frag"

// fragment shader for selection box sections outside of the main image

uniform vec4 background_color = vec4(0.5);

out vec4 sel_box_color;

in float edge_index;

const vec3 LINEAR_BLUE_STANDARD = vec3(0.013, 0.232, 1.000);
const vec3 LINEAR_BLUE_PALE     = vec3(0.300, 0.500, 1.000);
const vec3 LINEAR_BLUE_DARK     = vec3(0.000, 0.043, 0.900);

void main()
{
    const int dashes_per_edge = 20;
    int edge_step = int(fract(edge_index) * dashes_per_edge);
    if (edge_step % 2 == 0)
        sel_box_color = vec4(LINEAR_BLUE_PALE, 0.5);
    else
        sel_box_color = vec4(LINEAR_BLUE_DARK, 0.5);
}

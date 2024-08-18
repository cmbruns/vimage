#pragma include "shared.frag"

// fragment shader for selection box sections outside of the main image

uniform vec4 background_color = vec4(0.5);

out vec4 sel_box_color;

// TODO: move to shared.frag
vec4 box_color(vec3 base_color) {
    vec3 color = vec3(1) - base_color;
    // but inverted can be invisible on gray backgrounds
    if (length(color - base_color) < 0.5) {
        if (length(base_color.rgb) > 0.5)
            color = vec3(0);  // black box for light gray image
        else
            color = vec3(1);  // white box for dark gray image
    }
    return vec4(color, 1);
}

void main()
{
    // sel_box_color = vec4(1, 0, 0, 1);
    // return;

    sel_box_color = box_color(background_color.rgb);
}

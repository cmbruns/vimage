#pragma include "shared.frag"

uniform sampler2D image;
uniform int pixelFilter = NEAREST;
uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);  // left top bottom right

in vec2 p_tex;
in vec2 p_omp;
in float omp_scale_qwn;

out vec4 image_color;

void main()
{
    // clip to image boundary
    if (p_tex.x < 0 || p_tex.y < 0 || p_tex.x > 1 || p_tex.y > 1) {
        image_color = vec4(0);
        return;
    }

    switch(pixelFilter) {
    case NEAREST:
        image_color = nearest(image, p_tex);
        break;
    case CATMULL_ROM:
        image_color = catrom(image, p_tex);
        break;
    }

    // selection box
    float line_width_qwn = 1.8;  // box outline line width in window pixels
    float hlw = 0.5 * omp_scale_qwn * line_width_qwn;  // half line width, in image pixels
    // Is this pixel on the box outline?
    if (p_omp.x >= sel_rect_omp.x - hlw &&  // left clip
        p_omp.x <= sel_rect_omp.z + hlw &&  // right clip
        p_omp.y >= sel_rect_omp.y - hlw &&  // top clip
        p_omp.y <= sel_rect_omp.w + hlw && (  // bottom clip
          abs(p_omp.x - sel_rect_omp.x) <= hlw ||  // on left edge
          abs(p_omp.x - sel_rect_omp.z) <= hlw ||  // on right edge
          abs(p_omp.y - sel_rect_omp.y) <= hlw ||  // on top edge
          abs(p_omp.y - sel_rect_omp.w) <= hlw)  // on bottom edge
    ) {
        // invert color, similar to irfanview
        vec4 box_color = vec4(1, 1, 1, 2) - image_color;
        // but inverted can be invisible on gray backgrounds
        if (length(box_color.xyz - image_color.xyz) < 0.5) {
            if (length(image_color.xyz) > 0.5)
                box_color = vec4(0, 0, 0, 1);  // black box for light gray image
            else
                box_color = vec4(1, 1, 1, 1);  // white box for dark gray image
        }
        image_color = vec4(1, 1, 1, 2) - image_color;
    }

    // sRGB conversion should be the FINAL step of the fragment shader
    image_color = srgb_from_linear(image_color);
}

#pragma include "shared.frag"

uniform sampler2D image;
uniform int pixelFilter = FILTER_NEAREST;
uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);  // left top bottom right
uniform vec4 background_color = vec4(0.5);

in vec2 p_tex;
in vec2 p_omp;
in float omp_scale_qwn;

out vec4 image_color;

void main()
{
    image_color = clip_n_filter(image, p_tex, pixelFilter, false);

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
        vec4 base_color = mix(background_color, image_color, image_color.a);
        vec3 box_color = vec3(1) - base_color.rgb;
        // but inverted can be invisible on gray backgrounds
        if (length(box_color.rgb - image_color.rgb) < 0.5) {
            if (length(base_color.rgb) > 0.5)
                box_color = vec3(0);  // black box for light gray image
            else
                box_color = vec3(1);  // white box for dark gray image
        }
        image_color = vec4(box_color, 1);
    }

    // sRGB conversion should be the FINAL step of the fragment shader
    // image_color = srgb_from_linear(image_color);
}

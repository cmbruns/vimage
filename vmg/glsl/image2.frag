#pragma include "shared.frag"

uniform sampler2D image;
uniform int pixelFilter = FILTER_NEAREST;
uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);  // left top bottom right
uniform vec4 background_color = vec4(0.5);
uniform float omp_scale_qwn;

in vec2 p_tex;
in vec2 p_omp;

out vec4 image_color;

void main()
{
    image_color = clip_n_filter(image, p_tex, pixelFilter, false);
    image_color = selection_box(p_omp, image_color, background_color, sel_rect_omp, omp_scale_qwn);
}

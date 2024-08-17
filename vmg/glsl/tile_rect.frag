#pragma include "shared.frag"
// sketch of rectangular shader August 2024

uniform sampler2D tile;
uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);// left top bottom right
uniform vec4 background_color = vec4(0.5);
uniform int pixel_filter = FILTER_NEAREST;
uniform float omp_scale_qwn = 1.0;

in vec2 p_omp;
in vec2 p_tcr;

out vec4 image_color;

void main()
{
    float mipmapLevel = textureQueryLod(tile, p_tcr).x;
    if (mipmapLevel > 0 || pixel_filter == FILTER_NEAREST)
        image_color = texture(tile, p_tcr);
    else
        image_color = catrom(tile, p_tcr, false);

    image_color = selection_box(p_omp, image_color, background_color, sel_rect_omp, omp_scale_qwn);
}

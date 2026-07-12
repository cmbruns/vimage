#pragma include "shared.frag"
// rectangular shader

uniform sampler2D tile;
uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);// left top bottom right
uniform vec4 background_color = vec4(0.5);
uniform int pixel_filter = FILTER_NEAREST;
uniform float omp_scale_qwn = 1.0;
uniform float brightness = 0.0;
uniform bool input_is_linear = false;

in vec2 p_omp;
in vec2 p_tcr;

out vec4 image_color;

void main()
{
    /*
    float mipmapLevel = textureQueryLod(tile, p_tcr).x;
    if (mipmapLevel > 0 || pixel_filter == FILTER_NEAREST)
        image_color = texture(tile, p_tcr);
    else
        image_color = catrom(tile, p_tcr, false);
    /* */
    image_color = clip_n_filter(tile, p_tcr, pixel_filter, false);
    
    // Apply brightness
    vec4 linear;
    if (input_is_linear) linear = image_color;
    else linear = linear_from_srgb(image_color);
    vec4 brightened = vec4(pow(2.0, brightness) * linear.rgb, linear.a);  // apply to linear...

    image_color = srgb_from_linear(brightened);

    // OK to do texel boundary and selection box composition in sRGB space...
    image_color = texel_boundaries(image_color, p_tcr * textureSize(tile, 0));
    image_color = selection_box(p_omp, image_color, background_color, sel_rect_omp, omp_scale_qwn);
}

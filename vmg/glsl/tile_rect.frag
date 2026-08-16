#pragma include "shared.frag"
// rectangular shader

uniform sampler2D tile;
uniform ivec4 sel_rect_opx = ivec4(100, 150, 200, 300);// left top bottom right
uniform vec4 background_color = vec4(0.5);
uniform int pixel_filter = FILTER_NEAREST;
uniform float opx_scale_qwn = 1.0;
uniform float brightness = 0.0;
uniform bool input_is_linear = false;

// DNG only
uniform vec3 black_level = vec3(0);
uniform vec3 white_level = vec3(1);
uniform vec3 as_shot_neutral = vec3(1);
uniform mat3 lsr_X_wba = mat3(1);

in vec2 p_opx;
in vec2 p_ttc;

out vec4 image_color;

void main()
{
    image_color = clip_n_filter(tile, p_ttc, pixel_filter, false);
    
    // Apply brightness
    vec4 linear;
    if (input_is_linear) linear = image_color;
    else linear = linear_from_srgb(image_color);

    linear.rgb = linear_srgb_from_sensor(linear.rgb, black_level, white_level, as_shot_neutral, lsr_X_wba);

    vec4 brightened = vec4(pow(2.0, brightness) * linear.rgb, linear.a);  // apply to linear...

    image_color = srgb_from_linear(brightened);

    // OK to do texel boundary and selection box composition in sRGB space...
    image_color = texel_boundaries(image_color, p_ttc * textureSize(tile, 0));
    // image_color = selection_box(p_opx, image_color, background_color, sel_rect_opx, opx_scale_qwn);
}

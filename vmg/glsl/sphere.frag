#pragma include "shared.frag"

uniform int input_format = EQUIRECT_INPUT_FORMAT;
uniform int display_projection = STEREOGRAPHIC_DISPLAY_PROJECTION;

uniform sampler2D tile;
uniform int pixelFilter = FILTER_NEAREST;
uniform mat3 ont_rot_obq = mat3(1);
uniform mat3 raw_rot_ont = mat3(1);
uniform mat3 tile_X_img = mat3(1);
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform float brightness = 0.0;
uniform bool input_is_linear = false;

in vec2 p_nic;
out vec4 color;

void main() {
    vec3 p_obq;

    switch(display_projection) {
        case STEREOGRAPHIC_DISPLAY_PROJECTION:
            p_obq = stereographic_xyz(p_nic);
            break;
        case AZ_EQ_DISPLAY_PROJECTION:
            if (! azeqd_valid(p_nic)) {
                color = vec4(0);
                return;
            }
            p_obq = azimuthal_equidistant_xyz(p_nic);
            break;
        case GNOMONIC_DISPLAY_PROJECTION:
            p_obq = gnomonic_xyz(p_nic);
            break;
        case EQUIRECT_DISPLAY_PROJECTION:
        default :
            if (! equirect_valid(p_nic)) {
                color = vec4(0);
                return;
            }
            p_obq = equirect_xyz(p_nic);
            break;
    }

    vec3 p_raw = raw_rot_ont * ont_rot_obq * p_obq;
    vec2 p_img_tex;  // Texture coordinate in full image
    switch(input_format) {
        case DUAL_FISHEYE_INPUT_FORMAT:
            p_img_tex = gear360_2016_tex_coord(
                    p_raw,
                    df_fov_radians,  // fisheye field of view
                    df_lens_rot_radians);  // lens rotation offset
            break;
        case EQUIRECT_INPUT_FORMAT:
        default :
            p_img_tex = equirect_tex_coord(p_raw);
            break;
    }

    // TODO: two texture coordinates to blend for dual fisheye

    p_img_tex = p_img_tex - floor(p_img_tex); // Shift to range 0-1

    vec2 p_tile_tex = (tile_X_img * vec3(p_img_tex, 1)).xy;

    color = clip_n_filter(tile, p_tile_tex, pixelFilter, true);

    // Apply brightness
    vec4 linear;
    if (input_is_linear) linear = color;
    else linear = linear_from_srgb(color);
    vec4 brightened = pow(2.0, brightness) * linear;  // apply to linear...

    color = srgb_from_linear(brightened);

    // OK to do overlays like texel boundaries and bounding box in srgb space
    color = texel_boundaries(color, p_tile_tex * textureSize(tile, 0));
}

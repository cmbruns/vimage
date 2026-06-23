#pragma include "shared.frag"

uniform int input_projection = EQUIRECT_INPUT_PROJECTION;
uniform int display_projection = STEREOGRAPHIC_DISPLAY_PROJECTION;

uniform sampler2D image;
uniform int pixelFilter = FILTER_NEAREST;
uniform mat3 ont_rot_obq = mat3(1);
uniform mat3 raw_rot_ont = mat3(1);

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
    vec2 p_tex;
    switch(input_projection) {
        case DUAL_FISHEYE_INPUT_PROJECTION:
            p_tex = gear360_2016_tex_coord(p_raw);
            break;
        case EQUIRECT_INPUT_PROJECTION:
        default :
            p_tex = equirect_tex_coord(p_raw);
            break;
    }
    color = clip_n_filter(image, p_tex, pixelFilter, true);

    // sRGB conversion should be the FINAL step of the fragment shader
    // color = srgb_from_linear(color);
}

#pragma include "shared.frag"

uniform int projection = STEREOGRAPHIC_PROJECTION;

uniform sampler2D image;
uniform int pixelFilter = FILTER_NEAREST;
uniform mat3 ont_rot_obq = mat3(1);
uniform mat3 raw_rot_ont = mat3(1);

in vec2 p_nic;
out vec4 color;

void main() {
    vec3 p_obq;

    switch(projection) {
        case STEREOGRAPHIC_PROJECTION:
            p_obq = stereographic_xyz(p_nic);
            break;
        case AZ_EQ_PROJECTION:
            if (! azeqd_valid(p_nic)) {
                color = vec4(0);
                return;
            }
            p_obq = azimuthal_equidistant_xyz(p_nic);
            break;
        case GNOMONIC_PROJECTION:
            p_obq = gnomonic_xyz(p_nic);
            break;
        case EQUIRECT_PROJECTION:
        default :
            if (! equirect_valid(p_nic)) {
                color = vec4(0);
                return;
            }
            p_obq = equirect_xyz(p_nic);
            break;
    }

    vec3 p_raw = raw_rot_ont * ont_rot_obq * p_obq;
    vec2 p_tex = equirect_tex_coord(p_raw);
    color = clip_n_filter(image, p_tex, pixelFilter, true);

    // sRGB conversion should be the FINAL step of the fragment shader
    // color = srgb_from_linear(color);
}

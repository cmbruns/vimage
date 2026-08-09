#pragma include "shared.frag"

uniform sampler2D tile;
uniform sampler2D numerals;

uniform int display_projection = STEREOGRAPHIC_DISPLAY_PROJECTION;

uniform int input_format = EQUIRECT_INPUT_FORMAT;
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform int render_pass = 1;  // for tiled dual fisheye

uniform int   channel_count = 3;  // set from host
uniform float format_max = 255;
uniform float data_max = 255;
uniform mat2 rotation = mat2(1);
uniform int pixel_numerals = NUMERALS_HEXADECIMAL;

in vec2 p_nic;
out vec4 fragColor;

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // app-view-modified world 3D coordinates (obq)
    vec3 p_obq = obq_for_nic(p_nic, display_projection);
    if (p_obq == INVALID_OBQ) discard;

    // Convert direction to sky-up world frame (geo), then to camera frame (raw)
    vec3 p_pcm = pcm_rot_geo * geo_rot_obq * p_obq;

    TexCoordAlpha tca = tcr_for_pcm(
            p_pcm,
            input_format,
            df_fov_radians,
            df_lens_rot_radians,
            render_pass);

    if (tca.alpha == 0.0) discard;

    fragColor = numeral_color(
            p_ttc,
            tile,
            numerals,
            channel_count,
            format_max,
            data_max,
            rotation,
            pixel_numerals);
}

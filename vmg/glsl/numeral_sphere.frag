#pragma include "shared.frag"

uniform sampler2D tile;
uniform sampler2D numerals;

// tile related
uniform mat3 tile_X_img;
uniform vec4 uv_bounds = vec4(0, 0, 1, 1);  // (u_min, v_min, u_max, v_max)

// pano related
uniform int display_projection = STEREOGRAPHIC_DISPLAY_PROJECTION;
uniform mat3 geo_rot_usr = mat3(1);
uniform mat3 pcm_rot_geo = mat3(1);

// input format related
uniform int input_format = EQUIRECT_INPUT_FORMAT;
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform int render_pass = 1;  // for tiled dual fisheye

// numeral related
uniform int   channel_count = 3;  // set from host
uniform float format_max = 255;
uniform float data_max = 255;
uniform int pixel_numerals = NUMERALS_HEXADECIMAL;
uniform mat2 rotation = mat2(1);

in vec2 p_nic;
out vec4 fragColor;

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // app-view-modified world 3D coordinates (usr)
    vec3 p_usr = usr_for_nic(p_nic, display_projection);
    if (p_usr == INVALID_USR) discard;

    // Convert direction to sky-up world frame (geo), then to camera frame (raw)
    vec3 p_pcm = pcm_rot_geo * geo_rot_usr * p_usr;

    TexCoordAlpha tca = rtc_for_pcm(
            p_pcm,
            input_format,
            df_fov_radians,
            df_lens_rot_radians,
            render_pass);

    if (tca.alpha == 0.0) discard;

    vec2 p_ttc = ttc_for_rtc(tile_X_img, tca.p_rtc);

    if (p_ttc.x < uv_bounds[0]
        || p_ttc.y < uv_bounds[1]
        || p_ttc.x > uv_bounds[2]
        || p_ttc.y > uv_bounds[3])
    {
        discard;
    }

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

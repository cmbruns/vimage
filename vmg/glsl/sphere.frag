#pragma include "shared.frag"

uniform int input_format = EQUIRECT_INPUT_FORMAT;
uniform int display_projection = STEREOGRAPHIC_DISPLAY_PROJECTION;

uniform sampler2D tile;
uniform int pixelFilter = FILTER_NEAREST;
uniform mat3 ont_rot_obq = mat3(1);
uniform mat3 raw_rot_ont = mat3(1);
uniform mat3 tile_X_img = mat3(1);
uniform vec4 uv_bounds = vec4(0, 0, 1, 1);  // (u_min, v_min, u_max, v_max)
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform float brightness = 0.0;
uniform bool input_is_linear = false;
uniform int render_pass = 1;  // for tiled dual fisheye

in vec2 p_nic;
out vec4 color;


void main()
{
    // Convert normalized image screen coordinates (nic) to
    // app-view-modified world 3D coordinates (obq)
    vec3 p_obq = obq_for_nic(p_nic, display_projection);
    if (p_obq == INVALID_OBQ) discard;

    // Convert direction to sky-up world frame (ont), then to camera frame (raw)
    vec3 p_raw = raw_rot_ont * ont_rot_obq * p_obq;

    // Look up tile texture coordinate(s)
    vec2 p_tcr;  // Full image texture coordinate
    vec2 p_tct;  // Tile texture coordinate
    switch(input_format) {
        case DUAL_FISHEYE_INPUT_FORMAT:
            TexCoordPair pair = dual_fisheye_tex_coord(
                    p_raw,
                    df_fov_radians,  // fisheye field of view
                    df_lens_rot_radians);  // lens rotation offset
            float alpha = 1.0;
            if (render_pass == 2)  {
                alpha = 1.0 - pair.front_bias;
                p_tcr = pair.rear_tc;
                if (pair.front_bias >= 1) discard;
            }
            else {
                alpha = 1.0;  // first pass fully overwrites every valid pixel
                p_tcr = pair.front_tc;
                if (pair.front_bias <= 0) discard;
            }

            p_tct = tct_for_tcr(tile_X_img, p_tcr);
            color = clip_n_filter(tile, p_tct, pixelFilter, true);
            color.a = alpha;
            break;
        case EQUIRECT_INPUT_FORMAT:
        default:
            vec2 p_img_tex = equirect_tex_coord(p_raw);
            p_tct = tct_for_tcr(tile_X_img, p_img_tex);
            color = clip_n_filter(tile, p_tct, pixelFilter, true);
            break;
    }

    // TODO: valid get tile texture bounds from a uniform
    if (p_tct.x < uv_bounds[0]
        || p_tct.y < uv_bounds[1]
        || p_tct.x > uv_bounds[2]
        || p_tct.y > uv_bounds[3])
    {
        discard;
    }

    // Apply brightness
    vec4 linear;
    if (input_is_linear) linear = color;
    else linear = linear_from_srgb(color);
    vec4 brightened = vec4(pow(2.0, brightness) * linear.rgb, linear.a);  // apply to linear...

    color = srgb_from_linear(brightened);

    // OK to do overlays like texel boundaries and bounding box in srgb space
    color = texel_boundaries(color, p_tct * textureSize(tile, 0));
}

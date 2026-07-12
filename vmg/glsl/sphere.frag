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

vec2 tct_for_tcr(vec2 tcr) {
    tcr = tcr - floor(tcr); // Shift to range 0-1
    return (tile_X_img * vec3(tcr, 1)).xy;
}

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // app-view-modified world 3D coordinates (obq)
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
            vec2 front_tct = tct_for_tcr(pair.front_tc);
            vec2 rear_tct = tct_for_tcr(pair.rear_tc);
            if (pair.front_bias > 0.5) {
                p_tcr = pair.front_tc;
                p_tct = front_tct;
            }
            else {
                p_tcr = pair.rear_tc;
                p_tct = rear_tct;
            }
            vec4 front_color = clip_n_filter(tile, front_tct, pixelFilter, true);
            vec4 rear_color = clip_n_filter(tile, rear_tct, pixelFilter, true);
            color = mix(rear_color, front_color, pair.front_bias);
            break;
        case EQUIRECT_INPUT_FORMAT:
        default :
            vec2 p_img_tex = equirect_tex_coord(p_raw);
            p_tct = tct_for_tcr(p_img_tex);
            color = clip_n_filter(tile, p_tct, pixelFilter, true);
            break;
    }

    // TODO: valid get tile texture bounds from a uniform
    if (p_tct.x < 0 || p_tct.x > 1 || p_tct.y < 0 || p_tct.y > 1) {
        color = vec4(0);
        return;
    }

    const bool is_dng = false;  // TODO: proper DNG shading
    if (is_dng) {
        // For Bayer mosaic we need to know the parity of this texel
        // in the full image, not just the tile.
        // What's the upper left of the full image in tile coordinates?
        vec3 ul_full_tct = tile_X_img * vec3(0, 0, 1);
        vec2 tile_offset_texels = -ul_full_tct.xy * textureSize(tile, 0);
        vec2 this_texel_in_tile = p_tct * textureSize(tile, 0);
        ivec2 img_texel = ivec2(floor(this_texel_in_tile + tile_offset_texels));
        bool rowEven = (img_texel.y & 1) == 0;
        bool colEven = (img_texel.x & 1) == 0;
        // RGGB Bayer pattern
        if      ( rowEven &&  colEven) color = color * vec4(1, 0, 0, 1);  // red
        else if ( rowEven && !colEven) color = color * vec4(0, 1, 0, 1);  // green
        else if (!rowEven &&  colEven) color = color * vec4(0, 1, 0, 1);  // green
        else if (!rowEven && !colEven) color = color * vec4(0, 0, 1, 1);  // blue
    }

    // Apply brightness
    vec4 linear;
    if (input_is_linear) linear = color;
    else linear = linear_from_srgb(color);
    vec4 brightened = pow(2.0, brightness) * linear;  // apply to linear...

    color = srgb_from_linear(brightened);

    // OK to do overlays like texel boundaries and bounding box in srgb space
    color = texel_boundaries(color, p_tct * textureSize(tile, 0));
}

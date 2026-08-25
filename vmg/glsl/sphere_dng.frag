#pragma include "shared.frag"

/*
Spherical panorama shader for digital negative DNG raw camera images
/* */

// bayer_tile is the raw dng bytes:
//   one channel
//   no mipmaps, but functions as the unofficial level zero mipmap
//   always nearest neighbor filter
//   texels are colored by this shader as either red, green or blue
// NOTE: no setting explicit texture units here in glsl 410,
//   which is the highest Mac supports.
uniform sampler2D bayer_tile;  // true raw DNG bytes
// The base level zero mipmap of demosaic_tile is the virtual level 1 mipmap of bayer_tile
uniform sampler2D demosaic_tile;  // previously demosaicked RGB with mipmaps

// dual fisheye is the only raw dng spherical panorama we know about.
// const int input_format = DUAL_FISHEYE_INPUT_FORMAT;
// const bool input_is_linear = true;

// All image types
uniform float brightness;
uniform int pixelFilter = FILTER_NEAREST;  // applies only to demosaic
uniform mat3 tile_X_img;

// 360 only
uniform int display_projection = STEREOGRAPHIC_DISPLAY_PROJECTION;
uniform mat3 geo_rot_usr = mat3(1);
uniform mat3 pcm_rot_geo = mat3(1);
uniform vec4 uv_bounds = vec4(0, 0, 1, 1);  // (u_min, v_min, u_max, v_max)

// Dual fisheye only
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform vec4 df_front_center_scale = vec4(0.75, 0.5, 0.5, 1.0);
uniform vec4 df_rear_center_scale = vec4(0.25, 0.5, 0.5, 1.0);
uniform int render_pass = 1;

// DNG only
uniform vec3 black_level = vec3(0);
uniform vec3 white_level = vec3(1);
uniform vec3 as_shot_neutral = vec3(1);
uniform mat3 lsr_X_wba = mat3(1);
uniform ivec4 cfa_pattern = ivec4(0, 1, 1, 2);
uniform bool show_cfa_colors = true;

in vec2 p_nic;
out vec4 color;


vec4 color_sphere(vec3 p) {
    return vec4(0.5 * (p + vec3(1)), 1);
}

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // viewer-space 3D direction (usr)
    vec3 p_usr = usr_for_nic(p_nic, display_projection);
    if (p_usr == INVALID_USR) discard;

    // Convert direction to sky-up physical camera world frame (geo),
    // then to physical camera frame 3D direction (raw)
    vec3 p_pcm = pcm_rot_geo * geo_rot_usr * p_usr;

    TexCoordAlpha tca = rtc_for_pcm(
            p_pcm,
            DUAL_FISHEYE_INPUT_FORMAT,
            df_fov_radians,
            df_lens_rot_radians,
            df_front_center_scale,
            df_rear_center_scale,
            render_pass);

    if (tca.alpha == 0.0) discard;

    vec2 p_rtc = tca.p_rtc;

    // Compute lod before bounds clip,
    // to avoid derivative problems near the edges.
    float lod = textureQueryLod(demosaic_tile, p_rtc).y;

    vec2 p_ttc = ttc_for_rtc(tile_X_img, p_rtc);  // Tile texture coordinate

    // Clip to tile
    if (p_ttc.x < uv_bounds[0]
        || p_ttc.y < uv_bounds[1]
        || p_ttc.x > uv_bounds[2]
        || p_ttc.y > uv_bounds[3])
    discard;

    // TODO: allow manual front/rear bias adjustment

    vec4 demosaic_color = clip_n_filter(demosaic_tile, p_ttc, pixelFilter, true);

    if (show_cfa_colors) {
        // TODO: should bayer_color have a sharp transition along the seam?
        vec4 bayer_color = texture(bayer_tile, p_ttc);

        // For Bayer mosaic we need to know the parity of this texel
        //   in the full image, not just the tile.
        // What's the upper left of the full image in tile coordinates?
        vec3 ul_full_ttc = tile_X_img * vec3(0, 0, 1);
        vec2 tile_offset_texels = -ul_full_ttc.xy * textureSize(bayer_tile, 0);
        vec2 this_texel_in_tile = p_ttc * textureSize(bayer_tile, 0);
        ivec2 img_texel = ivec2(floor(this_texel_in_tile + tile_offset_texels));
        bayer_color = bayer_tint(img_texel, bayer_color, cfa_pattern);

        // Blend bayer and demosaicked depending on mipmap level
        // At high zoom the user sees the pure raw DNG mosaic.
        // At lower zoom, the user sees the demosaicked RGB interpretation.
        float demosaic_bias = clamp(lod + 10, 0.0, 4.0) * 0.25;  // Blended color between lod 0->1

        const bool debug = false;
        if (debug) {
            // Visualize lods
            color = vec4(0, demosaic_bias, 0, 1);
            return;
            // demosaic_bias = 1.0;  // pure demosaic
        }

        // Raw sensor color "sns"
        color = mix(bayer_color, demosaic_color, demosaic_bias);
    }
    else {
        color = demosaic_color;
    }

    color.a = tca.alpha;

    color.rgb = linear_srgb_from_sensor(color.rgb, black_level, white_level, as_shot_neutral, lsr_X_wba);

    // Apply user brightness
    // DNG is always photometrically linear
    color.rgb *= pow(2.0, brightness);

    // The very final step of basic raw color processing is to apply the
    // customary display gamma.
    color = srgb_from_linear(color);

    // It's OK to do overlays like texel boundaries and bounding box in
    // gamma srgb space
    // If we are zoomed in enough to see texel boundaries, it's the
    // Bayer ones we should see.
    color = texel_boundaries(color, p_ttc * textureSize(bayer_tile, 0));
}

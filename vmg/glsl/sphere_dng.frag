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
uniform mat3 ont_rot_obq = mat3(1);
uniform mat3 pcm_rot_geo = mat3(1);
uniform vec4 uv_bounds = vec4(0, 0, 1, 1);  // (u_min, v_min, u_max, v_max)

// Dual fisheye only
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform int render_pass = 1;

// DNG only
uniform vec3 black_level = vec3(0);
uniform vec3 white_level = vec3(1);
uniform vec3 as_shot_neutral = vec3(1);
uniform mat3 lsr_X_rfv = mat3(1);

in vec2 p_nic;
out vec4 color;


vec4 color_sphere(vec3 p) {
    return vec4(0.5 * (p + vec3(1)), 1);
}

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // viewer-space 3D direction (obq)
    vec3 p_obq = obq_for_nic(p_nic, display_projection);
    if (p_obq == INVALID_OBQ) discard;

    // Convert direction to sky-up physical camera world frame (ont),
    // then to physical camera frame 3D direction (raw)
    vec3 p_pcm = pcm_rot_geo * ont_rot_obq * p_obq;

    // Look up tile texture coordinate(s)
    vec2 p_tcr;  // Full image texture coordinate
    // Always dual fisheye with DNG as far as we know
    TexCoordPair pair = dual_fisheye_tex_coord(
            p_pcm,
            df_fov_radians,  // fisheye field of view
            df_lens_rot_radians);  // lens rotation offset
    float alpha = 1.0;
    if (render_pass == 1) {
        alpha = 1.0;  // first pass fully overwrites every valid pixel
        p_tcr = pair.front_tc;
        if (pair.front_bias <= 0) discard;
    }
    else if (render_pass == 2)  {
        alpha = 1.0 - pair.front_bias;  // blend second pass
        p_tcr = pair.rear_tc;
        if (pair.front_bias >= 1) discard;
    }
    else discard;

    vec2 p_tct = tct_for_tcr(tile_X_img, p_tcr);  // Tile texture coordinate

    // Clip to tile
    if (   p_tct.x < uv_bounds[0]
        || p_tct.y < uv_bounds[1]
        || p_tct.x > uv_bounds[2]
        || p_tct.y > uv_bounds[3])
        discard;

    // TODO: allow manual front/rear bias adjustment

    vec4 demosaic_color = clip_n_filter(demosaic_tile, p_tct, pixelFilter, true);
    // TODO: should bayer_color have a sharp transition along the seam?
    vec4 bayer_color = texture(bayer_tile, p_tct);

    // For Bayer mosaic we need to know the parity of this texel
    //   in the full image, not just the tile.
    // What's the upper left of the full image in tile coordinates?
    vec3 ul_full_tct = tile_X_img * vec3(0, 0, 1);
    vec2 tile_offset_texels = -ul_full_tct.xy * textureSize(bayer_tile, 0);
    vec2 this_texel_in_tile = p_tct * textureSize(bayer_tile, 0);
    ivec2 img_texel = ivec2(floor(this_texel_in_tile + tile_offset_texels));
    bayer_color = bayer_tint(img_texel, bayer_color);

    // Blend bayer and demosaicked depending on mipmap level
    // At high zoom the user sees the pure raw DNG mosaic.
    // At lower zoom, the user sees the demosaicked RGB interpretation.
    // TODO: this goes wonky near tile boundaries
    //  maybe use analytic jacobians
    float lod = textureQueryLod(demosaic_tile, p_tcr).y;
    float demosaic_bias = clamp(lod + 10, 0.0, 4.0) * 0.25;  // Blended color between lod 0->1

    const bool debug = false;
    if (debug) {
        // Visualize lods
        color = vec4(0, demosaic_bias, 0, 1);
        return;
        // demosaic_bias = 1.0;  // pure demosaic
    }

    color = mix(bayer_color, demosaic_color, demosaic_bias);
    color.a = alpha;

    // black level
    color.rgb = max(color.rgb - black_level, vec3(0));
    // white level
    color.rgb = min(color.rgb/(white_level - black_level), vec3(1));

    // clip so highlights are neutral
    color.rgb = min(color.rgb, as_shot_neutral);

    // up gain so non-clipped values fill valid range
    float gain = min(min(as_shot_neutral.r, as_shot_neutral.g), as_shot_neutral.b);
    color.rgb = color.rgb / gain;

    // convert to linear sRGB
    color.rgb = lsr_X_rfv * color.rgb;

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
    color = texel_boundaries(color, p_tct * textureSize(bayer_tile, 0));
}

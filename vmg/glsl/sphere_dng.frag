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
uniform mat3 raw_rot_ont = mat3(1);

// Dual fisheye only
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;

in vec2 p_nic;
out vec4 color;

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // viewer-space 3D direction (obq)
    vec3 p_obq = obq_for_nic(p_nic, display_projection);

    // Convert direction to sky-up physical camera world frame (ont),
    // then to physical camera frame 3D direction (raw)
    vec3 p_raw = raw_rot_ont * ont_rot_obq * p_obq;

    // Look up tile texture coordinate(s)
    vec2 p_tcr;  // Full image texture coordinate
    vec2 p_tct;  // Tile texture coordinate
    // Always dual fisheye with DNG as far as we know
    TexCoordPair pair = dual_fisheye_tex_coord(
            p_raw,
            df_fov_radians,  // fisheye field of view
            df_lens_rot_radians);  // lens rotation offset
    vec2 front_tct = tct_for_tcr(tile_X_img, pair.front_tc);
    vec2 rear_tct = tct_for_tcr(tile_X_img, pair.rear_tc);
    if (pair.front_bias > 0.5) {
        p_tcr = pair.front_tc;
        p_tct = front_tct;
    }
    else {
        p_tcr = pair.rear_tc;
        p_tct = rear_tct;
    }

    // TODO: allow manual front/rear bias adjustment

    vec4 front_color_d = clip_n_filter(demosaic_tile, front_tct, pixelFilter, true);
    vec4 rear_color_d = clip_n_filter(demosaic_tile, rear_tct, pixelFilter, true);
    vec4 demosaic_color = mix(rear_color_d, front_color_d, pair.front_bias);

    vec4 front_color_b = texture(bayer_tile, front_tct);
    vec4 rear_color_b = texture(bayer_tile, rear_tct);
    // TODO: should bayer_color have a sharp transition along the seam?
    vec4 bayer_color = mix(rear_color_b, front_color_b, pair.front_bias);

    // For Bayer mosaic we need to know the parity of this texel
    //   in the full image, not just the tile.
    // What's the upper left of the full image in tile coordinates?
    vec3 ul_full_tct = tile_X_img * vec3(0, 0, 1);
    vec2 tile_offset_texels = -ul_full_tct.xy * textureSize(bayer_tile, 0);
    vec2 this_texel_in_tile = p_tct * textureSize(bayer_tile, 0);
    ivec2 img_texel = ivec2(floor(this_texel_in_tile + tile_offset_texels));
    bool rowEven = (img_texel.y & 1) == 0;
    bool colEven = (img_texel.x & 1) == 0;
    // RGGB Bayer pattern
    if      ( rowEven &&  colEven) bayer_color = bayer_color * vec4(4, 0, 0, 1);  // red
    else if ( rowEven && !colEven) bayer_color = bayer_color * vec4(0, 2, 0, 1);  // green
    else if (!rowEven &&  colEven) bayer_color = bayer_color * vec4(0, 2, 0, 1);  // green
    else if (!rowEven && !colEven) bayer_color = bayer_color * vec4(0, 0, 4, 1);  // blue

    // Blend bayer and demosaicked depending on mipmap level
    // At high zoom the user sees the pure raw DNG mosaic.
    // At lower zoom, the user sees the demosaicked RGB interpretation.
    float lod = textureQueryLod(bayer_tile, p_tct).y;
    float demosaic_bias = clamp(lod + 4, 0.0, 4.0);  // Blended color between lod 0->1
    color = mix(bayer_color, demosaic_color, demosaic_bias * 0.25);

    // TODO: black level, white level, white balance, color_matrix,
    //  XYZ->linear sRGB, tone mapping,

    // Apply user brightness
    // DNG is always photometrically linear
    vec4 brightened = pow(2.0, brightness) * color;  // apply to linear...

    // The very final step of basic raw color processing is to apply the
    // customary display gamma.
    color = srgb_from_linear(brightened);

    // It's OK to do overlays like texel boundaries and bounding box in srgb space
    // If we are zoomed in enough to see texel boundaries, it's the
    // Bayer ones we should see.
    color = texel_boundaries(color, p_tct * textureSize(bayer_tile, 0));
}

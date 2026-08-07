#pragma include "shared.frag"
// rectangular shader for DNG raw files

uniform sampler2D bayer_tile;  // true raw DNG bytes
// The base level zero mipmap of demosaic_tile is the virtual level 1 mipmap of bayer_tile
uniform sampler2D demosaic_tile;  // previously demosaicked RGB with mipmaps

uniform ivec4 sel_rect_omp = ivec4(100, 150, 200, 300);// left top bottom right
uniform vec4 background_color = vec4(0.5);
uniform int pixel_filter = FILTER_NEAREST;
uniform float omp_scale_qwn = 1.0;
uniform float brightness = 0.0;
uniform mat3 tile_X_img;

// DNG only
uniform vec3 black_level = vec3(0);
uniform vec3 white_level = vec3(1);
uniform vec3 as_shot_neutral = vec3(1);
uniform mat3 lsr_X_wba = mat3(1);

in vec2 p_opx;
in vec2 p_ttc;

out vec4 color;

void main()
{

    vec4 demosaic_color = clip_n_filter(demosaic_tile, p_ttc, pixel_filter, false);
    vec4 bayer_color = texture(bayer_tile, p_ttc);

    // For Bayer mosaic we need to know the parity of this texel
    //   in the full image, not just the tile.
    // What's the upper left of the full image in tile coordinates?
    vec3 ul_full_tct = tile_X_img * vec3(0, 0, 1);
    vec2 tile_offset_texels = -ul_full_tct.xy * textureSize(bayer_tile, 0);
    vec2 this_texel_in_tile = p_ttc * textureSize(bayer_tile, 0);
    ivec2 img_texel = ivec2(floor(this_texel_in_tile + tile_offset_texels));
    bayer_color = bayer_tint(img_texel, bayer_color);

    // Blend bayer and demosaicked depending on mipmap level
    // At high zoom the user sees the pure raw DNG mosaic.
    // At lower zoom, the user sees the demosaicked RGB interpretation.
    float lod = textureQueryLod(bayer_tile, p_ttc).y;
    float demosaic_bias = clamp(lod + 6, 0.0, 4.0);  // Blended color between lod 0->1
    color = mix(bayer_color, demosaic_color, demosaic_bias * 0.25);

    // black level sns -> bkc
    color.rgb = max(color.rgb - black_level, vec3(0));
    // white level bkc -> rfv (camera "linear reference value" in DNG spec)
    color.rgb = min(color.rgb/(white_level - black_level), vec3(1));

    // rfv -> wba  white balanced
    color.rgb /= as_shot_neutral;
    // clip so highlights are neutral, to avoid magenta sun
    color.rgb = min(color.rgb, vec3(1));

    // convert to linear sRGB
    color.rgb = lsr_X_wba * color.rgb;

    // Apply brightness
    color.rgb *= pow(2.0, brightness);

    color = srgb_from_linear(color);

    // OK to do texel boundary and selection box composition in sRGB space...
    color = texel_boundaries(color, p_ttc * textureSize(bayer_tile, 0));
    color = selection_box(p_opx, color, background_color, sel_rect_omp, omp_scale_qwn);
}

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

in vec2 p_omp;
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
    bool rowEven = (img_texel.y & 1) == 0;
    bool colEven = (img_texel.x & 1) == 0;
    // RGGB Bayer pattern - compromise between pure gray and totally saturated
    const float gpt = 0.6;  // gray component of bayer false coloring
    if      ( rowEven &&  colEven) bayer_color = bayer_color * vec4(1.0, gpt, gpt, 1);  // red
    else if ( rowEven && !colEven) bayer_color = bayer_color * vec4(0.5, 1.0, 0.5, 1);  // green
    else if (!rowEven &&  colEven) bayer_color = bayer_color * vec4(0.5, 1.0, 0.5, 1);  // green
    else if (!rowEven && !colEven) bayer_color = bayer_color * vec4(0.5, gpt, 1.0, 1);  // blue

    // Blend bayer and demosaicked depending on mipmap level
    // At high zoom the user sees the pure raw DNG mosaic.
    // At lower zoom, the user sees the demosaicked RGB interpretation.
    float lod = textureQueryLod(bayer_tile, p_ttc).y;
    float demosaic_bias = clamp(lod + 6, 0.0, 4.0);  // Blended color between lod 0->1
    color = mix(bayer_color, demosaic_color, demosaic_bias * 0.25);

    // TODO: uniforms for black level etc
    // These are hard coded from this one image
    const float max_value = 65535.0;
    const vec3 black_level = vec3(528.0 / max_value);
    const vec3 white_level = vec3(4095.0 / max_value);
    const vec3 as_shot_neutral = vec3(450619520.0/1073741824.0, 1073741824.0/1073741824.0, 669515392.0/1073741824.0);
    const mat3 color_matrix1 = mat3(
            1317655680.0/1073741824.0, -585703104.0/1073741824.0, -280555424.0/1073741824.0,
            -488214944.0/1073741824.0, 1629703168.0/1073741824.0, -45795556.0/1073741824.0,
            -43956872.0/1073741824.0, 175679488.0/1073741824.0, 634952512.0/1073741824.0);

    color.rgb = (color.rgb - black_level) / (white_level - black_level);
    color.rgb /= as_shot_neutral;  // apply white balance
    color.rgb *= color_matrix1;  // convert to XYZ  TODO: correct order?
    // TODO: the rest of the pipeline is hard.
    // color.rgb = forward_matrix * color.rgb;

    // Apply brightness
    color.rgb *= pow(2.0, brightness);

    color = srgb_from_linear(color);

    // OK to do texel boundary and selection box composition in sRGB space...
    color = texel_boundaries(color, p_ttc * textureSize(bayer_tile, 0));
    color = selection_box(p_omp, color, background_color, sel_rect_omp, omp_scale_qwn);
}

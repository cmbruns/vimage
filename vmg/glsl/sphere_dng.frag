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
uniform vec4 uv_bounds = vec4(0, 0, 1, 1);  // (u_min, v_min, u_max, v_max)

// Dual fisheye only
uniform float df_fov_radians = radians(195.0);
uniform float df_lens_rot_radians = 0.0;
uniform int render_pass = 1;

// DNG only
const int format_max = 65535;
uniform vec3 black_level = vec3(0);
uniform float white_level = 1.0;

in vec2 p_nic;
out vec4 color;

bool check_bounds(vec2 p_tct) {
    return p_tct.x < uv_bounds[0]
        || p_tct.y < uv_bounds[1]
        || p_tct.x > uv_bounds[2]
        || p_tct.y > uv_bounds[3];
}

vec4 color_sphere(vec3 p) {
    return vec4(0.5 * (p + vec3(1)), 1);
}


//--------------------------------------------------------------
// 1. Map DNG illuminant tags → nominal Kelvin temperatures
//--------------------------------------------------------------
float tempFromIlluminant(int illum) {
    if (illum == 1 || illum == 17) return 2856.0; // Std A
    if (illum == 18) return 4874.0;               // Std B
    if (illum == 19) return 6774.0;               // Std C
    if (illum == 20) return 5003.0;               // D50
    if (illum == 21) return 6504.0;               // D65
    if (illum == 22) return 7504.0;               // D75
    if (illum == 23) return 5455.0;               // D55
    return 6504.0; // fallback
}

float calculate_dng_t(
    vec3 asShotNeutral,
    mat3 colorMatrix1,
    mat3 colorMatrix2,
    int illuminant1,
    int illuminant2)
{

    float temp1 = tempFromIlluminant(illuminant1);
    float temp2 = tempFromIlluminant(illuminant2);

    //--------------------------------------------------------------
    // 2. Build base Camera→XYZ matrix from average of CM1 & CM2
    //--------------------------------------------------------------
    mat3 cmBase = (colorMatrix1 + colorMatrix2) * 0.5;

    mat3 camToXYZ = inverse(cmBase);

    //--------------------------------------------------------------
    // 3. Convert AsShotNeutral → white balance gains → XYZ
    //--------------------------------------------------------------
    vec3 wb = 1.0 / asShotNeutral;
    vec3 xyz = camToXYZ * wb;

    float xyzSum = xyz.x + xyz.y + xyz.z;
    if (xyzSum <= 0.0) {
        return 0.5; // fail-safe midpoint
    }

    //--------------------------------------------------------------
    // 4. Convert XYZ → xy → uv → McCamy CCT
    //--------------------------------------------------------------
    float x = xyz.x / xyzSum;
    float y = xyz.y / xyzSum;

    float denom = (-2.0 * x + 12.0 * y + 3.0);
    float u = (4.0 * x) / denom;
    float v = (6.0 * y) / denom;

    float n = (u - 0.3320) / (v - 0.1858);

    float cct = -449.0 * n*n*n + 3525.0 * n*n - 6823.3 * n + 5524.07;

    cct = clamp(cct, 2000.0, 12000.0);

    //--------------------------------------------------------------
    // 5. Convert to mireds and compute interpolation t
    //--------------------------------------------------------------
    float miredShot = 1.0 / cct;
    float mired1 = 1.0 / temp1;
    float mired2 = 1.0 / temp2;

    if (abs(mired1 - mired2) < 1e-9) {
        return 0.0;
    }

    float t = (miredShot - mired1) / (mired2 - mired1);

    return clamp(t, 0.0, 1.0);
}

// Hardcoded Color Space Conversion Constants
const mat3 bradfordD50toD65 = mat3(
    0.9555766, -0.0282895,  0.0122982,
   -0.0230393,  1.0099416, -0.0204830,
    0.0631636,  0.0210077,  1.3299098
);

const mat3 xyzToSRGB = mat3(
     3.2404542, -0.9692660,  0.0556434,
    -1.5371385,  1.8760108, -0.2040259,
    -0.4985314,  0.0415560,  1.0572252
);

mat3 linear_srgb_from_sensor(
        vec3 asShotNeutral,
        mat3 colorMatrixInterpolated)
{
    mat3 wbGainMatrix = mat3(
        1.0 / asShotNeutral.r, 0.0, 0.0,
        0.0, 1.0 / asShotNeutral.g, 0.0,
        0.0, 0.0, 1.0 / asShotNeutral.b);

    mat3 sensorToXYZ = inverse(colorMatrixInterpolated) * wbGainMatrix;
    return xyzToSRGB * bradfordD50toD65 * sensorToXYZ;
}

void main()
{
    // Convert normalized image screen coordinates (nic) to
    // viewer-space 3D direction (obq)
    vec3 p_obq = obq_for_nic(p_nic, display_projection);
    if (p_obq == INVALID_OBQ) discard;

    // Convert direction to sky-up physical camera world frame (ont),
    // then to physical camera frame 3D direction (raw)
    vec3 p_raw = raw_rot_ont * ont_rot_obq * p_obq;

    // Look up tile texture coordinate(s)
    vec2 p_tcr;  // Full image texture coordinate
    // Always dual fisheye with DNG as far as we know
    TexCoordPair pair = dual_fisheye_tex_coord(
            p_raw,
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
    float lod = textureQueryLod(demosaic_tile, p_tcr).y;
    float demosaic_bias = clamp(lod + 9, 0.0, 4.0) * 0.25;  // Blended color between lod 0->1

    const bool debug = false;
    if (debug) {
        // Visualize lods
        color = vec4(0, demosaic_bias, 0, 1);
        return;
        // demosaic_bias = 1.0;  // pure demosaic
    }

    color = mix(bayer_color, demosaic_color, demosaic_bias);
    color.a = alpha;

    // TODO: black level, white level, white balance, color_matrix,

    // black level
    color.rgb = max(color.rgb - black_level, vec3(0));

    // white level
    color.rgb /= vec3(white_level);

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

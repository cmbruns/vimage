#version 410

// Set line numbers correctly for this file
#line 5 0

const float PI = 3.1415926535897932384626433832795;

// Keep these values in sync with PixelFilter enum in image_widget_gl.py
const int FILTER_NEAREST = 1;
const int FILTER_CATROM = 2;

// Keep these constants in sync with display_projection.py
const int GNOMONIC_DISPLAY_PROJECTION = 0;
const int STEREOGRAPHIC_DISPLAY_PROJECTION = 1;
const int AZ_EQ_DISPLAY_PROJECTION = 2;
const int EQUIRECT_DISPLAY_PROJECTION = 3;

// Keep these in sync with image_data.py
const int EQUIRECT_INPUT_FORMAT = 0;
const int DUAL_FISHEYE_INPUT_FORMAT = 1;
const int PERSPECTIVE_INPUT_FORMAT = 2;

// Colorize raw grayscale bayer mosaic texel intensity
vec4 bayer_tint(
        ivec2 texel_rtc,  // must be full image texel index, because parity
        vec4 bayer_color  // raw grayscale bayer mosaic intensity
) {
    bool rowEven = (texel_rtc.y & 1) == 0;
    bool colEven = (texel_rtc.x & 1) == 0;
    // RGGB Bayer pattern
    vec4 mask = vec4(1);

    if      ( rowEven &&  colEven) mask = vec4(1.0, 0.5, 0.4, 1);  // red
    else if ( rowEven && !colEven) mask = vec4(0.4, 1.0, 0.4, 1);  // green
    else if (!rowEven &&  colEven) mask = vec4(0.4, 1.0, 0.4, 1);  // green
    else /* if (!rowEven && !colEven) */ mask = vec4(0.4, 0.5, 1.0, 1);  // blue
    return bayer_color * mask;
}

vec4 equirect_color(sampler2D image, vec2 tex_coord)
{
    // Use explicit gradients, to preserve anisotropic filtering during mipmap lookup
    vec2 dpdx = dFdx(tex_coord);
    vec2 dpdy = dFdy(tex_coord);

    if (dpdx.x > 0.5) dpdx.x -= 1; // use "repeat" wrapping on gradient
    if (dpdx.x < -0.5) dpdx.x += 1;
    if (dpdy.x > 0.5) dpdy.x -= 1; // use "repeat" wrapping on gradient
    if (dpdy.x < -0.5) dpdy.x += 1;

    return textureGrad(image, tex_coord, dpdx, dpdy);
}

vec4 catrom_weights(float t) {
    return 0.5 * vec4(
        -1*t*t*t + 2*t*t - 1*t,  // P0 weight
        3*t*t*t - 5*t*t + 2,  // P1 weight
        -3*t*t*t + 4*t*t + 1*t,  // P2 weight
        1*t*t*t - 1*t*t);  // P3 weight
}

vec4 catrom(sampler2D image, vec2 textureCoordinate, bool wrap) {
    vec2 texel = textureCoordinate * textureSize(image, 0) - vec2(0.5);
    ivec2 texel1 = ivec2(floor(texel));
    vec2 param = texel - texel1;
    vec4 weightsX = catrom_weights(param.x);
    vec4 weightsY = catrom_weights(param.y);
    vec4 combined = vec4(0);
    float rgb_weight = 0;  // for pseudo pre/post multiply alpha
    for (int y = 0; y < 4; ++y) {
        float wy = weightsY[y];
        for (int x = 0; x < 4; ++x) {
            float wx = weightsX[x];
            vec2 texel2 = vec2(x , y) + texel1 - vec2(0.5);
            vec2 tc = texel2 / textureSize(image, 0);
            vec4 rgba;
            if (wrap)
                rgba = equirect_color(image, tc);
            else
                rgba = texture(image, tc);
            rgb_weight += wx * wy * rgba.a;
            combined += wx * wy * vec4(rgba.rgb * rgba.a, rgba.a);  // premultiply alpha
        }
    }
    if (rgb_weight > 0)
        combined.rgb /= rgb_weight;  // un-premultiply alpha
    return combined;
}

vec2 equirect_tex_coord(vec3 dir)
{
    float longitude = 0.5 * atan(dir.x, -dir.z) / PI + 0.5; // range [0-1]
    float r = length(dir.xz);
    float latitude = -atan(dir.y, r) / PI + 0.5; // range [0-1]
    vec2 tex_coord = vec2(longitude, latitude);
    return tex_coord;
}

struct TexCoordPair {
    vec2 front_tc;
    vec2 rear_tc;
    float front_bias;  // range 0-1
};

TexCoordPair dual_fisheye_tex_coord(vec3 p_sph, float fov_radians, float lens_rot_radians)
{
    // input vector space is 3D unit sphere, x-right, y-up, z-back (i.e. -Z forward/center)
    // range [-1, +1]
    vec3 p_sph_front = p_sph;
    vec3 p_sph_rear = p_sph * vec3(-1, 1, -1);  // rotate 180 about Y/up

    // The two lenses can be slightly misaligned by an axial rotation
    float crot = cos(lens_rot_radians/2.0);
    float srot = sin(lens_rot_radians/2.0);
    mat2 rot_nfish = mat2(  // half rotation adjustment in the left/front fisheye
        crot, srot,
        -srot, crot);

    // Texture coordinates of each fisheye image center
    vec2 center_front_tc = vec2(0.25, 0.5);  // left/front fisheye center in output texture coordinates
    vec2 center_rear_tc = vec2(0.75, 0.5);  // rear camera occupies right half of image

    // Amount the two lenses overlap determines the blending region
    float z_limit = 0.4 * sin(fov_radians - radians(180));  // angular overlap region in z direction
    float front_bias = smoothstep(+z_limit, -z_limit, p_sph_front.z);

    // normalized fisheye space 2D x-right, y-up, range [-1, +1]
    float radius_nfish_front = acos(-p_sph_front.z) / fov_radians;  // TODO: nonlinear calibration
    float radius_nfish_rear = acos(-p_sph_rear.z) / fov_radians;  // TODO: nonlinear calibration
    vec2 p_nfish_front = (normalize(p_sph_front.xy) * radius_nfish_front) * rot_nfish;
    vec2 p_nfish_rear = (normalize(p_sph_rear.xy) * radius_nfish_rear) * rot_nfish;

    // output gl texture coordinates 2D x-right, y-down, range[0, 1]
    vec2 p_front_tc = center_front_tc + p_nfish_front * vec2(0.5, -1);  // Translate and scale
    vec2 p_rear_tc = center_rear_tc + p_nfish_rear * vec2(0.5, -1);

    if (p_front_tc.x >= 0.5) front_bias = 0.0;
    if (p_front_tc.x <= 0.0) front_bias = 0.0;
    if (p_front_tc.y >= 1.0) front_bias = 0.0;
    if (p_front_tc.y <= 0.0) front_bias = 0.0;
    if (p_rear_tc.x <= 0.5) front_bias = 1.0;
    if (p_rear_tc.x >= 1.0) front_bias = 1.0;
    if (p_rear_tc.y >= 1.0) front_bias = 1.0;
    if (p_rear_tc.y <= 0.0) front_bias = 1.0;

    return TexCoordPair(p_front_tc, p_rear_tc, front_bias);
}

vec4 nearest_nowrap(sampler2D image, vec2 tc) {
    return texture(image, tc);
}

vec4 nearest_wrap(sampler2D image, vec2 tc) {
    return equirect_color(image, tc);
}

vec4 show_boundaries(vec4 baseColor, vec2 texelCoord,
        float edgeThickness,
        vec3 color1, vec3 color2
) {
    // Derivatives: texture-space delta per screen pixel
    vec2 dx = dFdx(texelCoord);
    vec2 dy = dFdy(texelCoord);

    // Size of one screen pixel in texture space
    float texelsPerPixel = min(length(dx), length(dy));
    // Screen pixels per texture pixel
    float pixelsPerTexel = 1.0 / texelsPerPixel;

    // Fade-in factor: 0 at 10px/texel, 1 at 20px/texel
    float fade = smoothstep(12.0, 100.0, pixelsPerTexel);
    // If fully faded out, skip work
    if (fade <= 0.0) return baseColor;

    // Compute fractional position inside a texel
    float fx = fract(texelCoord.x);
    float fy = fract(texelCoord.y);
    float distX = min(fx, 1.0 - fx) * pixelsPerTexel;
    float distY = min(fy, 1.0 - fy) * pixelsPerTexel;
    // Boundary thickness in texture space
    // const float edgeThickness = 0.7;

    bool isEdge = (distX < edgeThickness) || (distY < edgeThickness);
    if (!isEdge) return baseColor;

    // Black/white double line pattern
    float stripe = step(0.5, fract((texelCoord.x + texelCoord.y) * 4.0));
    vec4 edgeColor = vec4(mix(color1, color2, stripe), 1);

    // Final opacity: fade * something
    return mix(baseColor, edgeColor, fade * 0.4);
}

vec4 texel_boundaries(vec4 baseColor, vec2 texelCoord) {
    return show_boundaries(baseColor, texelCoord,
            1.2,  // edge thickness
            vec3(0, 0, 0.3), vec3(1, 1, 0.7)  // color1, color2
    );
}

vec4 clip_n_filter(sampler2D image, vec2 tc, int pixelFilter, bool wrap)
{
    // clip to image boundary
    if (tc.x < 0 || tc.y < 0 || tc.x > 1 || tc.y > 1) {
        return vec4(0);
    }

    float mipmapLevel = textureQueryLod(image, tc).x;
    if (mipmapLevel > 0 || pixelFilter == FILTER_NEAREST)
    {
        if (wrap)
            return equirect_color(image, tc);
        else
            return texture(image, tc);
    }
    else {
        return catrom(image, tc, wrap);
    }
}

float linear_from_srgb(in float srgb)
{
    if (srgb <= 0.04045)
        return srgb / 12.92;
    else
        return pow((srgb + 0.055) / 1.055, 2.4);
}

vec4 linear_from_srgb(in vec4 srgb)
{
    return vec4(
        linear_from_srgb(srgb.r),
        linear_from_srgb(srgb.g),
        linear_from_srgb(srgb.b),
        srgb.a);
}

const vec3 INVALID_OBQ = vec3(0);

float srgb_from_linear(in float linear)
{
    if (linear <= 0.0031308)
        return linear * 12.92;
    else
        return pow(linear, 1.0/2.4) * 1.055 - 0.055;
}

// computes tile texture coordinate for a full image texture coordinate
vec2 tct_for_tcr(mat3 tile_X_img, vec2 tcr)
{
    tcr = tcr - floor(tcr); // Shift to range 0-1
    return (tile_X_img * vec3(tcr, 1)).xy;
}

vec4 srgb_from_linear(in vec4 linear)
{
    return vec4(
        srgb_from_linear(linear.r),
        srgb_from_linear(linear.g),
        srgb_from_linear(linear.b),
        linear.a);
}

vec3 equirect_xyz(vec2 xy) {
    float lat = xy.y;
    float lon = xy.x;
    float clat = cos(lat);
    return vec3(clat * sin(lon), sin(lat), -clat * cos(lon));
}

vec3 gnomonic_xyz(vec2 xy) {  // pinhole camera
    float d = sqrt(dot(xy, xy) + 1);
    return vec3(xy.x, xy.y, -1) / d;
}

vec3 stereographic_xyz(vec2 xy) {  // conformal
    float d = dot(xy, xy) + 4;
    return vec3(4 * xy.x, 4 * xy.y, dot(xy, xy) - 4) / d;
}

vec3 azimuthal_equidistant_xyz(vec2 xy) {  // finite distance to edges
    float d = sqrt(dot(xy, xy));
    float sdd = sin(d) / d;
    float cd = cos(d);
    return vec3(xy.x * sdd, xy.y * sdd, -cd);
}

bool azeqd_valid(vec2 xy) {
    return dot(xy, xy) < PI * PI;
}

bool equirect_valid(vec2 xy) {
    if (abs(xy.y) > PI / 2)
        return false;
    return true;
}

// Convert normalized image screen coordinates (nic) to
// app-view-modified world 3D coordinates (obq).
// If the point is invalid, (0,0,0) is returned
vec3 obq_for_nic(vec2 nic, int display_projection)
{
    switch(display_projection) {
        case STEREOGRAPHIC_DISPLAY_PROJECTION:
            return stereographic_xyz(nic);
        case AZ_EQ_DISPLAY_PROJECTION:
            if (! azeqd_valid(nic))
                return INVALID_OBQ;
            return azimuthal_equidistant_xyz(nic);
        case GNOMONIC_DISPLAY_PROJECTION:
            return gnomonic_xyz(nic);
        case EQUIRECT_DISPLAY_PROJECTION:
        default :
            if (! equirect_valid(nic))
                return INVALID_OBQ;
            return equirect_xyz(nic);
    }
    return INVALID_OBQ;
}

// modify image color to show selection box
vec4 selection_box(
    in vec2 p_omp,
    in vec4 image_color,
    in vec4 background_color,
    in ivec4 sel_rect_omp,
    in float omp_scale_qwn)
{
    if (sel_rect_omp.x == 0 && sel_rect_omp.z == 0)
        return image_color;  // uninitialized box, don't draw anything
    else {
        const float line_width_qwn = 1.8;// box outline line width in window pixels
        float hlw = 0.5 * omp_scale_qwn * line_width_qwn;// half line width, in image pixels
        // Is this pixel on the box outline?
        if (p_omp.x >= sel_rect_omp.x - hlw  // left clip
            && p_omp.x <= sel_rect_omp.z + hlw  // right clip
            && p_omp.y >= sel_rect_omp.y - hlw  // top clip
            && p_omp.y <= sel_rect_omp.w + hlw  // bottom clip
            && (abs(p_omp.x - sel_rect_omp.x) <= hlw  // on left edge
                || abs(p_omp.x - sel_rect_omp.z) <= hlw  // on right edge
                || abs(p_omp.y - sel_rect_omp.y) <= hlw  // on top edge
                || abs(p_omp.y - sel_rect_omp.w) <= hlw  // on bottom edge
        )) {
            // invert color, similar to irfanview
            vec4 base_color = mix(background_color, image_color, image_color.a);
            vec3 box_color = vec3(1) - base_color.rgb;
            // but inverted can be invisible on gray backgrounds
            if (length(box_color.rgb - image_color.rgb) < 0.5) {
                if (length(base_color.rgb) > 0.5)
                box_color = vec3(0);// black box for light gray image
                else
                box_color = vec3(1);// white box for dark gray image
            }
            return vec4(box_color, 1);
        }
        else
            return image_color;
    }
}

// Prepare to set line numbers correctly for the next file
#line 1 1

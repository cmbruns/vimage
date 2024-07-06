#version 410

// Set line numbers correctly for this file
#line 5 0

const float PI = 3.1415926535897932384626433832795;

// Keep these values in sync with PixelFilter enum in image_widget_gl.py
const int FILTER_NEAREST = 1;
const int FILTER_CATROM = 2;

// Keep these constants in sync with projection_360.py
const int GNOMONIC_PROJECTION = 0;
const int STEREOGRAPHIC_PROJECTION = 1;
const int AZ_EQ_PROJECTION = 2;
const int EQUIRECT_PROJECTION = 3;

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

vec4 nearest_nowrap(sampler2D image, vec2 tc) {
    return texture(image, tc);
}

vec4 nearest_wrap(sampler2D image, vec2 tc) {
    return equirect_color(image, tc);
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
           return nearest_wrap(image, tc);
        else
            return nearest_nowrap(image, tc);
    }
    else {
        return catrom(image, tc, wrap);
    }
}

float srgb_from_linear(in float linear)
{
    if (linear <= 0.0031308)
        return linear * 12.92;
    else
        return pow(linear, 1.0/2.4) * 1.055 - 0.055;
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

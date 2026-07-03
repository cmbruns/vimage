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

vec2 gear360_2016_tex_coord(vec3 p_sph, float fov_radians, float lens_rot_radians)
{
    // input vector space is 3D unit sphere, x-right, y-up, z-back (i.e. -Z forward/center)
    // range [-1, +1]

    // const float FOV = radians(195.0);  // field of view of Gear360 fisheye
    // My camera has a slight relative rotation of the lenses
    // const float lens_rot = radians(-1.5);  // relative rotation correction of the lenses

    float crot = cos(lens_rot_radians/2.0);
    float srot = sin(lens_rot_radians/2.0);
    mat2 rot_nfish = mat2(  // half rotation adjustment in the left/front fisheye
        crot, srot,
        -srot, crot);
    vec2 center_tex = vec2(0.25, 0.5);  // left/front fisheye center in output texture coordinates
    // Is this fragment drawn from the right/back fisheye image?
    if (p_sph.z > 0) {  // right fisheye image is behind the camera
        // right fisheye view is rotated 180 degrees about Y w.r.t left fisheye
        p_sph = vec3(-p_sph.x, p_sph.y, -p_sph.z);  // Is there a glsl swizzle shortcut for this?
        center_tex = vec2(0.75, 0.5);  // right fisheye is to the right in the image pair
    }

    // normalized fisheye space 2D x-right, y-up, range [-1, +1]
    float radius_nfish = acos(-p_sph.z) / fov_radians;  // TODO: nonlinear calibration
    vec2 p_nfish = normalize(p_sph.xy) * radius_nfish * rot_nfish;

    // output gl texture coordinates 2D x-right, y-down, range[0, 1]
    vec2 p_tex = center_tex + p_nfish * vec2(0.5, -1);  // Translate and scale
    return p_tex;
}

vec4 nearest_nowrap(sampler2D image, vec2 tc) {
    return texture(image, tc);
}

vec4 nearest_wrap(sampler2D image, vec2 tc) {
    return equirect_color(image, tc);
}

vec4 texel_boundaries(vec4 baseColor, vec2 texelCoord)
{
    // Derivatives: texture-space delta per screen pixel
    vec2 dx = dFdx(texelCoord);
    vec2 dy = dFdy(texelCoord);

    // Size of one screen pixel in texture space
    float texelsPerPixel = min(length(dx), length(dy));
    // Screen pixels per texture pixel
    float pixelsPerTexel = 1.0 / texelsPerPixel;
    // Fade-in factor: 0 at 10px/texel, 1 at 20px/texel
    float fade = smoothstep(15.0, 100.0, pixelsPerTexel);
    // If fully faded out, skip work
    if (fade <= 0.0) return baseColor;

    // Compute fractional position inside a texel
    float fx = fract(texelCoord.x);
    float fy = fract(texelCoord.y);
    float distX = min(fx, 1.0 - fx) * pixelsPerTexel;
    float distY = min(fy, 1.0 - fy) * pixelsPerTexel;
    // Boundary thickness in texture space
    const float edgeThickness = 0.7;

    bool isEdge = (distX < edgeThickness) || (distY < edgeThickness);
    if (!isEdge) return baseColor;

    // Black/white double line pattern
    float stripe = step(0.5, fract((texelCoord.x + texelCoord.y) * 4.0));
    vec4 edgeColor = vec4(mix(vec3(0, 0, 0.4), vec3(1, 1, 0.6), stripe), 1);

    // Final opacity: fade * 0.5
    return mix(baseColor, edgeColor, fade * 0.2);
    // return vec4(1, 0, 1, 1);  // magenta for testing
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

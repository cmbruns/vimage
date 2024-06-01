#version 410

// Keep these values in sync with PixelFilter enum in image_widget_gl.py
const int NEAREST = 1;
const int CATMULL_ROM = 2;

const float PI = 3.1415926535897932384626433832795;

// Keep these constants in sync with projection_360.py
const int STEREOGRAPHIC_PROJECTION = 1;
const int AZ_EQ_PROJECTION = 2;
const int GNOMONIC_PROJECTION = 3;
const int EQUIRECT_PROJECTION = 4;
uniform int projection = STEREOGRAPHIC_PROJECTION;

uniform sampler2D image;
uniform int pixelFilter = NEAREST;
uniform mat3 rotation = mat3(1);

in vec3 tex_coord;
out vec4 color;

vec2 equirect_tex_coord(vec3 dir)
{
    float longitude = 0.5 * atan(dir.x, -dir.z) / PI + 0.5; // range [0-1]
    float r = length(dir.xz);
    float latitude = -atan(dir.y, r) / PI + 0.5; // range [0-1]
    vec2 tex_coord = vec2(longitude, latitude);
    return tex_coord;
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

vec4 nearest(sampler2D image, vec2 tex_coord) {
    return equirect_color(image, tex_coord);
}

vec4 catrom_weights(float t) {
    return 0.5 * vec4(
        -1*t*t*t + 2*t*t - 1*t,  // P0 weight
        3*t*t*t - 5*t*t + 2,  // P1 weight
        -3*t*t*t + 4*t*t + 1*t,  // P2 weight
        1*t*t*t - 1*t*t);  // P3 weight
}

vec4 catrom(sampler2D image, vec2 textureCoordinate) {
    vec2 texel = textureCoordinate * textureSize(image, 0) - vec2(0.5);
    ivec2 texel1 = ivec2(floor(texel));
    vec2 param = texel - texel1;
    // return vec4(param, 0, 1);  // interpolation parameter
    vec4 weightsX = catrom_weights(param.x);
    vec4 weightsY = catrom_weights(param.y);
    // return vec4(-3 * weightsX[3], 0, 0, 1);  // point 1 x weight
    vec4 combined = vec4(0);
    for (int y = 0; y < 4; ++y) {
        float wy = weightsY[y];
        for (int x = 0; x < 4; ++x) {
            float wx = weightsX[x];
            vec2 texel2 = vec2(x , y) + texel1 - vec2(0.5);
            vec2 tc = texel2 / textureSize(image, 0);
            combined += wx * wy * equirect_color(image, tc);
        }
    }
    return combined;
}

vec3 original_xyz(vec2 xy) {
    // Original working implementation. What projection is this?
    float d = 1 * dot(xy, xy);
    return vec3(2 * xy.x, 2 * xy.y, d - 2) / d;
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
    if (abs(xy.x) > 2 * PI)
        return false;
    if (abs(xy.y) > PI)
        return false;
    return true;
}

void main() {
    vec3 xyz;
    if (projection == STEREOGRAPHIC_PROJECTION) {
        xyz = stereographic_xyz(tex_coord.xy);
    }
    else if (projection == AZ_EQ_PROJECTION) {
        if (! azeqd_valid(tex_coord.xy)) {
            color = vec4(1, 0, 0, 0);
            return;
        }
        xyz = azimuthal_equidistant_xyz(tex_coord.xy);
    }
    else if (projection == GNOMONIC_PROJECTION) {
        if (! equirect_valid(tex_coord.xy)) {
            color = vec4(1, 0, 0, 0);
            return;
        }
        xyz = gnomonic_xyz(tex_coord.xy);
    }
    else if (projection == EQUIRECT_PROJECTION) {
        xyz = equirect_xyz(tex_coord.xy);
    }
    else {
        xyz = original_xyz(tex_coord.xy);
    }

    xyz = xyz * rotation;

    vec2 tex_coord = equirect_tex_coord(xyz);

    switch(pixelFilter) {
    case NEAREST:
        color = nearest(image, tex_coord);
        break;
    case CATMULL_ROM:
        color = catrom(image, tex_coord);
        break;
    }

    color = sqrt(color);
}

#version 410

// Keep these values in sync with PixelFilter enum in image_widget_gl.py
const int NEAREST = 1;
const int CATMULL_ROM = 2;

uniform sampler2D image;
uniform int pixelFilter = NEAREST;
uniform mat3 rotation = mat3(1);

in vec3 tex_coord;
out vec4 color;

vec4 nearest(sampler2D image, vec2 textureCoordinate) {
    return texture(image, textureCoordinate);
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
            combined += wx * wy * texture(image, tc);
        }
    }
    return combined;
}

vec4 equirect_color(vec3 dir, sampler2D image)
{
    const float PI = 3.1415926535897932384626433832795;
    float longitude = 0.5 * atan(dir.x, -dir.z) / PI + 0.5; // range [0-1]
    float r = length(dir.xz);
    float latitude = -atan(dir.y, r) / PI + 0.5; // range [0-1]
    vec2 tex_coord = vec2(longitude, latitude);

    // Use explicit gradients, to preserve anisotropic filtering during mipmap lookup
    vec2 dpdx = dFdx(tex_coord);
    vec2 dpdy = dFdy(tex_coord);
    if (true) {
        if (dpdx.x > 0.5) dpdx.x -= 1; // use "repeat" wrapping on gradient
        if (dpdx.x < -0.5) dpdx.x += 1;
        if (dpdy.x > 0.5) dpdy.x -= 1; // use "repeat" wrapping on gradient
        if (dpdy.x < -0.5) dpdy.x += 1;
    }

    return textureGrad(image, tex_coord, dpdx, dpdy);
}

void main() {
    vec2 xy = tex_coord.xy;
    float denom = 1 * dot(xy, xy);
    vec3 xyz = vec3(2 * xy.x, 2 * xy.y, denom - 2) / denom;
    xyz = xyz * rotation;
    // TODO: rotate

    color = equirect_color(xyz, image);

    // color = vec4(tex_coord.xy, 0.8, 1);
}

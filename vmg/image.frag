#version 410

// Keep these values in sync with PixelFilter enum in image_widget_gl.py
const int NEAREST = 1;
const int BILINEAR = 2;
const int HERMITE = 3;
const int CATMULL_ROM = 4;

uniform sampler2D image;
uniform int pixelFilter = NEAREST;
in vec3 tex_coord;
out vec4 color;

vec4 bilinear(sampler2D image, vec2 textureCoordinate) {
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
    // TODO:
    return combined;
}

void main() {
    vec2 tc = tex_coord.xy / tex_coord.z;

    if (tc.x < 0 || tc.y < 0 || tc.x > 1 || tc.y > 1) {
        color = vec4(0);
        return;
    }

    switch(pixelFilter) {
    case NEAREST:
    case BILINEAR:
        color = bilinear(image, tc);
        break;
    case HERMITE:  // not implemented...
    case CATMULL_ROM:
        color = catrom(image, tc);
        break;
    }

    color = sqrt(color);  // linear -> srgb
}

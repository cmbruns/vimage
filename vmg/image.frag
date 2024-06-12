#version 410

// Keep these values in sync with PixelFilter enum in image_widget_gl.py
const int NEAREST = 1;
const int CATMULL_ROM = 2;

uniform sampler2D image;
uniform int pixelFilter = NEAREST;
uniform ivec4 selrect_omp = ivec4(100, 150, 200, 300);  // left top bottom right

in vec2 p_tex;
in vec2 p_omp;
in float omp_scale_qwn;

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

void main()
{
    if (p_tex.x < 0 || p_tex.y < 0 || p_tex.x > 1 || p_tex.y > 1) {
        color = vec4(0);
        return;
    }

    switch(pixelFilter) {
    case NEAREST:
        color = nearest(image, p_tex);
        break;
    case CATMULL_ROM:
        color = catrom(image, p_tex);
        break;
    }

    vec4 image_color = sqrt(color);  // linear -> srgb

    // selection box
    float line_width_qwn = 1.8;  // box outline line width in window pixels
    float hlw = 0.5 * omp_scale_qwn * line_width_qwn;  // half line width, in image pixels
    // Is this pixel on the box outline?
    if (p_omp.x >= selrect_omp.x - hlw &&  // left clip
        p_omp.x <= selrect_omp.z + 1 + hlw &&  // right clip
        p_omp.y >= selrect_omp.y - hlw &&  // top clip
        p_omp.y <= selrect_omp.w + 1 + hlw && (  // bottom clip
          abs(p_omp.x - selrect_omp.x) <= hlw ||  // on left edge
          abs(p_omp.x - selrect_omp.z - 1) <= hlw ||  // on right edge
          abs(p_omp.y - selrect_omp.y) <= hlw ||  // on top edge
          abs(p_omp.y - selrect_omp.w - 1) <= hlw)  // on bottom edge
    ) {
        // invert color, similar to irfanview
        vec4 box_color = vec4(1, 1, 1, 2) - image_color;
        // but inverted can be invisible on gray backgrounds
        if (length(box_color.xyz - image_color.xyz) < 0.5) {
            if (length(image_color.xyz) > 0.5)
                box_color = vec4(0, 0, 0, 1);  // black box for light gray image
            else
                box_color = vec4(1, 1, 1, 1);  // white box for dark gray image
        }
        color = vec4(1, 1, 1, 2) - image_color;
    }
    else {
        color = image_color;
    }
}

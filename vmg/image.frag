#version 410

uniform sampler2D image;
uniform bool bHermite = true;
in vec3 tex_coord;
out vec4 color;

vec4 bilinear(sampler2D image, vec2 textureCoordinate) {
    return texture(image, textureCoordinate);
}

float inverse_smoothstep( float x )
{
    return 0.5 - sin(asin(1.0-2.0*x)/3.0);
}

vec4 hermite(sampler2D image, vec2 textureCoordinate, float test) {
    vec2 tcf1 = fract(textureCoordinate * textureSize(image, 0) + vec2(test));
    vec2 tcf2 = smoothstep(vec2(0), vec2(1), tcf1);
    // vec2 tcf2 = vec2(inverse_smoothstep(tcf1.x), inverse_smoothstep(tcf1.y));
    // return vec4(tcf2, 0, 1);
    vec2 delta = (tcf2 - tcf1) / textureSize(image, 0);
    return texture(image, textureCoordinate + delta);
}

void main() {
    vec2 tc = tex_coord.xy / tex_coord.z;

    if (tc.x < 0 || tc.y < 0 || tc.x > 1 || tc.y > 1) {
        color = vec4(0);
        return;
    }

    if (bHermite)
        color = hermite(image, tc, 0.5);
    else
        color = bilinear(image, tc);

    color = sqrt(color);
}

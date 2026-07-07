#version 410

uniform sampler2D bayer;
in vec2 tex_coord;
out vec4 color;

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

float sinc(float x) {
    x *= 3.14159265358979323846;   // π
    return (abs(x) < 1e-5) ? 1.0 : sin(x) / x;
}

float lanczos(vec2 xa) {
    float x = abs(xa.x);
    float a = xa.y;
    if (x >= a) return 0.0;
    return sinc(x) * sinc(x / a);
}

void main()
{
    // Fractional texel
    vec2 texel = tex_coord * textureSize(bayer, 0);
    ivec2 iTexel = ivec2(round(texel));
    // Visit a 5x5 neighborhood
    vec3 rgb = vec3(0);
    vec3 weights = vec3(0);
    const int dt = 2;  // 1->3x3; 2->5x5; 3->7x7
    const float window = dt + 0.5;  // Keep neighborhood symmetric-ish, shortest distance not visited here
    const float rb_sampling_rate = 2.0;  // neighbor red/blue are 2 cells away
    const float g_sampling_rate = sqrt(2.0);  // neighbor greens are diagonal
    for (int x = iTexel.x - dt; x <= iTexel.x + dt; ++x)
    {
        float dx = x - texel.x;
        for (int y = iTexel.y - dt; y <= iTexel.y + dt; ++y)
        {
            float dy = y - texel.y;
            float dist = length(vec2(dx, dy));
            if (dist > window)
                continue;
            vec2 xa = vec2(dist, window);

            float w = 1.0;  // TODO: this is the fancy part...

            if ((y & 1) == 0 && (x & 1) == 0) {  // red
                w = lanczos(xa/rb_sampling_rate);  // scale by distance between samples
                rgb.r += w * texelFetch(bayer, ivec2(x, y), 0).r;
                weights.r += w;
            }
            else if ((y & 1) != 0 && (x & 1) != 0) {  // blue
                w = lanczos(xa/rb_sampling_rate);  // scale by distance between samples
                rgb.b += w * texelFetch(bayer, ivec2(x, y), 0).r;
                weights.b += w;
            }
            else {  // green
                w = lanczos(xa/g_sampling_rate);  // scale by distance between samples
                rgb.g += w * texelFetch(bayer, ivec2(x, y), 0).r;
                weights.g += w;
            }
        }
    }

    float brightness = 5;
    color = vec4(brightness * rgb / weights, 1);

    color = srgb_from_linear(color);
}

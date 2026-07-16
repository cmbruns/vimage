#version 410 core

uniform sampler2D tileTexture;
uniform sampler2D numeralTexture;

uniform int   channel_count;        // set from host
uniform float format_max;
uniform float data_max;
uniform bool  srgb_gamma;
uniform vec2  texture_pixels;       // pixels per texture (or use textureSize)
uniform float micrometers_per_pixel;
uniform mat2  rotation;             // set from host (identity if no rotation)

const float left_margin   = 0.1;
const float right_margin  = 0.9;
const float top_margin    = 0.9;
const float bottom_margin = 0.1;

in  vec2 vTexCoord;   // from vertex shader
out vec4 fragColor;

// Convert linear RGB component to sRGB gamma corrected color space
float sRGB_gamma_correct(float c)
{
    const float a = 0.055;
    return (c < 0.0031308) ? 12.92*c : (1.0+a)*pow(c, 1.0/2.4) - a;
}

void main()
{
    // pixel-relative texture coordinates
    vec2 local_coords = fract(texture_pixels * vTexCoord);

    // rotate numbers
    local_coords -= vec2(0.5);
    local_coords  = rotation * local_coords;
    local_coords += vec2(0.5);

    // Trim to sub-region
    if (local_coords.x <= left_margin ||
        local_coords.x >= right_margin ||
        local_coords.y >= top_margin   ||
        local_coords.y <= bottom_margin)
        discard;

    // How many digits to show?
    float num_digits = ceil(log(data_max) / log(10.0));

    // Width of a single digit, in image pixels
    float w = (right_margin - left_margin) / num_digits;
    float h = w * 1.7; // number aspect ratio

    // Maybe reduce scale to fit all channels in the box height
    float total_height = float(channel_count) * h;
    float scale = (top_margin - bottom_margin) / total_height;
    scale = clamp(scale, 0.1, 1.0);
    w *= scale;
    h *= scale;

    // center justify number horizontally
    float hoffset    = right_margin - 0.5 * (right_margin - left_margin - w * num_digits);
    float place0     = (hoffset - local_coords.x) / w;
    float tens_place = floor(place0);
    if (tens_place < 0.0 || tens_place >= num_digits)
        discard;
    float dx = 1.0 - fract(place0);

    // center channels vertically
    float voffset = top_margin - 0.5 * (top_margin - bottom_margin - h * float(channel_count));
    float chan0   = (voffset - local_coords.y) / h;
    float channel = floor(chan0);

    // invert channels: red at top, alpha at bottom
    channel = float(channel_count) - channel - 1.0;

    if (channel < 0.0 || channel >= float(channel_count))
        discard;

    float dy = 1.0 - fract(chan0);
    if (dy > 0.95 || dy < 0.05)
        discard;
    dy = (dy - 0.05) / 0.90; // rescale to 0-1

    int c = int(channel);
    // 2-channel images store second channel in alpha (channel 3)
    if (channel_count == 2 && c == 1)
        c = 3;

    float intensity = texture(tileTexture, vTexCoord)[c];
    if (srgb_gamma)
        intensity = sRGB_gamma_correct(intensity);

    intensity = floor(format_max * intensity + 0.5); // exact integer

    float p = pow(10.0, tens_place);
    if (tens_place > 0.0 && intensity < p)
        discard; // number does not have this many digits

    float digit = floor(10.0 * fract(intensity / (10.0 * p)));

    vec4 pixel = texture(numeralTexture, vec2(0.1 * (digit + dx), dy));

    // antialiasing
    float radius = 18.0 * micrometers_per_pixel;
    // float radius = 2500.0 * abs(dFdx(vTexCoord.x))/w; // optional, slower

    const float l0 = 0.50; // outer edge of white outline
    const float l1 = 0.53; // inner border between white outline and black middle

    if (pixel.r < (l0 - radius))
        discard; // way outside numeral

    float wb_ratio = smoothstep(l0 - radius, l1 + radius, pixel.r);
    vec3 color     = mix(vec3(1.0), vec3(0.0), wb_ratio);
    float alpha    = smoothstep(l0 - radius, l0 + radius, pixel.r);

    fragColor = vec4(color, alpha);
}

#pragma include "shared.frag"

const int NUMERALS_HEXADECIMAL = 1;
const int NUMERALS_DECIMAL = 2;
const int NUMERALS_NONE = 3;

uniform sampler2D tile;
uniform sampler2D numerals;

uniform int   channel_count = 3;  // set from host
uniform float format_max = 255;
uniform float data_max = 255;
uniform mat2 rotation = mat2(1);
uniform int pixel_numerals = NUMERALS_HEXADECIMAL;


const float left_margin   = 0.1;
const float right_margin  = 0.9;
const float top_margin    = 0.9;
const float bottom_margin = 0.1;

in  vec2 p_ttc;   // from vertex shader
out vec4 fragColor;

void main()
{
    if (pixel_numerals == NUMERALS_NONE) {
        discard;
        return;
    }

    float lod = textureQueryLod(tile, p_ttc).y;
    float fade = smoothstep(-5.0, -8.0, lod);  // smoothly blend in at high zoom
    if (fade <= 0) discard;

    // pixel-relative texture coordinates
    vec2 texture_pixels = textureSize(tile, 0);
    vec2 local_coords = fract(texture_pixels * p_ttc);

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
    float base = 16.0;  // prepare for hex display
    if (pixel_numerals == NUMERALS_DECIMAL) {
        base = 10.0;
    }
    float num_digits = ceil(log(format_max) / log(base));

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

    vec4 intensity_v = texture(tile, p_ttc);

    // Not needed because all vimage texture values are as-found.
    // if (srgb_gamma)
    //     intensity_v = sRGB_gamma_correct(intensity_v);

    intensity_v = floor(format_max * intensity_v + 0.5); // exact integer

    float intensity = intensity_v[c];

    bool zero_pad_left = pixel_numerals == NUMERALS_HEXADECIMAL;
    float p = pow(base, tens_place);
    if (tens_place > 0.0 && intensity < p && !zero_pad_left)
        discard; // number does not have this many digits

    float digit = floor(base * fract(intensity / (base * p)));

    // compensate for imperfections of this particular numeral texture
    // hex_digits_df.png (used for both hex and decimal display)
    const float fudge_scale = 0.998;  // Increase to move "9" or "F" to the left
    const float fudge_offset = 0.010;  // Increase to move "0" to the left
    const float stride = fudge_scale * 1.0 / 16.0;  // 16 characters in atlas, plus fudge factor
    const float tracking = 0.88;  // lower to push numerals closer together
    vec4 pixel = texture(numerals, vec2(fudge_offset + stride * (digit + tracking * dx), dy));

    // antialiasing
    // float radius = 18.0 * texels_per_pixel;
    float radius = 3000.0 * abs(dFdx(p_ttc.x))/w; // optional, slower

    const float l0 = 0.50; // outer edge of white outline
    const float l1 = 0.65; // inner border between white outline and black middle

    if (pixel.r < (l0 - radius))
        discard; // way outside numeral

    vec3 border_color = vec3(1.0);
    vec3 center_color = vec3(0.0);

    // tint the numerals per color channel
    if (channel_count > 1) {
        if (c == 0) {  // red
            border_color = vec3(1.0, 0.8, 0.8);
            center_color = vec3(0.3, 0.0, 0.0);
        }
        else if (c == 1) {  // green
            border_color = vec3(0.8, 1.0, 0.8);
            center_color = vec3(0.0, 0.2, 0.0);
        }
        else if (c == 2) {  // blue
            border_color = vec3(0.8, 0.8, 1.0);
            center_color = vec3(0.0, 0.0, 0.4);
        }
    }

    float wb_ratio = smoothstep(l0 - radius, l1 + radius, pixel.r);
    vec3 color     = mix(border_color, center_color, wb_ratio);
    float alpha    = smoothstep(l0 - radius, l0 + radius, pixel.r);

    fragColor = vec4(color, 0.75 * alpha * fade);
}

#pragma include "shared.frag"

uniform sampler2D tile;
uniform sampler2D numerals;

uniform int   channel_count = 3;  // set from host
uniform float format_max = 255;
uniform float data_max = 255;
uniform mat2 rotation = mat2(1);
uniform int pixel_numerals = NUMERALS_HEXADECIMAL;

in  vec2 p_ttc;   // from vertex shader
out vec4 fragColor;

void main()
{
    fragColor = numeral_color(
            p_ttc,
            tile,
            numerals,
            channel_count,
            format_max,
            data_max,
            rotation,
            pixel_numerals);
}

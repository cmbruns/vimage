#version 410 core

uniform sampler2D bayer;
in vec2 tex_coord;
out vec4 color;

// Malvar He Cutler Linear Image Demosaicking on 5x5 neighborhood
// 13 neighbor texel offsets that contribute to the demosaic
const ivec2 MHC_NBRS[13] = ivec2[13](
                                ivec2(0, -2),
                 ivec2(-1, -1), ivec2(0, -1), ivec2(1, -1),
  ivec2(-2, +0), ivec2(-1, +0), ivec2(0, +0), ivec2(1, +0), ivec2(2, +0),
                 ivec2(-1, +1), ivec2(0, +1), ivec2(1, +1),
                                ivec2(0, +2)  );
// Coefficients times 8.0
const float MHC_SCALE = 1.0 / 8.0;
// green at red, or green at blue
const float MHC_G_AT_R_OR_B[13] = float[13](
          -1,
        0, 2, 0,
    -1, 2, 4, 2, -1,
        0, 2, 0,
          -1  );
// red at blue, or blue at red
const float MHC_RB_AT_BR[13] = float[13](
           -1.5,
          2, 0, 2,
    -1.5, 0, 6, 0, -1.5,
          2, 0, 2,
           -1.5  );
// red at green in blue row, or blue at green in red row
const float MHC_RB_AT_G_IN_BR[13] = float[13](
           -1,
        -1, 4, -1,
    0.5, 0, 5, 0, 0.5,
        -1, 4, -1,
           -1  );
// red at green in red row, or blue at green in blue row
const float MHC_RB_AT_G_IN_RB[13] = float[13](
           0.5,
        -1, 0, -1,
     -1, 4, 5, 4, -1,
        -1, 0, -1,
           0.5  );
// red at red, or green at green, or blue at blue
const float MHC_RGB_AT_RGB[13] = float[13](
           0,
        0, 0, 0,
     0, 0, 8, 0, 0,
        0, 0, 0,
           0  );

const ivec2 LIN_NBRS[9] = ivec2[9](
        ivec2(-1, -1), ivec2(0, -1), ivec2(+1, -1),
        ivec2(-1, +0), ivec2(0, +0), ivec2(+1, +0),
        ivec2(-1, +1), ivec2(0, +1), ivec2(+1, +1)  );

const float LIN_RGB_AT_RGB[9] = float[9](
        0, 0, 0,
        0, 1, 0,
        0, 0, 0  );

const float LIN_G_AT_RB[9] = float[9](
        0, 0.25, 0,
        0.25, 0, 0.25,
        0, 0.25, 0);

const float LIN_RB_AT_BR[9] = float[9](
        0.25, 0, 0.25,
        0, 0, 0,
        0.25, 0, 0.25
);

const float LIN_RB_AT_G_IN_RB[9] = float[9](
          0, 0, 0,
        0.5, 0, 0.5,
          0, 0, 0
);

const float LIN_RB_AT_G_IN_BR[9] = float[9](
        0, 0.5, 0,
        0, 0.0, 0,
        0, 0.5, 0
);

// RGGB aware manual clamp to edge
// Find the closest in-bounds texel matching the parity of the logical texel
ivec2 rggb_clamp_to_edge(ivec2 xy)
{
    ivec2 max_tex = textureSize(bayer, 0) - ivec2(1);
    const ivec2 min_tex = ivec2(0);
    int x = xy.x;
    int y = xy.y;
    int cx = x >= 0 ? x : (-x) & 1;
    cx = cx <= max_tex.x ? cx : max_tex.x - ((cx + 1) & 1);
    int cy = y >= 0 ? y : (-y) & 1;
    cy = cy <= max_tex.y ? cy : max_tex.y - ((cy + 1) & 1);
    return ivec2(cx, cy);
}

// Malvar He Cutler Linear Image Demosaicking on 5x5 neighborhood
vec3 linear_color(vec2 texel)
{
    // fract(texel) should be near 0.5 if textures are aligned correctly
    ivec2 txl = ivec2(floor(texel));
    int x = txl.x;
    int y = txl.y;
    vec3 result = vec3(0);
    for (int t = 0; t < 9; ++t)
    {
        ivec2 tx = rggb_clamp_to_edge(txl + LIN_NBRS[t]);
        float intensity = texelFetch(bayer, tx, 0).r;
        if ((y & 1) == 0 && (x & 1) == 0) {  // red
            result.r += intensity * LIN_RGB_AT_RGB[t];
            result.g += intensity * LIN_G_AT_RB[t];
            result.b += intensity * LIN_RB_AT_BR[t];
        }
        else if ((y & 1) != 0 && (x & 1) != 0) {  // blue
            result.r += intensity * LIN_RB_AT_BR[t];
            result.g += intensity * LIN_G_AT_RB[t];
            result.b += intensity * LIN_RGB_AT_RGB[t];
        }
        else if ((y & 1) == 0 && (x & 1) != 0) {  // green in red row
            result.r += intensity * LIN_RB_AT_G_IN_RB[t];
            result.g += intensity * LIN_RGB_AT_RGB[t];
            result.b += intensity * LIN_RB_AT_G_IN_BR[t];
        }
        else if ((y & 1) != 0 && (x & 1) == 0) {  // green in blue row
            result.r += intensity * LIN_RB_AT_G_IN_BR[t];
            result.g += intensity * LIN_RGB_AT_RGB[t];
            result.b += intensity * LIN_RB_AT_G_IN_RB[t];
        }
        else {
            result = vec3(0, 1, 1);  // MAGENTA should not happen
        }
    }
    // debugging - fractional texel should be X.5
    // result.r = 10 * abs(fract(texel.y) - 0.5);  // should be zero
    return result;
}

vec3 mhc_color(vec2 texel)
{
    // fract(texel) should be near 0.5 if textures are aligned correctly
    ivec2 txl = ivec2(floor(texel));
    int x = txl.x;
    int y = txl.y;
    vec3 result = vec3(0);
    for (int t = 0; t < 13; ++t)
    {
        ivec2 tx = rggb_clamp_to_edge(txl + MHC_NBRS[t]);
        float intensity = MHC_SCALE * texelFetch(bayer, tx, 0).r;
        if ((y & 1) == 0 && (x & 1) == 0) {  // red
            result.r += intensity * MHC_RGB_AT_RGB[t];
            result.g += intensity * MHC_G_AT_R_OR_B[t];
            result.b += intensity * MHC_RB_AT_BR[t];
        }
        else if ((y & 1) != 0 && (x & 1) != 0) {  // blue
            result.r += intensity * MHC_RB_AT_BR[t];
            result.g += intensity * MHC_G_AT_R_OR_B[t];
            result.b += intensity * MHC_RGB_AT_RGB[t];
        }
        else if ((y & 1) == 0 && (x & 1) != 0) {  // green in red row
            result.r += intensity * MHC_RB_AT_G_IN_RB[t];
            result.g += intensity * MHC_RGB_AT_RGB[t];
            result.b += intensity * MHC_RB_AT_G_IN_BR[t];
        }
        else if ((y & 1) != 0 && (x & 1) == 0) {  // green in blue row
            result.r += intensity * MHC_RB_AT_G_IN_BR[t];
            result.g += intensity * MHC_RGB_AT_RGB[t];
            result.b += intensity * MHC_RB_AT_G_IN_RB[t];
        }
        else {
            result = vec3(0, 1, 1);  // MAGENTA should not happen
        }
    }
    // debugging - fractional texel should be X.5
    // result.r = 10 * abs(fract(texel.y) - 0.5);  // should be zero
    return result;
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

float sinc(float x) {
    x *= 3.14159265358979323846;   // π
    return (abs(x) < 1e-5) ? 1.0 : sin(x) / x;
}

float lanczos(vec2 xa) {
    float x = abs(xa.x);  // distance
    float a = xa.y;  // window
    if (x >= a) return 0.0;
    return sinc(x) * sinc(x / a);
}

// My first crack at demosaic
vec3 lanczos7x7_color(vec2 texel)
{
    ivec2 iTexel = ivec2(floor(texel));
    // Visit a 5x5 neighborhood
    vec3 rgb = vec3(0);
    vec3 weights = vec3(0);
    const int dt = 3;  // 1->3x3; 2->5x5; 3->7x7
    const float window = dt + 0.5;  // Keep neighborhood symmetric-ish, shortest distance not visited here
    // Maybe both sampling rates should be 2.0 since that's the band limit for this raster
    // 2.5 to give it a bit more blur
    const float rb_sampling_rate = 2.0;  // neighbor red/blue are 2 cells away
    const float g_sampling_rate = 2.0;  // sqrt(2.0);  // neighbor greens are diagonal
    ivec2 max_tex = textureSize(bayer, 0) - ivec2(1);
    ivec2 min_tex = ivec2(0);
    for (int x = iTexel.x - dt; x <= iTexel.x + dt; ++x)
    {
        // RGGB aware manual clamp to edge
        // Find the closest in-bounds texel matching the parity of the logical texel
        int cx = x >= 0 ? x : (-x) & 1;
        cx = cx <= max_tex.x ? cx : max_tex.x - ((cx + 1) & 1);

        float dx = x - texel.x;
        for (int y = iTexel.y - dt; y <= iTexel.y + dt; ++y)
        {
            // RGGB aware manual clamp to edge
            // Find the closest in-bounds texel matching the parity of the logical texel
            int cy = y >= 0 ? y : (-y) & 1;
            cy = cy <= max_tex.y ? cy : max_tex.y - ((cy + 1) & 1);

            float dy = y - texel.y;
            float dist = length(vec2(dx, dy));
            if (dist > window)
                continue;
            vec2 xa = vec2(dist, window);

            // A) distance based lanczos weight. I made this up.
            float w_rb1 = lanczos(xa/rb_sampling_rate);
            float w_g1 = lanczos(xa/g_sampling_rate);

            // B) scalar product standard lanczos weight. This is what the books say
            float w_rb2 = lanczos(vec2(dx, window)/rb_sampling_rate) * lanczos(vec2(dy, window)/rb_sampling_rate);
            // but with green texel offset rotated 45 degrees, because that's green's actual rectangular lattice
            const float s22 = sqrt(2.0)/2.0;
            const mat2 rot45 = mat2(s22, -s22, s22, s22);
            vec2 dxy_g = vec2(dx, dy) * rot45;
            float w_g2 = lanczos(vec2(dxy_g.x, window)/g_sampling_rate) * lanczos(vec2(dxy_g.y, window)/g_sampling_rate);

            float w = 1.0;

            if ((y & 1) == 0 && (x & 1) == 0) {  // red
                w = w_rb2;
                rgb.r += w * texelFetch(bayer, ivec2(cx, cy), 0).r;
                weights.r += w;
            }
            else if ((y & 1) != 0 && (x & 1) != 0) {  // blue
                w = w_rb2;
                rgb.b += w * texelFetch(bayer, ivec2(cx, cy), 0).r;
                weights.b += w;
            }
            else {  // green
                w = w_g2;
                rgb.g += w * texelFetch(bayer, ivec2(cx, cy), 0).r;
                weights.g += w;
            }
        }
    }
    return rgb / weights;
}

void main()
{
    // Fractional texel
    vec2 texel = tex_coord * textureSize(bayer, 0);
    vec3 rgb = lanczos7x7_color(texel);  // better than mhc but softer
    // vec3 rgb = mhc_color(texel);  // bad zippering near door
    // vec3 rgb = linear_color(texel);  // different bad zippering
    color = vec4(rgb, 1);
}

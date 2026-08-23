#version 410 core

uniform sampler2D bayer;

uniform vec3 white_level = vec3(1);
uniform vec3 as_shot_neutral = vec3(1);
uniform ivec4 cfa_pattern = ivec4(0, 1, 1, 2);

in vec2 tex_coord;
out vec4 frag_color;


// Texel type in a RGGB Bayer Color Filter Array (CFA) camera sensor
const int CFA_NONE = -1;
const int CFA_RED = 0;
const int CFA_GREEN1 = 1;  // green in red row
const int CFA_GREEN2 = 2;  // green in blue row
const int CFA_BLUE = 3;

struct CfaSample {
    float i;  // intensity
    int cfa;
};

struct Rgb {
  vec3 rgb;  // accumulated color
  vec3 unclipped_weight;  // accumulated weight
  vec3 clipped_weight;  // accumulated weight rejected due to clipping
};

int cfa_for_texel(ivec2 texel) {
    ivec2 parity = texel & ivec2(1);
    int index;
    if (parity == ivec2(0)) index = 0;  // red in RGGB
    else if (parity == ivec2(1)) index = 3;  // blue in RGGB
    else if (parity == ivec2(1, 0)) index = 1;  // G1 in RGGB
    else index = 2;  // G2 in RGGB
    // handle alternate cfa pattern
    int shift = 0;
    for (int i = 0; i < 4; ++i) {
        if (cfa_pattern[i] == 0) {
            shift = -i;
            break;
        }
    }
    index = (index + shift) % 4;
    return index;
}

int cfa_for_texel(vec2 texel) {
    return cfa_for_texel(ivec2(floor(texel)));
}

vec3 mask_for_cfa(int cfa) {
    if (cfa == CFA_RED) return vec3(1, 0, 0);
    else if (cfa == CFA_GREEN1) return vec3(0, 1, 0);
    else if (cfa == CFA_GREEN2) return vec3(0, 1, 0);
    else if (cfa == CFA_BLUE) return vec3(0, 0, 1);
    else return vec3(0);
}

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

// Lanczos 5x5 for green, with median chroma
// "LGMC5"

/*
  To get the median chroma values, we first collect the closest 8 values
  of Cb = blue - green,  and Cr = red - green

  Case1: centered on BLUE; Cr:"+" Cb:"-"
  x = -2 -1 +0 +1 +2   y =

       B  G  B  G  B   -2
             |
       G  R++G++R  G   -1
          +  |  +
       B--G--B--G--B   +0
          +  |  +
       G  R++G++R  G   +1
             |
       B  G  B  G  B   +2

       Cb: (0,0)-(0,-1), (0,0)-(0,1), (0,0)-(1,0), (0,0)-(-1,0)
           (0,-2)-(0,-1), (-2,0)-(-1,0), (2,0)-(1,0), (0,2)-(0,1)
       Cr: (-1,-1)-(0,-1), (-1, -1)-(-1,0), (1,-1)-(0,-1), (1,-1)-(1,0)
           (-1,1)-(0,1), (-1, 1)-(1,0), (1,1)-(0,1), (1,1)-(1,0)

  Case 2: centered on GREEN in RED row
  x = -2 -1 +0 +1 +2   y =

       G  R  G  R  G   -2
             |
       B  G--B--G  B   -1
          +  |  +
       G++R++G++R++G   +0
          +  |  +
       B  G--B--G  B   +1
             |
       G  R  G  R  G   +2

/* */

// Chroma texel index pairs for central green texel
const ivec2 CRB_AT_GBR[16] = ivec2[16](
        ivec2(0,-1),ivec2(0,-2),
        ivec2(0,-1),ivec2(-1,-1),
        ivec2(0,-1),ivec2(1,-1),
        ivec2(0,-1),ivec2(0,0),  // TODO: weight repeated green 0.5
        ivec2(0,1),ivec2(0,0),  // TODO: weight repeated green 0.5
        ivec2(0,1),ivec2(-1,1),
        ivec2(0,1),ivec2(1,1),
        ivec2(0,1),ivec2(0,2));

const ivec2 CRB_AT_GRB[16] = ivec2[16](
        ivec2(-1,0),ivec2(-2,0),
        ivec2(-1,0),ivec2(-1,-1),
        ivec2(-1,0),ivec2(-1,1),
        ivec2(-1,0),ivec2(0,0),  // TODO: weight repeated green 0.5
        ivec2(1,0),ivec2(0,0),  // TODO: weight repeated green 0.5
        ivec2(1,0),ivec2(2,0),
        ivec2(1,0),ivec2(1,-1),
        ivec2(1,0),ivec2(1,1));

// Chroma texel index pairs for central texel red or blue
const ivec2 CRB_AT_RB[16] = ivec2[16](
        ivec2(0,0),ivec2(0,-1),
        ivec2(0,0),ivec2(0,1),
        ivec2(0,0),ivec2(1,0),
        ivec2(0,0),ivec2(-1,0),
        ivec2(0,-2),ivec2(0,-1),
        ivec2(-2,0),ivec2(-1,0),
        ivec2(2,0),ivec2(1,0),
        ivec2(0,2),ivec2(0,1));

const ivec2 CRB_AT_BR[16] = ivec2[16](
        ivec2(-1,-1),ivec2(0,-1),
        ivec2(-1,-1),ivec2(-1,0),
        ivec2(1,-1),ivec2(0,-1),
        ivec2(1,-1),ivec2(1,0),
        ivec2(-1,1),ivec2(0,1),
        ivec2(-1,1),ivec2(-1,0),
        ivec2(1,1),ivec2(0,1),
        ivec2(1,1),ivec2(1,0));

const float LGMC5_G_AT_RB[25] = float[25](
  //  x=-2    x=-1    x=+0    x=+1    x=+2
    +0.000, -0.056, +0.000, -0.056, +0.000,   // y=-2:
    -0.056, +0.000, +0.348, +0.000, -0.056,   // y=-1:
    +0.000, +0.348, +1.000, +0.348, +0.000,   // y=+0:
    -0.056, +0.000, +0.348, +0.000, -0.056,   // y=+1:
    +0.000, -0.056, +0.000, -0.056, +0.000    // y=+2:
);

struct ChromaSample {
    float chroma;
    float weight;
};

// Sort two values
void sort2(inout float a, inout float b) {
    float t = a;
    a = min(t, b);
    b = max(t, b);
}

// Sort an array of 8 floats, for use in median calculation
void sort8(inout float arr[8]) {
    // Pass 1
    sort2(arr[0], arr[1]); sort2(arr[2], arr[3]);
    sort2(arr[4], arr[5]); sort2(arr[6], arr[7]);

    // Pass 2
    sort2(arr[0], arr[2]); sort2(arr[1], arr[3]);
    sort2(arr[4], arr[6]); sort2(arr[5], arr[7]);

    // Pass 3
    sort2(arr[0], arr[1]); sort2(arr[2], arr[3]);
    sort2(arr[4], arr[5]); sort2(arr[6], arr[7]);

    // Pass 4
    sort2(arr[0], arr[4]); sort2(arr[1], arr[5]);
    sort2(arr[2], arr[6]); sort2(arr[3], arr[7]);

    // Pass 5
    sort2(arr[2], arr[4]); sort2(arr[3], arr[5]);

    // Pass 6
    sort2(arr[1], arr[2]); sort2(arr[3], arr[4]); sort2(arr[5], arr[6]);
}

float median_chroma5x5(ivec2 CX_AT[16], CfaSample samples[25]) {
    const int NBR = 2;
    const int GRID_SIZE = 5;
    float cb_array[8];
    for (int i = 0; i < 8; i++) {
        ivec2 rb_ix = CX_AT[i * 2] + ivec2(NBR);
        float rb = samples[rb_ix.x + GRID_SIZE * rb_ix.y].i;
        ivec2 g_ix = CX_AT[i * 2 + 1] + ivec2(NBR);
        float g = samples[g_ix.x + GRID_SIZE * g_ix.y].i;
        cb_array[i] = rb - g;
    }
    sort8(cb_array);
    float cb_med = 0.5 * (cb_array[3] + cb_array[4]);  // median Cb chroma
    // float cb_med = cb_array[4];  // minimum for testing
    return cb_med;
}

vec3 lgmc5_color(vec2 texel)
{
    // Initialize array of samples, without fetching anything yet
    const int NBR = 2;  // number of texels to go in each direction
    const int GRID_SIZE = 2 * NBR + 1;
    CfaSample[GRID_SIZE*GRID_SIZE] samples;
    for (int i = 0; i < GRID_SIZE*GRID_SIZE; i++) {
        samples[i] = CfaSample(0, CFA_NONE);
    }

    // Fetch relevant texels into the sample array
    // TODO: just the needed subset
    ivec2 txl = ivec2(floor(texel));
    for (int y = 0; y < GRID_SIZE; y++) {
        for (int x = 0; x < GRID_SIZE; x++) {
            int ix = y * GRID_SIZE + x;
            ivec2 tx = ivec2(txl.x + x - NBR, txl.y + y - NBR);
            samples[ix].i = texelFetch(bayer, tx, 0).r;
            samples[ix].cfa = cfa_for_texel(tx);
        }
    }

    // Clamp to edge
    for (int y = 0; y < GRID_SIZE; y++) {
        for (int x = 0; x < GRID_SIZE; x++) {
            int ix = y * GRID_SIZE + x;
            ivec2 tx0 = ivec2(txl.x + x - NBR, txl.y + y - NBR);
            ivec2 tx1 = rggb_clamp_to_edge(tx0);
            if (tx0 != tx1) {
                // copy tx1 value to tx0 position
                ivec2 ix0 = tx0 - txl + ivec2(NBR);
                ivec2 ix1 = tx1 - txl + ivec2(NBR);
                int src = ix1.x + GRID_SIZE * ix1.y;
                int dst = ix0.x + GRID_SIZE * ix0.y;
                samples[dst].i = samples[src].i;
                // .cfa should already be the same
            }
        }
    }

    // accumulate green lanczos
    int cfa = cfa_for_texel(txl);
    vec3 mask0 = mask_for_cfa(CFA_GREEN1);
    Rgb rgb = Rgb(vec3(0), vec3(0), vec3(0));
    for (int i = 0; i < GRID_SIZE*GRID_SIZE; i++) {
        vec3 mask1 = mask_for_cfa(samples[i].cfa);
        float w = LGMC5_G_AT_RB[i];
        rgb.rgb += w * mask0 * mask1 * samples[i].i;
        rgb.unclipped_weight += w * mask0 * mask1;
        // TODO: clip highlights
    }

    // Duplicate green channel - until we have chroma median fully working
    rgb.rgb.g /= rgb.unclipped_weight.g;
    rgb.rgb = rgb.rgb.ggg;
    rgb.unclipped_weight = vec3(1);

    // Use median chroma values to generate red/blue
    if (cfa == CFA_BLUE) {
        float cb_med = median_chroma5x5(CRB_AT_RB, samples);
        rgb.rgb.b = cb_med + rgb.rgb.g;
        float cr_med = median_chroma5x5(CRB_AT_BR, samples);
        rgb.rgb.r = cr_med + rgb.rgb.g;
    }
    else if (cfa == CFA_RED) {
        float cb_med = median_chroma5x5(CRB_AT_BR, samples);
        rgb.rgb.b = cb_med + rgb.rgb.g;
        float cr_med = median_chroma5x5(CRB_AT_RB, samples);
        rgb.rgb.r = cr_med + rgb.rgb.g;
    }
    else if (cfa == CFA_GREEN1) {
        float cb_med = median_chroma5x5(CRB_AT_GBR, samples);
        rgb.rgb.b = cb_med + rgb.rgb.g;
        float cr_med = median_chroma5x5(CRB_AT_GRB, samples);
        rgb.rgb.r = cr_med + rgb.rgb.g;
    }
    else if (cfa == CFA_GREEN2) {
        float cb_med = median_chroma5x5(CRB_AT_GRB, samples);
        rgb.rgb.b = cb_med + rgb.rgb.g;
        float cr_med = median_chroma5x5(CRB_AT_GBR, samples);
        rgb.rgb.r = cr_med + rgb.rgb.g;
    }

    return vec3(rgb.rgb);

}


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

// Bilinear demosaicking
vec3 linear_color(vec2 texel)
{
    // fract(texel) should be near 0.5 if textures are aligned correctly
    ivec2 txl = ivec2(floor(texel));
    int x = txl.x;
    int y = txl.y;
    int cfa = cfa_for_texel(txl);
    vec3 result = vec3(0);
    for (int t = 0; t < 9; ++t)
    {
        ivec2 tx = rggb_clamp_to_edge(txl + LIN_NBRS[t]);
        float intensity = texelFetch(bayer, tx, 0).r;
        if (cfa == CFA_RED) {  // red
            result.r += intensity * LIN_RGB_AT_RGB[t];
            result.g += intensity * LIN_G_AT_RB[t];
            result.b += intensity * LIN_RB_AT_BR[t];
        }
        else if (cfa == CFA_BLUE) {  // blue
            result.r += intensity * LIN_RB_AT_BR[t];
            result.g += intensity * LIN_G_AT_RB[t];
            result.b += intensity * LIN_RGB_AT_RGB[t];
        }
        else if (cfa == CFA_GREEN1) {  // green in red row
            result.r += intensity * LIN_RB_AT_G_IN_RB[t];
            result.g += intensity * LIN_RGB_AT_RGB[t];
            result.b += intensity * LIN_RB_AT_G_IN_BR[t];
        }
        else if (cfa == CFA_GREEN2) {  // green in blue row
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

// Malvar He Cutler Linear Image Demosaicking on 5x5 neighborhood
vec3 mhc_color(vec2 texel)
{
    // fract(texel) should be near 0.5 if textures are aligned correctly
    ivec2 txl = ivec2(floor(texel));
    int x = txl.x;
    int y = txl.y;
    int cfa = cfa_for_texel(txl);
    vec3 result = vec3(0);
    for (int t = 0; t < 13; ++t)
    {
        ivec2 tx = rggb_clamp_to_edge(txl + MHC_NBRS[t]);
        float intensity = MHC_SCALE * texelFetch(bayer, tx, 0).r;
        if (cfa == CFA_RED) {  // red
            result.r += intensity * MHC_RGB_AT_RGB[t];
            result.g += intensity * MHC_G_AT_R_OR_B[t];
            result.b += intensity * MHC_RB_AT_BR[t];
        }
        else if (cfa == CFA_BLUE) {  // blue
            result.r += intensity * MHC_RB_AT_BR[t];
            result.g += intensity * MHC_G_AT_R_OR_B[t];
            result.b += intensity * MHC_RGB_AT_RGB[t];
        }
        else if (cfa == CFA_GREEN1) {  // green in red row
            result.r += intensity * MHC_RB_AT_G_IN_RB[t];
            result.g += intensity * MHC_RGB_AT_RGB[t];
            result.b += intensity * MHC_RB_AT_G_IN_BR[t];
        }
        else if (cfa == CFA_GREEN2) {  // green in blue row
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

const vec3[3] rgb_mask = vec3[3](
    vec3(1, 0, 0),  // red
    vec3(0, 1, 0),  // green
    vec3(0, 0, 1)  // blue
);

// My first crack at demosaic
vec3 lanczos7x7_color(vec2 texel)
{
    vec3 rgb = vec3(0);  // accumulated color
    vec3 weights = vec3(0);  // accumulated non-clipped sample weights
    vec3 clipped_weights = vec3(0);  // accumulated clipped sample weights
    // sensor space color of neutral overexposed pixel
    vec3 clipped_rgb = white_level * as_shot_neutral;

    // Use two different Nyquist rates for green vs red/blue pixels
    const float rb_sampling_rate = 2.0;  // neighbor red/blue are 2 cells away
    const float g_sampling_rate = sqrt(2.0);  // neighbor greens are diagonal
    // Texture coordinate bounds for this tile
    ivec2 max_tex = textureSize(bayer, 0) - ivec2(1);
    ivec2 min_tex = ivec2(0);
    // Visit a 7x7 neighborhood
    ivec2 iTexel = ivec2(floor(texel));
    const int dt = 3;  // 1->3x3; 2->5x5; 3->7x7
    const float window = dt + 0.9;  // Keep neighborhood symmetric-ish, shortest distance not visited here
    for (int x = iTexel.x - dt; x <= iTexel.x + dt; ++x)
    {
        float dx = x - texel.x;
        for (int y = iTexel.y - dt; y <= iTexel.y + dt; ++y)
        {
            ivec2 tx = rggb_clamp_to_edge(ivec2(x, y));
            float dy = y - texel.y;

            // Scalar product standard lanczos weight.
            float w_rb = lanczos(vec2(dx, window)/rb_sampling_rate) * lanczos(vec2(dy, window)/rb_sampling_rate);
            // rotate green texel offset by 45 degrees, because that's green's actual rectangular lattice
            const float s22 = sqrt(2.0)/2.0;
            const mat2 rot45 = mat2(s22, -s22, s22, s22);
            vec2 dxy_g = vec2(dx, dy) * rot45;
            float w_g = lanczos(vec2(dxy_g.x, window)/g_sampling_rate) * lanczos(vec2(dxy_g.y, window)/g_sampling_rate);

            float intensity = texelFetch(bayer, tx, 0).r;

            float w = 0.0;  // weight for this sample
            vec3 mask = vec3(0, 0, 0);  // color mask for this sample

            if ((y & 1) == 0 && (x & 1) == 0) { // red
                w = w_rb;
                mask = rgb_mask[cfa_pattern[0]];
            }
            else if ((y & 1) == 0 && (x & 1) != 0) { // green1
                w = w_rb;
                mask = rgb_mask[cfa_pattern[1]];
            }
            else if ((y & 1) != 0 && (x & 1) == 0) { // green2
                w = w_rb;
                mask = rgb_mask[cfa_pattern[2]];
            }
            else { // blue
                w = w_rb;
                mask = rgb_mask[cfa_pattern[3]];
            }

            // Only accumulate colors where the intensity is not clipped to the max
            if (lessThan(mask * intensity, clipped_rgb) == bvec3(true)) {
                rgb += w * mask * intensity;
                weights += w * mask;
            }
            else {
                clipped_weights += w * mask;
            }
        }
    }

    // handle fully clipped and zero clipped cases first
    if (weights == vec3(0)) return clipped_rgb;
    vec3 linear_rgb = rgb / max(weights, vec3(0.0001));
    if (clipped_weights == vec3(0)) return linear_rgb;

    // smoothly interpolate between clipped and unclipped at the boundary
    vec3 total_weights = weights + clipped_weights;
    vec3 clip_ratio = clipped_weights / max(total_weights, vec3(0.0001));
    vec3 blend_factor = smoothstep(0.2, 0.8, clip_ratio);
    return mix(linear_rgb, clipped_rgb, blend_factor);
}

void main()
{
    // Fractional texel
    vec2 texel = tex_coord * textureSize(bayer, 0);
    // vec3 rgb = lanczos7x7_color(texel);  // better than mhc but softer
    vec3 rgb = lgmc5_color(texel);
    // vec3 rgb = mhc_color(texel);  // bad zippering near door
    // vec3 rgb = linear_color(texel);  // different bad zippering
    frag_color = vec4(rgb, 1);
}

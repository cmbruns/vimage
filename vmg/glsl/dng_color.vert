#version 410 core

// From google AI
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec2 aTexCoords;

out vec2 TexCoords;
flat out mat3 v_CameraToLinearSRGB;

// Control Flag
uniform bool u_HasForwardMatrix;

// Pipeline 1: Forward Matrix Metadata
uniform mat3 u_ForwardMatrix;

// Pipeline 2: Color Matrix Metadata (Fallback)
uniform mat3 u_ColorMatrixInterpolated;
uniform vec3 u_AsShotNeutral;

void main() {
    gl_Position = vec4(aPos, 1.0);
    TexCoords = aTexCoords;

    // Hardcoded Color Space Conversion Constants
    mat3 bradfordD50toD65 = mat3(
        0.9555766, -0.0282895,  0.0122982,
       -0.0230393,  1.0099416, -0.0204830,
        0.0631636,  0.0210077,  1.3299098
    );

    mat3 xyzToSRGB = mat3(
         3.2404542, -0.9692660,  0.0556434,
        -1.5371385,  1.8760108, -0.2040259,
        -0.4985314,  0.0415560,  1.0572252
    );

    // Branching here costs nothing because it executes only 4 times total
    if (u_HasForwardMatrix) {
        // --- PATH A: Forward Matrix Pipeline ---
        // ForwardMatrix maps white-balanced camera space directly to XYZ D50.
        // So we just string the operations from right to left.
        v_CameraToLinearSRGB = xyzToSRGB * bradfordD50toD65 * u_ForwardMatrix;
    }
    else {
        // --- PATH B: Color Matrix Fallback Pipeline ---
        // ColorMatrix requires us to undo white balance first, then invert the matrix.
        mat3 wbGainMatrix = mat3(
            1.0 / u_AsShotNeutral.r, 0.0, 0.0,
            0.0, 1.0 / u_AsShotNeutral.g, 0.0,
            0.0, 0.0, 1.0 / u_AsShotNeutral.b
        );

        mat3 sensorToXYZ = inverse(u_ColorMatrixInterpolated) * wbGainMatrix;
        v_CameraToLinearSRGB = xyzToSRGB * bradfordD50toD65 * sensorToXYZ;
    }
}


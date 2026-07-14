#version 410 core

out vec4 fragColor;

const float uStipplePeriod = 16.0;   // pixels per color block

void main()
{
    // Screen-space coordinate
    float s = gl_FragCoord.x + gl_FragCoord.y;

    // Divide by period to make coarse blocks
    int block = int(s / uStipplePeriod);

    bool even = (block & 1) == 0;

    vec3 color = even ? vec3(1.0, 1.0, 0.0)   // yellow
                      : vec3(0.0, 0.0, 1.0);  // blue

    fragColor = vec4(color, 0.5); // 50% transparency
}

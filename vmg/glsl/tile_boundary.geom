#version 410 core

layout(lines) in;
layout(triangle_strip, max_vertices = 4) out;

const float uLineWidth = 2.2;
uniform vec2 uViewportSize;   // screen size in pixels

flat in int vID[];
flat out int vEdgeID;         // 0=top, 1=right, 2=bottom, 3=left

void main()
{
    // Input positions in NDC
    vec2 p0 = gl_in[0].gl_Position.xy;
    vec2 p1 = gl_in[1].gl_Position.xy;

    // Determine which edge this is based on vertex indices
    int i0 = vID[0];
    int i1 = vID[1];

    // Your quad vertex order:
    // 0: top-left
    // 1: top-right
    // 2: bottom-left
    // 3: bottom-right

    if (i0 == 0 && i1 == 1)      vEdgeID = 0; // top
    else if (i0 == 1 && i1 == 3) vEdgeID = 1; // right
    else if (i0 == 3 && i1 == 2) vEdgeID = 2; // bottom
    else if (i0 == 2 && i1 == 0) vEdgeID = 3; // left
    else                         vEdgeID = 4; // fallback (should not happen)

    // Compute thickness in NDC
    float w = uLineWidth / uViewportSize.y;

    vec2 dir  = normalize(p1 - p0);
    vec2 perp = vec2(-dir.y, dir.x);
    vec2 off  = perp * w;

    // Emit quad
    gl_Position = vec4(p0 + off, 0, 1);
    EmitVertex();

    gl_Position = vec4(p0 - off, 0, 1);
    EmitVertex();

    gl_Position = vec4(p1 + off, 0, 1);
    EmitVertex();

    gl_Position = vec4(p1 - off, 0, 1);
    EmitVertex();

    EndPrimitive();
}

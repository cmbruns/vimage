#version 410 core

layout(lines) in;
layout(triangle_strip, max_vertices = 4) out;

const float uLineWidth = 3.0;   // in pixels
uniform vec2 uViewportSize;       // (width, height)

out vec2 vStippleCoord;

void main()
{
    // Convert pixel width to NDC offset
    float w = uLineWidth / uViewportSize.y;  // use vertical scale for uniform thickness

    vec2 p0 = gl_in[0].gl_Position.xy;
    vec2 p1 = gl_in[1].gl_Position.xy;

    // Direction of the line in NDC
    vec2 dir = normalize(p1 - p0);

    // Perpendicular
    vec2 perp = vec2(-dir.y, dir.x);

    // Offset for thickness
    vec2 off = perp * w;

    // Emit the quad as a triangle strip
    gl_Position = vec4(p0 + off, 0.0, 1.0);
    vStippleCoord = vec2(0.0, 0.0);
    EmitVertex();

    gl_Position = vec4(p0 - off, 0.0, 1.0);
    vStippleCoord = vec2(0.0, 1.0);
    EmitVertex();

    gl_Position = vec4(p1 + off, 0.0, 1.0);
    vStippleCoord = vec2(1.0, 0.0);
    EmitVertex();

    gl_Position = vec4(p1 - off, 0.0, 1.0);
    vStippleCoord = vec2(1.0, 1.0);
    EmitVertex();

    EndPrimitive();
}

#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D u_tex;
uniform float u_time;
uniform vec2 u_resolution;

varying vec2 v_texcoord;

void main() {
    vec2 uv = v_texcoord;
    vec2 dc = uv - 0.5;
    float dist = dot(dc, dc);
    uv = uv + dc * dist * 0.08;

    vec4 col = texture2D(u_tex, uv);
    float scan = sin((uv.y + u_time * 0.02) * u_resolution.y * 3.14159) * 0.04;
    col.rgb -= scan;
    col.rgb *= 0.92 + 0.08 * sin(u_time * 2.0 + uv.x * 80.0);
    gl_FragColor = col;
}

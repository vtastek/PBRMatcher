#version 330 core
in vec2 TexCoord;

uniform sampler2D textureSampler1;  // First texture
uniform sampler2D textureSampler2;  // Second texture
uniform float time;                 // For animated effects
uniform float mixRatio;             // Blend ratio between textures
uniform float rot;
uniform float hue;
uniform float sat;
uniform float val;

out vec4 FragColor;

// Convert RGB to HSV
vec3 RGBtoHSV(vec3 color) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(color.bg, K.wz), vec4(color.gb, K.xy), step(color.b, color.g));
    vec4 q = mix(vec4(p.xyw, color.r), vec4(color.r, p.yzx), step(p.x, color.r));
    
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

// Convert HSV to RGB
vec3 HSVtoRGB(vec3 color) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(color.xxx + K.xyz) * 6.0 - K.www);
    return color.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), color.y);
}


vec2 rotate(vec2 tex, float angle) {
    float s = sin(angle);
    float c = cos(angle);
    mat2 rot = mat2(c, -s, s, c);
    return rot * tex;
}

void main() {
    // Sample both textures
    vec4 texColor1 = texture(textureSampler1, TexCoord);
    vec2 tex = rotate(TexCoord, rot);
    vec4 texColor2 = texture(textureSampler2, tex);

    vec3 hsv = RGBtoHSV(texColor2.rgb);
    // hue is between -180 and 180
    hsv.x += hue/360.0;
    if (hsv.x > 1.0) {
        hsv.x -= 1.0;
    } else if (hsv.x < 0.0) {
        hsv.x += 1.0;
    }
    hsv.y *= sat;
    hsv.z *= val;

    texColor2.rgb = HSVtoRGB(hsv);

    // Blend the two textures
    vec4 blendedColor = mix(texColor1, texColor2, step(1.0 - mixRatio, 1.0 - TexCoord.y));
    
    FragColor = vec4(blendedColor.rgb, 1.0);
}

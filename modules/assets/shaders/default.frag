#version 330 core
in vec2 TexCoord;

uniform sampler2D textureSampler1;  // First texture
uniform sampler2D textureSampler2;  // Second texture
uniform float time;                 // For animated effects
uniform float mixRatio;             // Blend ratio between textures

out vec4 FragColor;

void main() {
    // Sample both textures
    vec4 texColor1 = texture(textureSampler1, TexCoord);
    vec4 texColor2 = texture(textureSampler2, TexCoord);
    
    // Animated mix ratio (can be overridden by uniform)
    float animatedMix = (sin(time) + 1.0) / 2.0;
    float currentMix = mixRatio > 0.0 ? mixRatio : animatedMix;
    
    // Blend the two textures
    vec4 blendedColor = mix(texColor1, texColor2, currentMix);
    
    // Example effect: Vignette
    vec2 center = vec2(0.5, 0.5);
    float dist = distance(TexCoord, center);
    float vignette = smoothstep(0.5, 0.2, dist);
    
    // Apply vignette
    vec3 finalColor = blendedColor.rgb * vignette;
    
    FragColor = vec4(texColor1, 1.0);
}
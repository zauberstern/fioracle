import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useTexture } from "@react-three/drei";
import * as THREE from "three";
import CustomShaderMaterial from "three-custom-shader-material/vanilla";
import { useMarketStore } from "../store/marketStore";

const crackVertexShader = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vPosition;

  void main() {
    vUv = uv;
    vPosition = position;
  }
`;

const crackFragmentShader = /* glsl */ `
  uniform float uIntensity;
  uniform float uTime;
  uniform sampler2D uAlbedo;
  varying vec2 vUv;
  varying vec3 vPosition;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float crackPattern(vec2 uv) {
    float n = noise(uv * 8.0);
    n += noise(uv * 16.0) * 0.5;
    n += noise(uv * 32.0) * 0.25;
    return smoothstep(0.42, 0.58, n);
  }

  void main() {
    vec2 centeredUv = vUv - 0.5;
    float dist = length(centeredUv * vec2(1.0, 2.2));
    float crack = crackPattern(vUv + vec2(uTime * 0.015, 0.0));
    float fade = 1.0 - smoothstep(0.25, 0.55, dist);

    vec3 groundColor = texture2D(uAlbedo, vUv * 2.0).rgb * 0.55;
    vec3 glowColor = vec3(1.0, 0.22, 0.05);
    float glowStrength = crack * uIntensity * fade;

    vec3 finalColor = mix(groundColor, glowColor, glowStrength);
    csm_DiffuseColor = vec4(finalColor, 1.0);
    csm_Emissive = glowColor * glowStrength * 2.5;
  }
`;

export function Rift({ position = [0, 0.05, -8] as [number, number, number] }) {
  const albedo = useTexture("/textures/cracked/Ground048_1K-JPG_Color.jpg");
  albedo.wrapS = albedo.wrapT = THREE.RepeatWrapping;

  const uniformsRef = useRef({
    uIntensity: { value: 0 },
    uTime: { value: 0 },
    uAlbedo: { value: albedo },
  });

  const material = useMemo(() => {
    uniformsRef.current.uAlbedo.value = albedo;
    return new CustomShaderMaterial({
      baseMaterial: THREE.MeshStandardMaterial,
      vertexShader: crackVertexShader,
      fragmentShader: crackFragmentShader,
      uniforms: uniformsRef.current,
      roughness: 0.92,
      metalness: 0.05,
    });
  }, [albedo]);

  useFrame(({ clock }) => {
    const intensity = useMarketStore.getState().interpolated.riftIntensity;
    uniformsRef.current.uIntensity.value = intensity;
    uniformsRef.current.uTime.value = clock.getElapsedTime();
  });

  return (
    <mesh
      position={position}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
      material={material}
    >
      <planeGeometry args={[20, 6, 64, 32]} />
    </mesh>
  );
}

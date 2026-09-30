import { forwardRef, useMemo } from "react";
import { Effect, BlendFunction } from "postprocessing";
import { Uniform, Vector2 } from "three";
import { useFrame } from "@react-three/fiber";
import { useMarketStore } from "../store/marketStore";

const fragmentShader = /* glsl */ `
uniform float uTime;
uniform float uStrength;
uniform vec2 uDistortion;

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec2 distortedUv = uv;
  float noise1 = sin(uv.y * 40.0 + uTime * 3.0) * 0.5 + 0.5;
  float noise2 = sin(uv.y * 60.0 - uTime * 2.5) * 0.5 + 0.5;
  float groundMask = smoothstep(0.0, 0.45, 1.0 - uv.y);

  distortedUv.x += noise1 * uDistortion.x * uStrength * groundMask;
  distortedUv.y += noise2 * uDistortion.y * uStrength * groundMask;

  outputColor = texture2D(inputBuffer, distortedUv);
}
`;

class HeatDistortionEffect extends Effect {
  constructor() {
    const uniforms = new Map<string, Uniform<unknown>>();
    uniforms.set("uTime", new Uniform(0));
    uniforms.set("uStrength", new Uniform(0));
    uniforms.set("uDistortion", new Uniform(new Vector2(0.003, 0.002)));
    super("HeatDistortionEffect", fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      uniforms: uniforms as Map<string, Uniform<number>>,
    });
  }

  update(_renderer: unknown, _inputBuffer: unknown, deltaTime: number) {
    this.uniforms.get("uTime")!.value += deltaTime;
  }
}

export const HeatDistortion = forwardRef(function HeatDistortion(
  _props: Record<string, never>,
  ref: React.Ref<HeatDistortionEffect>
) {
  const effect = useMemo(() => new HeatDistortionEffect(), []);

  useFrame(() => {
    const strength = useMarketStore.getState().interpolated.shimmerStrength;
    effect.uniforms.get("uStrength")!.value = strength;
  });

  return <primitive ref={ref} object={effect} dispose={null} />;
});

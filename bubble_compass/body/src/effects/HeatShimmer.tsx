import { Bloom, ChromaticAberration } from "@react-three/postprocessing";
import { useMarketStore } from "../store/marketStore";
import * as THREE from "three";

/** Sentiment-driven bloom/aberration; must live inside a single EffectComposer. */
export function HeatShimmer() {
  const strength = useMarketStore((s) => s.interpolated.shimmerStrength);
  return (
    <>
      <Bloom intensity={0.2 + strength * 1.4} luminanceThreshold={0.25} mipmapBlur />
      <ChromaticAberration
        offset={new THREE.Vector2(0.0004 + strength * 0.004, 0.0004)}
      />
    </>
  );
}

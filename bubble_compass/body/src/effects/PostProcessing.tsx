import {
  EffectComposer,
  Bloom,
  DepthOfField,
  Vignette,
  Noise,
  ChromaticAberration,
} from "@react-three/postprocessing";
import * as THREE from "three";
import { HeatDistortion } from "./HeatDistortion";

export function PostProcessing() {
  return (
    <EffectComposer>
      <HeatDistortion />
      <Bloom intensity={0.45} luminanceThreshold={0.2} mipmapBlur />
      <DepthOfField focusDistance={0.02} focalLength={0.05} bokehScale={2.4} />
      <Vignette eskil={false} offset={0.3} darkness={0.55} />
      <Noise opacity={0.02} />
      <ChromaticAberration offset={new THREE.Vector2(0.0005, 0.0005)} />
    </EffectComposer>
  );
}

import { Environment as DreiEnvironment, Sky, Stars, Cloud } from "@react-three/drei";
import { useMarketStore } from "../store/marketStore";

export function WorldEnvironment() {
  const riftIntensity = useMarketStore((s) => s.interpolated.riftIntensity);
  const turbidity = 8 + riftIntensity * 4;
  const rayleigh = 0.5 + riftIntensity * 2;

  return (
    <>
      <DreiEnvironment files="/hdri/forest_slope_1k.hdr" background={false} />
      <Sky
        distance={450000}
        sunPosition={[100, 20, 100]}
        turbidity={turbidity}
        rayleigh={rayleigh}
        mieCoefficient={0.005}
        mieDirectionalG={0.8}
      />
      {riftIntensity > 0.5 && (
        <Stars radius={100} depth={50} count={2000} factor={4} fade speed={1} />
      )}
      <Cloud
        position={[0, 15, -50]}
        opacity={0.28}
        speed={0.2}
        segments={20}
        volume={12}
        fade={40}
      />
      <fog
        attach="fog"
        args={["#0a1218", 30, Math.max(60, 150 - riftIntensity * 50)]}
      />
    </>
  );
}

import { useMemo } from "react";
import { useMarketStore } from "../store/marketStore";

interface FoliageChunkProps {
  chunkX: number;
  chunkZ: number;
}

export function FoliageChunk({ chunkX, chunkZ }: FoliageChunkProps) {
  const density = useMarketStore((s) => 1 - Math.min(1, s.interpolated.riftIntensity));
  const instances = useMemo(() => {
    const count = Math.floor(40 * density);
    const mats: [number, number, number][] = [];
    for (let i = 0; i < count; i++) {
      const x = chunkX * 64 + ((i * 17) % 60) - 30;
      const z = chunkZ * 64 + ((i * 13) % 60) - 30;
      mats.push([x, 0.4, z]);
    }
    return mats;
  }, [chunkX, chunkZ, density]);

  return (
    <group>
      {instances.map((pos, i) => (
        <mesh key={i} position={pos}>
          <coneGeometry args={[0.25, 1.2, 5]} />
          <meshStandardMaterial color="#2f6b3a" />
        </mesh>
      ))}
    </group>
  );
}

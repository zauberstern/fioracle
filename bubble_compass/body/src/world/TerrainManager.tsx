import { useChunkStreaming } from "../hooks/useChunkLoader";
import { TerrainChunk } from "./TerrainChunk";

export function TerrainManager() {
  const chunks = useChunkStreaming();
  return (
    <group>
      {chunks.map((chunk) => (
        <TerrainChunk
          key={chunk.key}
          chunkX={chunk.cx}
          chunkZ={chunk.cz}
          priceData={chunk.heights}
        />
      ))}
    </group>
  );
}

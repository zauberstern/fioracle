import { useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { useMarketStore } from "../store/marketStore";

export const CHUNK_SIZE = 64;
export const VIEW_RADIUS = 2;

export interface ChunkRecord {
  key: string;
  cx: number;
  cz: number;
  heights: Float32Array;
}

function heightsFor(cx: number, cz: number, trend: number, bump: number) {
  const res = 32;
  const out = new Float32Array(res * res);
  for (let i = 0; i < res; i++) {
    for (let j = 0; j < res; j++) {
      const nx = i / res + cx * 0.1;
      const nz = j / res + cz * 0.1;
      const ridge = Math.sin(nx * 3.1) * Math.cos(nz * 2.7) * (0.4 + bump);
      out[i * res + j] = (trend - 100) * 0.05 + ridge;
    }
  }
  return out;
}

export function useChunkStreaming(playerX = 0, playerZ = 0): ChunkRecord[] {
  const trend = useMarketStore((s) => s.interpolated.terrainHeight);
  const bump = useMarketStore((s) => s.interpolated.terrainBumpiness);
  const cx = Math.floor(playerX / CHUNK_SIZE);
  const cz = Math.floor(playerZ / CHUNK_SIZE);
  return useMemo(() => {
    const list: ChunkRecord[] = [];
    for (let dx = -VIEW_RADIUS; dx <= VIEW_RADIUS; dx++) {
      for (let dz = -VIEW_RADIUS; dz <= VIEW_RADIUS; dz++) {
        const x = cx + dx;
        const z = cz + dz;
        list.push({
          key: `${x}_${z}`,
          cx: x,
          cz: z,
          heights: heightsFor(x, z, trend, bump),
        });
      }
    }
    return list;
  }, [bump, cx, cz, trend]);
}

export function ChunkWatcher() {
  useFrame(() => undefined);
  return null;
}

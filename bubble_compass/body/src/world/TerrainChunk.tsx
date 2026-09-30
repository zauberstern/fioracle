import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { HeightfieldCollider, RigidBody } from "@react-three/rapier";
import { useFrame } from "@react-three/fiber";
import { useMarketStore } from "../store/marketStore";

const CHUNK_SIZE = 64;
const RESOLUTION = 32;

interface TerrainChunkProps {
  chunkX: number;
  chunkZ: number;
  priceData: Float32Array;
}

export function TerrainChunk({ chunkX, chunkZ, priceData }: TerrainChunkProps) {
  const geometry = useMemo(() => {
    const geo = new THREE.PlaneGeometry(
      CHUNK_SIZE,
      CHUNK_SIZE,
      RESOLUTION - 1,
      RESOLUTION - 1
    );
    geo.rotateX(-Math.PI / 2);
    const positions = geo.attributes.position;
    for (let i = 0; i < positions.count; i++) {
      const heightIndex = Math.min(i, priceData.length - 1);
      positions.setY(i, priceData[heightIndex] || 0);
    }
    geo.computeVertexNormals();
    return geo;
  }, [priceData]);

  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(0x4a7c59),
        roughness: 0.8,
        metalness: 0.1,
      }),
    []
  );

  useFrame(() => {
    const t = useMarketStore.getState().interpolated.riftIntensity;
    const calm = new THREE.Color(0x4a7c59);
    const warn = new THREE.Color(0xd4a373);
    material.color.lerpColors(calm, warn, t);
  });

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  return (
    <group position={[chunkX * CHUNK_SIZE, 0, chunkZ * CHUNK_SIZE]}>
      <mesh geometry={geometry} material={material} castShadow receiveShadow />
      <RigidBody type="fixed" colliders={false}>
        <HeightfieldCollider
          args={[
            RESOLUTION - 1,
            RESOLUTION - 1,
            Array.from(priceData),
            { x: CHUNK_SIZE, y: 1, z: CHUNK_SIZE },
          ]}
        />
      </RigidBody>
    </group>
  );
}

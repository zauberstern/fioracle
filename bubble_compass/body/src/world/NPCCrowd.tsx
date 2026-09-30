import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useMarketStore } from "../store/marketStore";

const COUNT = 80;

export function NPCCrowd() {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const seeds = useMemo(
    () =>
      Array.from({ length: COUNT }, (_, i) => ({
        x: (i % 10) * 1.6 - 8,
        z: Math.floor(i / 10) * 1.6 - 6,
        phase: i * 0.37,
      })),
    []
  );

  useFrame(({ clock }) => {
    if (!mesh.current) return;
    const m = useMarketStore.getState().interpolated.crowdMomentum;
    const t = clock.getElapsedTime();
    seeds.forEach((s, i) => {
      const stampede = m > 0 ? m * 4 : m * 2;
      dummy.position.set(
        s.x + Math.sin(t * (1.2 + stampede) + s.phase) * (1 + Math.abs(m) * 3),
        0.5,
        s.z + Math.cos(t * (0.9 + stampede) + s.phase) * (1 + Math.abs(m) * 2)
      );
      dummy.updateMatrix();
      mesh.current!.setMatrixAt(i, dummy.matrix);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, COUNT]}>
      <sphereGeometry args={[0.22, 8, 8]} />
      <meshStandardMaterial color="#c9d4e8" />
    </instancedMesh>
  );
}

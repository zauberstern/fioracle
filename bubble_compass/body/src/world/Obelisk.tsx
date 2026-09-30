import { useRef } from "react";
import { MeshTransmissionMaterial } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useMarketStore } from "../store/marketStore";

export function Obelisk({ position = [4, 0, 4] as [number, number, number] }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const glow = useMarketStore((s) => s.interpolated.obeliskGlow);

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.002;
    }
  });

  const crystalColor = new THREE.Color().setHSL(0.55, 0.6, 0.45 + glow * 0.25);
  const emissive = new THREE.Color().setHSL(0.08, 0.9, Math.min(0.55, glow * 0.45));

  return (
    <group position={position}>
      <mesh position={[0, 0.6, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.8, 1.2, 1.2, 6]} />
        <meshStandardMaterial color="#3a4a5a" roughness={0.9} metalness={0.15} />
      </mesh>

      <mesh ref={meshRef} position={[0, 3, 0]} castShadow>
        <octahedronGeometry args={[1.2, 0]} />
        <MeshTransmissionMaterial
          backside
          samples={8}
          thickness={0.5}
          chromaticAberration={0.1}
          anisotropy={0.3}
          distortion={0.15 + glow * 0.2}
          distortionScale={0.2}
          temporalDistortion={0.08}
          color={crystalColor}
          emissive={emissive}
          emissiveIntensity={0.4 + glow * 3}
        />
      </mesh>

      <mesh position={[0, 3, 0]}>
        <sphereGeometry args={[0.35, 16, 16]} />
        <meshBasicMaterial
          color={emissive}
          transparent
          opacity={0.25 + glow * 0.55}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

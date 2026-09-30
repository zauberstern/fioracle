import { Canvas } from "@react-three/fiber";
import { Physics } from "@react-three/rapier";
import { Suspense } from "react";
import { Character } from "../player/Character";
import { TerrainManager } from "./TerrainManager";
import { Obelisk } from "./Obelisk";
import { Rift } from "./Rift";
import { NPCCrowd } from "./NPCCrowd";
import { FoliageChunk } from "./FoliageChunk";
import { WorldEnvironment } from "./Environment";
import { PostProcessing } from "../effects/PostProcessing";
import { CameraDirector } from "../effects/CameraDirector";
import { useWebSocket } from "../hooks/useWebSocket";
import { useMarketStore } from "../store/marketStore";

export function WorldCanvas() {
  const asset = useMarketStore((s) => s.currentAsset);
  const connected = useMarketStore((s) => s.connected);
  useWebSocket({ asset });

  return (
    <div className="world-canvas-wrap">
      <div className="world-banner">
        <strong>World · in progress</strong>
        <div>
          {asset} · {connected ? "live" : "offline"} · WASD to walk
        </div>
      </div>
      <Canvas shadows camera={{ position: [0, 12, 22], fov: 50 }}>
        <color attach="background" args={["#081018"]} />
        <ambientLight intensity={0.25} />
        <directionalLight
          position={[20, 40, 10]}
          intensity={1.1}
          castShadow
          shadow-mapSize={[2048, 2048]}
        />
        <Suspense fallback={null}>
          <WorldEnvironment />
          <Physics gravity={[0, -9.81, 0]}>
            <TerrainManager />
            <FoliageChunk chunkX={0} chunkZ={0} />
            <Obelisk position={[4, 0, 4]} />
            <Rift position={[0, 0.02, -8]} />
            <NPCCrowd />
            <Character />
          </Physics>
          <PostProcessing />
          <CameraDirector />
        </Suspense>
      </Canvas>
    </div>
  );
}

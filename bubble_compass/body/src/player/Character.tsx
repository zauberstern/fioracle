import { KeyboardControls } from "@react-three/drei";
import Ecctrl from "ecctrl";

const keyboardMap = [
  { name: "forward", keys: ["ArrowUp", "KeyW"] },
  { name: "backward", keys: ["ArrowDown", "KeyS"] },
  { name: "leftward", keys: ["ArrowLeft", "KeyA"] },
  { name: "rightward", keys: ["ArrowRight", "KeyD"] },
  { name: "jump", keys: ["Space"] },
  { name: "run", keys: ["Shift"] },
];

export function Character() {
  return (
    <KeyboardControls map={keyboardMap}>
      <Ecctrl camCollision={false} camInitDis={-12} camMinDis={-22} camMaxDis={-6}>
        <mesh castShadow>
          <capsuleGeometry args={[0.35, 1.1, 4, 8]} />
          <meshStandardMaterial color="#e8eefc" />
        </mesh>
      </Ecctrl>
    </KeyboardControls>
  );
}

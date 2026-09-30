import { useThree } from "@react-three/fiber";
import { useEffect } from "react";
import gsap from "gsap";
import { useMarketStore } from "../store/marketStore";

export function CameraDirector() {
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    const unsub = useMarketStore.subscribe((state, prev) => {
      if (state.interpolated.riftIntensity > 0.8 && prev.interpolated.riftIntensity <= 0.8) {
        gsap.to(camera.position, { y: camera.position.y - 1.5, duration: 1.2 });
      }
    });
    return unsub;
  }, [camera]);
  return null;
}

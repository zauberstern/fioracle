/// <reference lib="webworker" />

self.onmessage = ({ data }: MessageEvent<{ cx: number; cz: number; resolution: number }>) => {
  const { cx, cz, resolution } = data;
  const heights = new Float32Array(resolution * resolution);
  for (let i = 0; i < resolution; i++) {
    for (let j = 0; j < resolution; j++) {
      heights[i * resolution + j] = Math.sin((cx + i) * 0.12) + Math.cos((cz + j) * 0.09);
    }
  }
  (self as DedicatedWorkerGlobalScope).postMessage({ cx, cz, heights }, [heights.buffer]);
};

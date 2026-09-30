/// <reference types="playwright" />
export {};

declare global {
  interface Window {
    __renderer?: { info: { memory: { geometries: number } } };
  }
}

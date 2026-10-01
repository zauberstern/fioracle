/// <reference types="vite/client" />

declare module "*.frag?raw" {
  const content: string;
  export default content;
}

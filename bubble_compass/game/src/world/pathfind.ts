/** BFS 4-directional pathfinding. No Kaplay import. */

export type Tile = { tx: number; ty: number };

const NEIGHBORS: Tile[] = [
  { tx: 0, ty: -1 }, // north
  { tx: 1, ty: 0 }, // east
  { tx: 0, ty: 1 }, // south
  { tx: -1, ty: 0 }, // west
];

/**
 * Shortest path excluding `from` and including `to`.
 * Returns [] when already there, null when blocked or unreachable.
 */
export function shortestPath(
  isSolid: (tx: number, ty: number) => boolean,
  from: Tile,
  to: Tile,
  mapW: number,
  mapH: number
): Tile[] | null {
  if (to.tx < 0 || to.ty < 0 || to.tx >= mapW || to.ty >= mapH) return null;
  if (isSolid(to.tx, to.ty)) return null;
  if (from.tx === to.tx && from.ty === to.ty) return [];

  const key = (t: Tile) => `${t.tx},${t.ty}`;
  const parent = new Map<string, Tile | null>();
  const queue: Tile[] = [from];
  parent.set(key(from), null);
  let expansions = 0;
  const cap = mapW * mapH;

  while (queue.length > 0) {
    const cur = queue.shift()!;
    expansions += 1;
    if (expansions > cap) return null;
    for (const d of NEIGHBORS) {
      const n: Tile = { tx: cur.tx + d.tx, ty: cur.ty + d.ty };
      if (n.tx < 0 || n.ty < 0 || n.tx >= mapW || n.ty >= mapH) continue;
      if (isSolid(n.tx, n.ty)) continue;
      const nk = key(n);
      if (parent.has(nk)) continue;
      parent.set(nk, cur);
      if (n.tx === to.tx && n.ty === to.ty) {
        const path: Tile[] = [];
        let step: Tile | null = n;
        while (step && !(step.tx === from.tx && step.ty === from.ty)) {
          path.push(step);
          step = parent.get(key(step)) ?? null;
        }
        path.reverse();
        return path;
      }
      queue.push(n);
    }
  }
  return null;
}

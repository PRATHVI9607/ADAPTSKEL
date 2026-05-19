interface Neighbor { v: number; w: number }

export class DijkstraEngine {
  private adj: Map<number, Neighbor[]> = new Map()

  private ensure(u: number): void {
    if (!this.adj.has(u)) this.adj.set(u, [])
  }

  insert(u: number, v: number, w: number): void {
    this.ensure(u)
    this.ensure(v)
    // Remove existing edge if present (update weight)
    this.adj.set(u, this.adj.get(u)!.filter(n => n.v !== v))
    this.adj.set(v, this.adj.get(v)!.filter(n => n.v !== u))
    this.adj.get(u)!.push({ v, w })
    this.adj.get(v)!.push({ v: u, w })
  }

  delete(u: number, v: number): void {
    if (this.adj.has(u)) {
      this.adj.set(u, this.adj.get(u)!.filter(n => n.v !== v))
    }
    if (this.adj.has(v)) {
      this.adj.set(v, this.adj.get(v)!.filter(n => n.v !== u))
    }
  }

  query(s: number, t: number): { distance: number; path: number[]; timeUs: number } {
    const t0 = performance.now()

    const dist = new Map<number, number>()
    const prev = new Map<number, number>()
    const visited = new Set<number>()

    // Simple priority queue via sorted array (adequate for demo sizes)
    const pq: Array<{ node: number; d: number }> = []

    for (const node of this.adj.keys()) dist.set(node, Infinity)
    dist.set(s, 0)
    pq.push({ node: s, d: 0 })

    while (pq.length > 0) {
      pq.sort((a, b) => a.d - b.d)
      const { node: u, d } = pq.shift()!

      if (visited.has(u)) continue
      visited.add(u)

      if (u === t) break

      const neighbors = this.adj.get(u) ?? []
      for (const { v, w } of neighbors) {
        if (visited.has(v)) continue
        const nd = d + w
        if (nd < (dist.get(v) ?? Infinity)) {
          dist.set(v, nd)
          prev.set(v, u)
          pq.push({ node: v, d: nd })
        }
      }
    }

    // Reconstruct path
    const path: number[] = []
    let cur: number | undefined = t
    while (cur !== undefined) {
      path.unshift(cur)
      cur = prev.get(cur)
    }

    const timeUs = (performance.now() - t0) * 1000

    const distance = dist.get(t) ?? Infinity
    return {
      distance: isFinite(distance) ? distance : -1,
      path: path[0] === s ? path : [],
      timeUs,
    }
  }

  reset(): void {
    this.adj.clear()
  }

  nodeCount(): number {
    return this.adj.size
  }

  edgeCount(): number {
    let count = 0
    for (const neighbors of this.adj.values()) count += neighbors.length
    return count / 2
  }
}

/**
 * DemoSimulator — self-contained graph simulation for offline mode.
 * Generates a random Erdős–Rényi graph and continuously applies
 * random insert / delete / query operations.
 */
import type { Node3D, Edge3D, AlgorithmStats, QueryResult } from './GraphState'
import { DijkstraEngine } from './DijkstraEngine'

function edgeId(u: number, v: number): string {
  return `${Math.min(u, v)}-${Math.max(u, v)}`
}

function randInt(max: number): number {
  return Math.floor(Math.random() * max)
}

function randBetween(a: number, b: number): number {
  return a + Math.random() * (b - a)
}

export type DemoCallback = (patch: {
  nodes: Map<number, Node3D>
  edges: Map<string, Edge3D>
  skeletonEdges: Set<string>
  heatScores: Map<string, number>
  hotPath: number[]
  stats: AlgorithmStats
  queryResult: QueryResult | null
}) => void

export class DemoSimulator {
  private N = 18
  private nodes: Map<number, Node3D> = new Map()
  private edges: Map<string, Edge3D> = new Map()
  private skeletonEdges: Set<string> = new Set()
  private heatScores: Map<string, number> = new Map()
  private hotPath: number[] = []
  private dijkstra = new DijkstraEngine()
  private callback: DemoCallback
  private insertTimer: ReturnType<typeof setInterval> | null = null
  private queryTimer: ReturnType<typeof setInterval> | null = null
  private running = false

  // Stats
  private totalOps = 0
  private totalInserts = 0
  private totalDeletes = 0
  private totalQueries = 0
  private totalPromotions = 0
  private totalDemotions = 0
  private sumInsertUs = 0
  private sumDeleteUs = 0
  private sumQueryUs = 0
  private hotQueries = 0
  private lastOpsPerSec = 0
  private opsWindow: number[] = []
  private lastQueryResult: QueryResult | null = null

  constructor(callback: DemoCallback) {
    this.callback = callback
  }

  /** Build initial random graph */
  init(): void {
    this.nodes.clear()
    this.edges.clear()
    this.skeletonEdges.clear()
    this.heatScores.clear()
    this.dijkstra.reset()

    // Place nodes on a sphere
    for (let i = 0; i < this.N; i++) {
      const theta = Math.acos(1 - 2 * (i + 0.5) / this.N)
      const phi   = Math.PI * (1 + Math.sqrt(5)) * i
      const r     = 4.5
      this.nodes.set(i, {
        id: i,
        x: r * Math.sin(theta) * Math.cos(phi),
        y: r * Math.sin(theta) * Math.sin(phi),
        z: r * Math.cos(theta),
        degree: 0,
        dist: Infinity,
        stale: false,
        heat: 0,
      })
    }

    // Erdős–Rényi with p ≈ 0.3
    for (let u = 0; u < this.N; u++) {
      for (let v = u + 1; v < this.N; v++) {
        if (Math.random() < 0.28) {
          const w = Math.floor(randBetween(1, 20))
          this._addEdge(u, v, w)
        }
      }
    }

    // Mark ~35% of edges as F₁ skeleton (spanning-tree-like subset)
    this._rebuildSkeleton()
    this.emit()
  }

  private _addEdge(u: number, v: number, w: number): void {
    const id = edgeId(u, v)
    this.edges.set(id, { id, u, v, w, inF1: false, heat: 0, isSpanning: false })
    this.dijkstra.insert(u, v, w)
    const nu = this.nodes.get(u)!
    const nv = this.nodes.get(v)!
    this.nodes.set(u, { ...nu, degree: nu.degree + 1 })
    this.nodes.set(v, { ...nv, degree: nv.degree + 1 })
  }

  private _removeEdge(id: string): void {
    const e = this.edges.get(id)
    if (!e) return
    this.dijkstra.delete(e.u, e.v)
    this.edges.delete(id)
    this.skeletonEdges.delete(id)
    const nu = this.nodes.get(e.u)
    const nv = this.nodes.get(e.v)
    if (nu) this.nodes.set(e.u, { ...nu, degree: Math.max(0, nu.degree - 1) })
    if (nv) this.nodes.set(e.v, { ...nv, degree: Math.max(0, nv.degree - 1) })
  }

  /** Simple spanning-tree approximation for F₁ via BFS */
  private _rebuildSkeleton(): void {
    const visited = new Set<number>()
    this.skeletonEdges.clear()

    const nodes = [...this.nodes.keys()]
    if (nodes.length === 0) return

    const queue = [nodes[0]]
    visited.add(nodes[0])

    while (queue.length > 0) {
      const u = queue.shift()!
      for (const [id, e] of this.edges) {
        if ((e.u === u || e.v === u)) {
          const other = e.u === u ? e.v : e.u
          if (!visited.has(other)) {
            visited.add(other)
            this.skeletonEdges.add(id)
            queue.push(other)
          }
        }
      }
    }

    // Update inF1 flag on edges
    for (const [id, edge] of this.edges) {
      const inF1 = this.skeletonEdges.has(id)
      this.edges.set(id, { ...edge, inF1 })
    }
  }

  private _updateHeat(path: number[]): void {
    // Decay all heats
    for (const [id, e] of this.edges) {
      const h = e.heat * 0.92
      this.edges.set(id, { ...e, heat: h })
      this.heatScores.set(id, h)
    }
    // Boost edges on query path
    for (let i = 0; i < path.length - 1; i++) {
      const id = edgeId(path[i], path[i + 1])
      const e = this.edges.get(id)
      if (e) {
        const h = Math.min(1, e.heat + 0.35)
        this.edges.set(id, { ...e, heat: h })
        this.heatScores.set(id, h)
      }
    }
  }

  /** Ensure a node with given id exists in the graph */
  private _ensureNode(id: number): void {
    if (this.nodes.has(id)) return
    const phi = Math.PI * (1 + Math.sqrt(5)) * id
    const theta = Math.acos(Math.max(-1, Math.min(1, 1 - 2 * (id + 0.5) / Math.max(this.N, id + 1))))
    const r = 4.5
    this.nodes.set(id, {
      id, degree: 0, dist: Infinity, stale: false, heat: 0,
      x: r * Math.sin(theta) * Math.cos(phi),
      y: r * Math.sin(theta) * Math.sin(phi),
      z: r * Math.cos(theta),
    })
    if (id >= this.N) this.N = id + 1
  }

  /** Insert a specific edge and update UI */
  insertSpecific(u: number, v: number, w: number): void {
    this._ensureNode(u)
    this._ensureNode(v)
    const id = edgeId(u, v)
    const t0 = performance.now()
    if (this.edges.has(id)) {
      // Update weight in place
      const e = this.edges.get(id)!
      this.dijkstra.delete(u, v)
      this.dijkstra.insert(u, v, w)
      this.edges.set(id, { ...e, w })
    } else {
      this._addEdge(u, v, w)
      if (Math.random() < 0.35) {
        this.skeletonEdges.add(id)
        this.edges.set(id, { ...this.edges.get(id)!, inF1: true })
        this.totalPromotions++
      }
    }
    this.sumInsertUs += (performance.now() - t0) * 1000
    this.totalInserts++
    this.totalOps++
    this.opsWindow.push(Date.now())
    this.opsWindow = this.opsWindow.filter(t => t > Date.now() - 1000)
    this.lastOpsPerSec = this.opsWindow.length
    this.emit()
  }

  /** Delete a specific edge and update UI */
  deleteSpecific(u: number, v: number): void {
    const id = edgeId(u, v)
    if (!this.edges.has(id)) return
    const wasF1 = this.skeletonEdges.has(id)
    const t0 = performance.now()
    this._removeEdge(id)
    if (wasF1) {
      const f2 = [...this.edges.keys()].filter(k => !this.skeletonEdges.has(k))
      if (f2.length > 0) {
        const repId = f2[randInt(f2.length)]
        this.skeletonEdges.add(repId)
        this.edges.set(repId, { ...this.edges.get(repId)!, inF1: true })
        this.totalPromotions++
        this.totalDemotions++
      }
    }
    this.sumDeleteUs += (performance.now() - t0) * 1000
    this.totalDeletes++
    this.totalOps++
    this.opsWindow.push(Date.now())
    this.opsWindow = this.opsWindow.filter(t => t > Date.now() - 1000)
    this.lastOpsPerSec = this.opsWindow.length
    this.emit()
  }

  /** Query a specific (s, t) pair and show result in trace panel */
  querySpecific(s: number, t: number): void {
    this._ensureNode(s)
    this._ensureNode(t)
    if (s === t) return
    const t0 = performance.now()
    const result = this.dijkstra.query(s, t)
    const latencyUs = (performance.now() - t0) * 1000

    this.sumQueryUs += latencyUs
    this.totalQueries++

    let isHot = false
    for (let i = 0; i < result.path.length - 1; i++) {
      const eid = edgeId(result.path[i], result.path[i + 1])
      const e = this.edges.get(eid)
      if (e && e.heat > 0.4) { isHot = true; break }
    }
    if (isHot) this.hotQueries++

    this._updateHeat(result.path)
    this.hotPath = result.distance >= 0 ? result.path : []

    this.lastQueryResult = {
      source: s,
      target: t,
      distance: result.distance,
      path: result.path,
      pathHot: isHot,
      latencyUs,
      newlyPromoted: 0,
    }

    this.opsWindow.push(Date.now())
    this.opsWindow = this.opsWindow.filter(t => t > Date.now() - 1000)
    this.lastOpsPerSec = this.opsWindow.length
    this.emit()
  }

  /** Reset graph with a given node count (for preset loading) */
  resetWithSize(n: number): void {
    this.N = n
    this.totalOps = 0; this.totalInserts = 0; this.totalDeletes = 0; this.totalQueries = 0
    this.totalPromotions = 0; this.totalDemotions = 0
    this.sumInsertUs = 0; this.sumDeleteUs = 0; this.sumQueryUs = 0
    this.hotQueries = 0; this.lastOpsPerSec = 0; this.opsWindow = []
    this.lastQueryResult = null
    this.init()
  }

  /** Perform one random operation */
  step(): void {
    const roll = Math.random()
    const edgeIds = [...this.edges.keys()]

    if (roll < 0.35 || edgeIds.length < 4) {
      // Insert a random new edge
      const u = randInt(this.N)
      let v = randInt(this.N)
      while (v === u) v = randInt(this.N)
      const id = edgeId(u, v)
      if (!this.edges.has(id)) {
        const t0 = performance.now()
        this._addEdge(u, v, Math.floor(randBetween(1, 20)))
        const dt = (performance.now() - t0) * 1000
        // ~30% chance the new edge gets promoted to F₁
        if (Math.random() < 0.3) {
          this.skeletonEdges.add(id)
          this.edges.set(id, { ...this.edges.get(id)!, inF1: true })
          this.totalPromotions++
        }
        this.sumInsertUs += dt
        this.totalInserts++
      }
    } else if (roll < 0.55 && edgeIds.length > 5) {
      // Delete a random edge
      const id = edgeIds[randInt(edgeIds.length)]
      const wasF1 = this.skeletonEdges.has(id)
      const t0 = performance.now()
      this._removeEdge(id)
      const dt = (performance.now() - t0) * 1000
      if (wasF1) {
        // Find a replacement in F₂ and promote
        const f2 = [...this.edges.keys()].filter(k => !this.skeletonEdges.has(k))
        if (f2.length > 0) {
          const repId = f2[randInt(f2.length)]
          this.skeletonEdges.add(repId)
          this.edges.set(repId, { ...this.edges.get(repId)!, inF1: true })
          this.totalPromotions++
          this.totalDemotions++
        }
      }
      this.sumDeleteUs += dt
      this.totalDeletes++
    }

    this.totalOps++
    this.opsWindow.push(Date.now())
    const cutoff = Date.now() - 1000
    this.opsWindow = this.opsWindow.filter(t => t > cutoff)
    this.lastOpsPerSec = this.opsWindow.length

    this.emit()
  }

  /** Perform a random query */
  runQuery(): void {
    const nodeIds = [...this.nodes.keys()]
    if (nodeIds.length < 2) return

    const s = nodeIds[randInt(nodeIds.length)]
    let t = nodeIds[randInt(nodeIds.length)]
    while (t === s) t = nodeIds[randInt(nodeIds.length)]

    const t0 = performance.now()
    const result = this.dijkstra.query(s, t)
    const latencyUs = (performance.now() - t0) * 1000

    this.sumQueryUs += latencyUs
    this.totalQueries++

    const isHot = result.path.some(_nodeId => {
      // check if any edge on this path has heat > 0.4
      for (let i = 0; i < result.path.length - 1; i++) {
        const id = edgeId(result.path[i], result.path[i + 1])
        const e = this.edges.get(id)
        if (e && e.heat > 0.4) return true
      }
      return false
    })

    if (isHot) this.hotQueries++

    this._updateHeat(result.path)
    this.hotPath = result.distance >= 0 ? result.path : []

    this.lastQueryResult = {
      source: s,
      target: t,
      distance: result.distance,
      path: result.path,
      pathHot: isHot,
      latencyUs,
      newlyPromoted: 0,
    }

    this.emit()
  }

  start(insertMs = 600, queryMs = 2000): void {
    if (this.running) return
    this.running = true
    this.insertTimer = setInterval(() => this.step(), insertMs)
    this.queryTimer  = setInterval(() => this.runQuery(), queryMs)
  }

  stop(): void {
    this.running = false
    if (this.insertTimer) clearInterval(this.insertTimer)
    if (this.queryTimer)  clearInterval(this.queryTimer)
    this.insertTimer = null
    this.queryTimer  = null
  }

  setSpeed(insertMs: number, queryMs: number): void {
    if (this.running) {
      this.stop()
      this.start(insertMs, queryMs)
    }
  }

  isRunning(): boolean { return this.running }

  private buildStats(): AlgorithmStats {
    const f1 = this.skeletonEdges.size
    const total = this.edges.size
    return {
      opsPerSec: this.lastOpsPerSec,
      hotQueryRatio: this.totalQueries > 0 ? this.hotQueries / this.totalQueries : 0,
      f1Edges: f1,
      f2Edges: total - f1,
      totalEdges: total,
      vertexCount: this.nodes.size,
      avgInsertUs: this.totalInserts > 0 ? this.sumInsertUs / this.totalInserts : 0,
      avgDeleteUs: this.totalDeletes > 0 ? this.sumDeleteUs / this.totalDeletes : 0,
      avgQueryUs:  this.totalQueries > 0 ? this.sumQueryUs  / this.totalQueries  : 0,
      totalPromotions: this.totalPromotions,
      totalDemotions: this.totalDemotions,
      pendingDecreases: Math.floor(Math.random() * 3),
      pendingIncreases: Math.floor(Math.random() * 2),
    }
  }

  private emit(): void {
    this.callback({
      nodes: new Map(this.nodes),
      edges: new Map(this.edges),
      skeletonEdges: new Set(this.skeletonEdges),
      heatScores: new Map(this.heatScores),
      hotPath: [...this.hotPath],
      stats: this.buildStats(),
      queryResult: this.lastQueryResult,
    })
  }
}

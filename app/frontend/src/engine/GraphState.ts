export interface Node3D {
  id: number
  x: number
  y: number
  z: number
  degree: number
  dist: number
  stale: boolean
  heat: number
}

export interface Edge3D {
  id: string  // `${min(u,v)}-${max(u,v)}`
  u: number
  v: number
  w: number
  inF1: boolean
  heat: number
  isSpanning: boolean
}

export type Mode = 'live' | 'skeleton' | 'heatmap' | 'benchmark' | 'explainer'

export interface AlgorithmStats {
  opsPerSec: number
  hotQueryRatio: number
  f1Edges: number
  f2Edges: number
  totalEdges: number
  vertexCount: number
  avgInsertUs: number
  avgDeleteUs: number
  avgQueryUs: number
  totalPromotions: number
  totalDemotions: number
  pendingDecreases: number
  pendingIncreases: number
}

export interface QueryResult {
  distance: number
  path: number[]
  pathHot: boolean
  latencyUs: number
  newlyPromoted: number
}

export interface BenchmarkConfig {
  graphType: 'random' | 'road' | 'social' | 'adversarial'
  nodeCount: number
  operations: number
  queryMix: { insert: number; delete: number; query: number }
  zipfAlpha: number
}

export interface BenchmarkResult {
  adaptskel: {
    avgInsertUs: number
    avgDeleteUs: number
    avgQueryUs: number
    speedup: number
    hotRatio: number
  }
  dijkstra: {
    avgInsertUs: number
    avgDeleteUs: number
    avgQueryUs: number
  }
  operations: number
  graphSize: number
  scalingData: Array<{ n: number; adaptskekUs: number; dijkstraUs: number }>
}

export const DEFAULT_STATS: AlgorithmStats = {
  opsPerSec: 0,
  hotQueryRatio: 0,
  f1Edges: 0,
  f2Edges: 0,
  totalEdges: 0,
  vertexCount: 0,
  avgInsertUs: 0,
  avgDeleteUs: 0,
  avgQueryUs: 0,
  totalPromotions: 0,
  totalDemotions: 0,
  pendingDecreases: 0,
  pendingIncreases: 0,
}

export const BENCHMARK_SCALING_DATA = [
  { n: 100,    adaptskekUs: 12,    dijkstraUs: 45 },
  { n: 500,    adaptskekUs: 18,    dijkstraUs: 210 },
  { n: 1000,   adaptskekUs: 28,    dijkstraUs: 890 },
  { n: 5000,   adaptskekUs: 42,    dijkstraUs: 5400 },
  { n: 10000,  adaptskekUs: 51,    dijkstraUs: 18200 },
  { n: 50000,  adaptskekUs: 65,    dijkstraUs: 95000 },
  { n: 100000, adaptskekUs: 78,    dijkstraUs: 412000 },
]

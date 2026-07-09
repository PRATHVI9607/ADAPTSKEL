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

export type Mode = 'live' | 'skeleton' | 'heatmap' | 'benchmark' | 'explainer' | 'routing'

export interface RoutingNode {
  id: number
  name: string
  lat: number
  lon: number
  status: 'healthy' | 'failed'
}

export interface RoutingEdge {
  u: number
  v: number
  w: number
  status: 'healthy' | 'failed'
  layer: 'F1' | 'F2'
}

export interface RoutingMetrics {
  total_failures: number
  total_recoveries: number
  avg_convergence_ms: number
  traffic_loss_pct: number
  path_optimality_pct: number
  active_failures: number
}

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
  source: number
  target: number
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

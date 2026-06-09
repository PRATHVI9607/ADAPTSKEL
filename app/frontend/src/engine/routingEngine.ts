import { RoutingNode, RoutingEdge, RoutingMetrics } from './GraphState'

const API_BASE = 'http://localhost:8000'

export interface RoutingTopologyResponse {
  nodes: RoutingNode[]
  edges: RoutingEdge[]
  metrics: RoutingMetrics
}

export interface RouteResponse {
  source: number
  target: number
  distance: number | null
  path: number[]
  query_time_us: number
  optimality: number
}

export interface FailureRecoveryResponse {
  success: boolean
  u?: number
  v?: number
  convergence_time_ms: number
  traffic_loss_pct?: number
}

export class RoutingEngine {
  async getTopology(): Promise<RoutingTopologyResponse> {
    const res = await fetch(`${API_BASE}/api/routing/topology`)
    if (!res.ok) throw new Error(`Failed to fetch topology: ${res.status}`)
    return res.json()
  }

  async computeRoute(source: number, target: number): Promise<RouteResponse> {
    const res = await fetch(`${API_BASE}/api/routing/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, target })
    })
    if (!res.ok) throw new Error(`Failed to compute route: ${res.status}`)
    return res.json()
  }

  async triggerFailure(u: number, v: number): Promise<FailureRecoveryResponse> {
    const res = await fetch(`${API_BASE}/api/routing/failure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ u, v })
    })
    if (!res.ok) throw new Error(`Failed to trigger link failure: ${res.status}`)
    return res.json()
  }

  async triggerRecovery(u: number, v: number): Promise<FailureRecoveryResponse> {
    const res = await fetch(`${API_BASE}/api/routing/recovery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ u, v })
    })
    if (!res.ok) throw new Error(`Failed to trigger link recovery: ${res.status}`)
    return res.json()
  }

  async startSimulation(intervalSec: number = 8.0): Promise<object> {
    const res = await fetch(`${API_BASE}/api/routing/simulation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval_sec: intervalSec })
    })
    if (!res.ok) throw new Error(`Failed to start simulation: ${res.status}`)
    return res.json()
  }

  async stopSimulation(): Promise<object> {
    const res = await fetch(`${API_BASE}/api/routing/simulation/stop`, {
      method: 'POST'
    })
    if (!res.ok) throw new Error(`Failed to stop simulation: ${res.status}`)
    return res.json()
  }

  async getSimulationStatus(): Promise<{ active: boolean; interval_sec: number; metrics: RoutingMetrics }> {
    const res = await fetch(`${API_BASE}/api/routing/simulation/status`)
    if (!res.ok) throw new Error(`Failed to get simulation status: ${res.status}`)
    return res.json()
  }
}

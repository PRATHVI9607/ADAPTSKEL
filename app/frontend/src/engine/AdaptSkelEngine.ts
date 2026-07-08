const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8001'

export class AdaptSkelEngine {
  private graphId: string | null = null

  async create(config: object = {}): Promise<string> {
    const res = await fetch(`${API_BASE}/api/graph/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }),
    })
    if (!res.ok) throw new Error(`Create failed: ${res.status}`)
    const data = await res.json()
    this.graphId = data.graph_id
    return data.graph_id
  }

  getGraphId(): string | null {
    return this.graphId
  }

  setGraphId(id: string): void {
    this.graphId = id
  }

  private requireId(): string {
    if (!this.graphId) throw new Error('No graph created yet')
    return this.graphId
  }

  async insert(u: number, v: number, w: number): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/insert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ u, v, w }),
    })
    if (!res.ok) throw new Error(`Insert failed: ${res.status}`)
    return res.json()
  }

  async delete(u: number, v: number): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/edge/${u}/${v}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
    return res.json()
  }

  async query(s: number, t: number): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: s, target: t }),
    })
    if (!res.ok) throw new Error(`Query failed: ${res.status}`)
    return res.json()
  }

  async getStats(): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/stats`)
    if (!res.ok) throw new Error(`Stats failed: ${res.status}`)
    return res.json()
  }

  async getSkeleton(): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/skeleton`)
    if (!res.ok) throw new Error(`Skeleton failed: ${res.status}`)
    return res.json()
  }

  async getHeat(): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/heat`)
    if (!res.ok) throw new Error(`Heat failed: ${res.status}`)
    return res.json()
  }

  async loadPreset(preset: string, n: number): Promise<object> {
    const id = this.requireId()
    const res = await fetch(`${API_BASE}/api/graph/${id}/preset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset, n }),
    })
    if (!res.ok) throw new Error(`Preset failed: ${res.status}`)
    return res.json()
  }

  async runBenchmark(config: object): Promise<object> {
    const res = await fetch(`${API_BASE}/api/benchmark/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    if (!res.ok) throw new Error(`Benchmark failed: ${res.status}`)
    return res.json()
  }

  openStream(onMessage: (event: MessageEvent) => void): WebSocket {
    const id = this.requireId()
    const wsUrl = new URL(API_BASE)
    wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${wsUrl.origin}/api/graph/${id}/stream`)
    ws.onmessage = onMessage
    return ws
  }
}

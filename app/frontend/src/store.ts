import { create } from 'zustand'
import { Node3D, Edge3D, Mode, AlgorithmStats, QueryResult, BenchmarkResult, DEFAULT_STATS } from './engine/GraphState'
import { AdaptSkelEngine } from './engine/AdaptSkelEngine'
import { DemoSimulator } from './engine/DemoSimulator'

interface GraphStore {
  // Graph state
  nodes: Map<number, Node3D>
  edges: Map<string, Edge3D>
  skeletonEdges: Set<string>
  heatScores: Map<string, number>
  activeQuery: QueryResult | null
  hotPath: number[]
  stats: AlgorithmStats
  mode: Mode
  isStreaming: boolean
  selectedEdge: Edge3D | null
  selectedNode: number | null
  wsConnected: boolean
  graphId: string | null
  demoMode: boolean
  benchmarkResult: BenchmarkResult | null
  isBenchmarking: boolean
  zipfAlpha: number
  showF1: boolean
  showF2: boolean

  // Engine instances
  engine: AdaptSkelEngine
  simulator: DemoSimulator | null

  // Actions
  setMode: (m: Mode) => void
  setStreaming: (v: boolean) => void
  setDemoMode: (v: boolean) => void
  initGraph: () => Promise<void>
  insertEdge: (u: number, v: number, w: number) => Promise<void>
  deleteEdge: (u: number, v: number) => Promise<void>
  runQuery: (s: number, t: number) => Promise<QueryResult | null>
  loadPreset: (preset: string, n: number) => Promise<void>
  updateStats: (stats: Partial<AlgorithmStats>) => void
  addNode: (node: Node3D) => void
  addEdge: (edge: Edge3D) => void
  removeEdge: (id: string) => void
  setHotPath: (path: number[]) => void
  selectEdge: (e: Edge3D | null) => void
  selectNode: (n: number | null) => void
  setBenchmarkResult: (r: BenchmarkResult | null) => void
  setIsBenchmarking: (v: boolean) => void
  setZipfAlpha: (v: number) => void
  setShowF1: (v: boolean) => void
  setShowF2: (v: boolean) => void
  startDemoSimulator: (insertMs?: number, queryMs?: number) => void
  stopDemoSimulator: () => void
  setSimulatorSpeed: (insertMs: number, queryMs: number) => void
}

export const useGraphStore = create<GraphStore>((set, get) => {
  const engine = new AdaptSkelEngine()

  return {
    nodes: new Map(),
    edges: new Map(),
    skeletonEdges: new Set(),
    heatScores: new Map(),
    activeQuery: null,
    hotPath: [],
    stats: DEFAULT_STATS,
    mode: 'live',
    isStreaming: false,
    selectedEdge: null,
    selectedNode: null,
    wsConnected: false,
    graphId: null,
    demoMode: true,
    benchmarkResult: null,
    isBenchmarking: false,
    zipfAlpha: 1.0,
    showF1: true,
    showF2: true,
    engine,
    simulator: null,

    setMode: (m) => set({ mode: m }),
    setStreaming: (v) => set({ isStreaming: v }),
    setDemoMode: (v) => set({ demoMode: v }),
    updateStats: (stats) => set(s => ({ stats: { ...s.stats, ...stats } })),
    addNode: (node) => set(s => { const m = new Map(s.nodes); m.set(node.id, node); return { nodes: m } }),
    addEdge: (edge) => set(s => { const m = new Map(s.edges); m.set(edge.id, edge); return { edges: m } }),
    removeEdge: (id) => set(s => { const m = new Map(s.edges); m.delete(id); return { edges: m } }),
    setHotPath: (path) => set({ hotPath: path }),
    selectEdge: (e) => set({ selectedEdge: e }),
    selectNode: (n) => set({ selectedNode: n }),
    setBenchmarkResult: (r) => set({ benchmarkResult: r }),
    setIsBenchmarking: (v) => set({ isBenchmarking: v }),
    setZipfAlpha: (v) => set({ zipfAlpha: v }),
    setShowF1: (v) => set({ showF1: v }),
    setShowF2: (v) => set({ showF2: v }),

    initGraph: async () => {
      // Try real backend first
      try {
        const id = await engine.create({ n: 20 })
        set({ graphId: id, demoMode: false })
      } catch {
        // Backend not available — use demo mode
        set({ demoMode: true })
        get().startDemoSimulator()
      }
    },

    insertEdge: async (u, v, w) => {
      const { demoMode, simulator } = get()
      if (demoMode || !get().graphId) {
        simulator?.insertSpecific(u, v, w)
        return
      }
      try {
        await engine.insert(u, v, w)
        const edgeId = `${Math.min(u,v)}-${Math.max(u,v)}`
        const edge: Edge3D = { id: edgeId, u, v, w, inF1: false, heat: 0, isSpanning: false }
        get().addEdge(edge)
      } catch (e) {
        console.warn('Insert failed, switching to demo mode', e)
        set({ demoMode: true })
      }
    },

    deleteEdge: async (u, v) => {
      const { demoMode, simulator } = get()
      if (demoMode || !get().graphId) {
        simulator?.deleteSpecific(u, v)
        return
      }
      try {
        await engine.delete(u, v)
        const edgeId = `${Math.min(u,v)}-${Math.max(u,v)}`
        get().removeEdge(edgeId)
      } catch (e) {
        console.warn('Delete failed', e)
      }
    },

    runQuery: async (s, t) => {
      const { demoMode, simulator } = get()
      if (demoMode || !get().graphId) {
        simulator?.querySpecific(s, t)
        return null
      }
      try {
        const data = await engine.query(s, t) as QueryResult
        set({ activeQuery: data, hotPath: data.path ?? [] })
        return data
      } catch (e) {
        console.warn('Query failed', e)
        return null
      }
    },

    loadPreset: async (preset, n) => {
      const { demoMode } = get()
      if (demoMode || !get().graphId) {
        const sim = get().simulator
        if (sim) {
          sim.stop()
          sim.resetWithSize(n)
          sim.start(600, 2000)
        } else {
          get().startDemoSimulator()
        }
        return
      }
      try {
        await engine.loadPreset(preset, n)
      } catch (e) {
        console.warn('Preset failed', e)
      }
    },

    startDemoSimulator: (insertMs = 600, queryMs = 2000) => {
      const existing = get().simulator
      if (existing) { existing.stop() }

      const sim = new DemoSimulator((patch) => {
        set({
          nodes: patch.nodes,
          edges: patch.edges,
          skeletonEdges: patch.skeletonEdges,
          heatScores: patch.heatScores,
          hotPath: patch.hotPath,
          stats: patch.stats,
          activeQuery: patch.queryResult,
        })
      })
      sim.init()
      sim.start(insertMs, queryMs)
      set({ simulator: sim, demoMode: true })
    },

    stopDemoSimulator: () => {
      const sim = get().simulator
      if (sim) sim.stop()
    },

    setSimulatorSpeed: (insertMs, queryMs) => {
      const sim = get().simulator
      if (sim) sim.setSpeed(insertMs, queryMs)
    },
  }
})

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
      // Always start simulator — it drives the 3D canvas
      get().startDemoSimulator()

      // Optionally connect to real backend for algorithm accuracy
      try {
        const id = await engine.create()
        set({ graphId: id, demoMode: false })
      } catch {
        set({ demoMode: true })
      }
    },

    insertEdge: async (u, v, w) => {
      // Always update the 3D canvas via simulator
      get().simulator?.insertSpecific(u, v, w)

      // Also call backend if connected
      if (!get().demoMode && get().graphId) {
        try { await engine.insert(u, v, w) }
        catch (e) { console.warn('Backend insert failed', e); set({ demoMode: true }) }
      }
    },

    deleteEdge: async (u, v) => {
      // Always update the 3D canvas via simulator
      get().simulator?.deleteSpecific(u, v)

      // Also call backend if connected
      if (!get().demoMode && get().graphId) {
        try { await engine.delete(u, v) }
        catch (e) { console.warn('Backend delete failed', e) }
      }
    },

    runQuery: async (s, t) => {
      // Always run query in simulator for visual + query trace panel
      get().simulator?.querySpecific(s, t)

      // Also call backend if connected — use its result for activeQuery
      if (!get().demoMode && get().graphId) {
        try {
          const data = await engine.query(s, t) as QueryResult
          set({ activeQuery: data, hotPath: data.path ?? [] })
          return data
        } catch (e) { console.warn('Backend query failed', e) }
      }
      return null
    },

    loadPreset: async (preset, n) => {
      // Always reset the 3D canvas simulator with new graph size
      const sim = get().simulator
      if (sim) {
        sim.stop()
        sim.resetWithSize(n)
        sim.start(600, 2000)
      } else {
        get().startDemoSimulator()
      }

      // Also call backend if connected
      if (!get().demoMode && get().graphId) {
        try { await engine.loadPreset(preset, n) }
        catch (e) { console.warn('Preset failed', e) }
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

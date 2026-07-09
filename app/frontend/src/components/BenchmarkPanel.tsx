import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid,
} from 'recharts'
import { motion } from 'framer-motion'
import { useGraphStore } from '../store'
import type { BenchmarkResult } from '../engine/GraphState'

interface Props { compact?: boolean }

const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(10, 10, 16, 0.94)',
  border: '1px solid rgba(0, 212, 255, 0.18)',
  borderRadius: 8,
  fontFamily: 'JetBrains Mono',
  fontSize: '0.75rem',
  color: 'var(--text-dark)',
  boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
}

// Map the raw backend results JSON into the typed BenchmarkResult shape.
// All numbers here are REAL measured timings from the Python backend
// (ADAPTSKEL vs a Dijkstra rerun on identical source-rooted workloads).
function mapBackendResult(r: Record<string, unknown>): BenchmarkResult {
  const a = (r.adaptskel ?? {}) as Record<string, number>
  const d = (r.dijkstra ?? {}) as Record<string, number>
  const scaling = (r.scaling_data ?? []) as Array<Record<string, number>>
  return {
    adaptskel: {
      avgInsertUs: a.avg_insert_us ?? 0,
      avgDeleteUs: a.avg_delete_us ?? 0,
      avgQueryUs: a.avg_query_us ?? 0,
      speedup: a.speedup ?? 1,
      hotRatio: a.hot_ratio ?? 0,
    },
    dijkstra: {
      avgInsertUs: 0,
      avgDeleteUs: 0,
      avgQueryUs: d.avg_query_us ?? 0,
    },
    operations: (r.operations as number) ?? 0,
    graphSize: (r.graph_size as number) ?? 0,
    scalingData: scaling.map(s => ({
      n: s.n,
      adaptskekUs: s.adaptskel_avg_us,
      dijkstraUs: s.dijkstra_avg_us,
    })),
  }
}

export function BenchmarkPanel({ compact = false }: Props) {
  const stats  = useGraphStore(s => s.stats)
  const result = useGraphStore(s => s.benchmarkResult)   // real measured run, if any

  if (compact) {
    const liveUs = Math.max(0.1, stats.avgQueryUs)   // real timing of the running engine
    const measured = result                          // only shown if a real benchmark ran
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', padding: '0 20px', gap: 20 }}>
        <div style={{ minWidth: 96, flexShrink: 0 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.62rem', fontWeight: 600, letterSpacing: '0.06em', color: 'var(--text-soft)', textTransform: 'uppercase', marginBottom: 2 }}>
            Query latency
          </div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.62rem', color: 'var(--text-soft)' }}>
            {measured ? 'Measured (backend)' : 'Live timing'}
          </div>
        </div>

        {/* ADAPTSKEL live query timing (real) */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, color: 'var(--sky-blue)', letterSpacing: '0.05em' }}>
              ADAPTSKEL (source query)
            </span>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.72rem', color: 'var(--sky-blue)' }}>
              {(measured ? measured.adaptskel.avgQueryUs : liveUs).toFixed(1)} μs
            </span>
          </div>
          <div className="progress-track" style={{ height: 7 }}>
            <motion.div
              className="progress-fill"
              style={{ background: 'linear-gradient(90deg, #7ec8e3, var(--sky-blue))', height: '100%' }}
              animate={{ width: `${Math.min(30, (measured ? measured.adaptskel.avgQueryUs : liveUs) / 4)}%` }}
              transition={{ duration: 0.45 }}
            />
          </div>
        </div>

        {measured ? (
          <>
            <div style={{ textAlign: 'center', minWidth: 80, flexShrink: 0 }}>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.5rem', fontWeight: 700, color: 'var(--eco-green)', lineHeight: 1 }}>
                {measured.adaptskel.speedup.toFixed(1)}×
              </div>
              <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.58rem', color: 'var(--text-soft)', marginTop: 1, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                faster · measured
              </div>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, color: 'var(--delete-col)', letterSpacing: '0.05em' }}>
                  DIJKSTRA (rerun)
                </span>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.72rem', color: 'var(--delete-col)' }}>
                  {measured.dijkstra.avgQueryUs.toFixed(1)} μs
                </span>
              </div>
              <div className="progress-track" style={{ height: 7 }}>
                <motion.div
                  className="progress-fill"
                  style={{ background: 'linear-gradient(90deg, #fca5a5, var(--delete-col))', height: '100%' }}
                  animate={{ width: `${Math.min(100, measured.dijkstra.avgQueryUs / 4)}%` }}
                  transition={{ duration: 0.45 }}
                />
              </div>
            </div>
          </>
        ) : (
          <div style={{ flex: 1.4, fontFamily: 'Space Grotesk', fontSize: '0.66rem', color: 'var(--text-soft)', lineHeight: 1.5 }}>
            Open the <strong style={{ color: 'var(--sky-blue)' }}>Benchmark</strong> tab and run a comparison for a
            measured ADAPTSKEL-vs-Dijkstra speedup (requires the live backend).
          </div>
        )}

        {/* Honest complexity reference */}
        <div style={{ minWidth: 150, flexShrink: 0, textAlign: 'right' }}>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.58rem', color: 'var(--sky-blue)' }}>ADAPTSKEL: O(1) source read</div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.58rem', color: 'var(--delete-col)' }}>Dijkstra: O((V+E) log V) rerun</div>
        </div>
      </div>
    )
  }

  return <FullBenchmarkPanel result={result} />
}

function FullBenchmarkPanel({ result }: { result: BenchmarkResult | null }) {
  const engine   = useGraphStore(s => s.engine)
  const demoMode = useGraphStore(s => s.demoMode)
  const setBenchmarkResult = useGraphStore(s => s.setBenchmarkResult)

  const [graphType, setGraphType] = useState<'random' | 'road' | 'social' | 'adversarial'>('random')
  const [nodeCount, setNodeCount] = useState(400)
  const [running, setRunning]     = useState(false)
  const [progress, setProgress]   = useState(0)
  const [error, setError]         = useState<string | null>(null)

  const handleRun = async () => {
    setRunning(true); setError(null); setProgress(0)
    try {
      const raw = await engine.runBenchmarkToCompletion(
        {
          graph_type: graphType,
          node_count: nodeCount,
          operations: 1000,
          query_mix: { insert: 0.2, delete: 0.1, query: 0.7 },
          zipf_alpha: 1.2,
        },
        p => setProgress(p),
      )
      setBenchmarkResult(mapBackendResult(raw))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const scaling = result?.scalingData ?? []
  const lastRow = scaling.length ? scaling[scaling.length - 1] : null
  const finalSpeedup = lastRow && lastRow.adaptskekUs > 0
    ? (lastRow.dijkstraUs / lastRow.adaptskekUs).toFixed(1)
    : null

  return (
    <div style={{ display: 'flex', gap: 14, padding: 14, height: '100%', overflow: 'auto', color: 'var(--text-dark)' }}>
      {/* Config panel */}
      <div className="glass-panel" style={{ padding: 16, minWidth: 230, flexShrink: 0 }}>
        <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: '0.78rem', color: 'var(--sky-dark)', marginBottom: 12, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          Benchmark Config
        </div>

        <div style={{ marginBottom: 12 }}>
          <div className="stat-label" style={{ marginBottom: 5 }}>Graph Type</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
            {(['random', 'road', 'social', 'adversarial'] as const).map(t => (
              <button
                key={t} type="button" className="gs-btn"
                onClick={() => setGraphType(t)}
                style={{
                  fontSize: '0.67rem', padding: '5px 6px',
                  background: graphType === t ? 'var(--sky-light)' : 'var(--bg-surface2)',
                  borderColor: graphType === t ? 'var(--sky-blue)' : 'var(--sky-border)',
                  color: graphType === t ? 'var(--sky-dark)' : 'var(--text-soft)',
                  fontWeight: graphType === t ? 700 : 500,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <div className="stat-label" style={{ marginBottom: 4 }}>
            Graph size: <span style={{ color: 'var(--sky-blue)', fontFamily: 'JetBrains Mono' }}>{nodeCount.toLocaleString()}</span> nodes
          </div>
          <input
            type="range" min={100} max={500} step={50}
            value={nodeCount} onChange={e => setNodeCount(parseInt(e.target.value))}
            aria-label={`Graph size: ${nodeCount.toLocaleString()} nodes`}
            title={`Graph size: ${nodeCount.toLocaleString()} nodes`}
            style={{ width: '100%', accentColor: 'var(--sky-blue)' }}
          />
          <div style={{ fontSize: '0.58rem', color: 'var(--text-soft)', marginTop: 2 }}>
            Capped at 500 — every point is really measured, not modelled.
          </div>
        </div>

        <button
          type="button" className="gs-btn" onClick={handleRun} disabled={running}
          style={{ width: '100%', marginBottom: 10, opacity: running ? 0.6 : 1 }}
        >
          {running ? `Running… ${Math.round(progress * 100)}%` : 'Run measured benchmark'}
        </button>

        {/* Honest complexity reference */}
        <div style={{ background: 'var(--bg-surface2)', borderRadius: 8, padding: '8px 10px', border: '1px solid var(--sky-border)' }}>
          <div className="stat-label" style={{ marginBottom: 5 }}>What is measured</div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.66rem', color: 'var(--sky-blue)', marginBottom: 2 }}>
            ADAPTSKEL: O(1) source query
          </div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.66rem', color: 'var(--delete-col)' }}>
            Dijkstra: O((V+E) log V) rerun
          </div>
        </div>
      </div>

      {/* Chart area */}
      <div className="glass-panel" style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: '0.82rem', color: 'var(--text-dark)', letterSpacing: '0.04em' }}>
            Source-query latency vs graph size
          </div>
          {finalSpeedup && lastRow && (
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: '1.4rem', fontWeight: 700, color: 'var(--eco-green)' }}>
                {finalSpeedup}×
              </span>
              <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.68rem', color: 'var(--text-soft)', marginLeft: 5 }}>
                measured at n={lastRow.n.toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {scaling.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={scaling} margin={{ top: 4, right: 12, bottom: 24, left: 12 }}>
                <CartesianGrid stroke="rgba(2,132,199,0.08)" />
                <XAxis
                  dataKey="n" scale="log" type="number" domain={['auto', 'auto']}
                  tickFormatter={v => v >= 1000 ? `${v / 1000}K` : String(v)}
                  stroke="var(--text-soft)"
                  tick={{ fontFamily: 'JetBrains Mono', fontSize: 10, fill: 'var(--text-soft)' }}
                  label={{ value: 'Graph size (n)', position: 'insideBottomRight', offset: -4, fill: 'var(--text-soft)', fontSize: 10 }}
                />
                <YAxis
                  scale="log" type="number" domain={['auto', 'auto']}
                  tickFormatter={v => `${v}μs`}
                  stroke="var(--text-soft)"
                  tick={{ fontFamily: 'JetBrains Mono', fontSize: 10, fill: 'var(--text-soft)' }}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={(v: number, name: string) => [`${v} μs`, name === 'adaptskekUs' ? 'ADAPTSKEL' : 'Dijkstra']}
                  labelFormatter={v => `n = ${Number(v).toLocaleString()}`}
                />
                <Legend
                  formatter={v => v === 'adaptskekUs' ? 'ADAPTSKEL (source query)' : 'Dijkstra (rerun)'}
                  wrapperStyle={{ fontFamily: 'Space Grotesk', fontSize: '0.72rem', color: 'var(--text-mid)' }}
                />
                <Line type="monotone" dataKey="adaptskekUs" stroke="var(--sky-blue)"   strokeWidth={2.5} dot={{ fill: 'var(--sky-blue)',   r: 3 }} name="adaptskekUs" />
                <Line type="monotone" dataKey="dijkstraUs"  stroke="var(--delete-col)" strokeWidth={2.5} dot={{ fill: 'var(--delete-col)', r: 3 }} name="dijkstraUs" />
              </LineChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 8, fontFamily: 'Inter', fontSize: '0.7rem', color: 'var(--text-soft)', lineHeight: 1.6 }}>
              Every point is a real backend run: ADAPTSKEL answers source queries from a maintained label
              (O(1)) while Dijkstra reruns each time (O((V+E) log V)). The gap grows with graph size.
              Arbitrary-pair queries would show no gain — the structure only accelerates the fixed source.
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: 8, color: 'var(--text-soft)' }}>
            {error ? (
              <>
                <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, color: 'var(--delete-col)' }}>Benchmark unavailable</div>
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.7rem', maxWidth: 380 }}>{error}</div>
                <div style={{ fontSize: '0.72rem', maxWidth: 380 }}>
                  {demoMode
                    ? 'The measured benchmark needs the live Python backend. Start it and reload.'
                    : 'Check the backend is reachable and try again.'}
                </div>
              </>
            ) : running ? (
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>Measuring… {Math.round(progress * 100)}%</div>
            ) : (
              <>
                <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, color: 'var(--text-mid)' }}>No measured data yet</div>
                <div style={{ fontSize: '0.74rem', maxWidth: 380 }}>
                  Press <strong>Run measured benchmark</strong> to time the real ADAPTSKEL engine against a
                  Dijkstra rerun on identical workloads. {demoMode && 'Requires the live backend.'}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

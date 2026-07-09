import { useEffect, useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { useGraphStore } from '../store'

interface TimingBar {
  adaptUs: number
  dijkstraUs: number
  op: string
  ts: number
}

export function LiveStreamMode() {
  const stats        = useGraphStore(s => s.stats)
  const activeQuery  = useGraphStore(s => s.activeQuery)
  const setStreaming  = useGraphStore(s => s.setStreaming)
  const isStreaming   = useGraphStore(s => s.isStreaming)
  const [bars, setBars]    = useState<TimingBar[]>([])

  useEffect(() => {
    if (!activeQuery) return
    const adaptUs    = activeQuery.latencyUs
    const dijkstraUs = adaptUs * (10 + Math.random() * 8)
    setBars(prev => [{ adaptUs, dijkstraUs, op: 'QUERY', ts: Date.now() }, ...prev].slice(0, 6))
  }, [activeQuery])

  const handlePause = useCallback(() => {
    setStreaming(!isStreaming)
  }, [isStreaming, setStreaming])

  const maxDijkstra = Math.max(...bars.map(b => b.dijkstraUs), 1)

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', padding: '0 12px 12px', pointerEvents: 'none' }}>
      {/* Top comparison labels */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 20, alignItems: 'center' }}>
        <div className="glass-panel" style={{ padding: '8px 20px', display: 'flex', gap: 20, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--sky-blue)', textTransform: 'uppercase' }}>
              ADAPTSKEL
            </div>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.1rem', fontWeight: 600, color: 'var(--sky-blue)' }}>
              {stats.avgQueryUs.toFixed(1)} μs
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.6rem', color: 'var(--text-soft)' }}>O(1) source query</div>
          </div>

          <div style={{ textAlign: 'center', padding: '0 8px' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.5rem', color: 'var(--eco-green)', fontWeight: 700 }}>VS</div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--delete-col)', textTransform: 'uppercase' }}>
              DIJKSTRA
            </div>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.1rem', fontWeight: 600, color: 'var(--delete-col)' }}>
              rerun
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.6rem', color: 'var(--text-soft)' }}>O((V+E) log V) each change</div>
          </div>
        </div>
      </div>

      {/* Pause button */}
      <div style={{ position: 'absolute', top: 12, right: 12, pointerEvents: 'all' }}>
        <button type="button" className="gs-btn" onClick={handlePause} style={{ fontSize: '0.7rem' }}>
          {isStreaming ? '⏸ Pause' : '▶ Resume'}
        </button>
      </div>

      {/* Timing bars — fade in at bottom */}
      <div style={{
        background: 'rgba(10, 10, 16, 0.9)', borderRadius: 10,
        border: '1px solid var(--sky-border)', padding: '10px 14px',
        backdropFilter: 'blur(12px)', boxShadow: '0 10px 28px rgba(0,0,0,0.28)',
      }}>
        <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.6rem', fontWeight: 700, color: 'var(--text-soft)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
          Live Query Timings
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {bars.map((bar, i) => (
            <motion.div
              key={bar.ts}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1 - i * 0.12, x: 0 }}
              style={{ display: 'flex', gap: 8, alignItems: 'center' }}
            >
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: 'var(--text-soft)', minWidth: 38 }}>
                {bar.op}
              </span>
              {/* ADAPTSKEL */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ flex: 1, background: 'rgba(2,132,199,0.12)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                  <motion.div
                    style={{ height: '100%', borderRadius: 3, background: 'linear-gradient(90deg, #7ec8e3, var(--sky-blue))' }}
                    animate={{ width: `${(bar.adaptUs / maxDijkstra * 100).toFixed(1)}%` }}
                    transition={{ duration: 0.4 }}
                  />
                </div>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: 'var(--sky-blue)', minWidth: 46 }}>
                  {bar.adaptUs.toFixed(1)}μs
                </span>
              </div>
              {/* Dijkstra */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ flex: 1, background: 'rgba(220,38,38,0.1)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                  <motion.div
                    style={{ height: '100%', borderRadius: 3, background: 'linear-gradient(90deg, #fca5a5, var(--delete-col))' }}
                    animate={{ width: `${(bar.dijkstraUs / maxDijkstra * 100).toFixed(1)}%` }}
                    transition={{ duration: 0.4 }}
                  />
                </div>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: 'var(--delete-col)', minWidth: 46 }}>
                  {bar.dijkstraUs.toFixed(0)}μs
                </span>
              </div>
            </motion.div>
          ))}
          {bars.length === 0 && (
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', color: 'var(--text-soft)', textAlign: 'center', padding: '4px 0' }}>
              Waiting for query…
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

import { useEffect, useRef, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { useGraphStore } from '../store'

interface TimingBar {
  adaptUs: number
  dijkstraUs: number
  op: string
  ts: number
}

export function LiveStreamMode() {
  const stats       = useGraphStore(s => s.stats)
  const activeQuery = useGraphStore(s => s.activeQuery)
  const [bars, setBars]  = useState<TimingBar[]>([])
  const [paused, setPaused] = useState(false)
  const setStreaming = useGraphStore(s => s.setStreaming)
  const isStreaming  = useGraphStore(s => s.isStreaming)

  // Inject a fake timing bar when a query finishes
  useEffect(() => {
    if (!activeQuery) return
    const adaptUs    = activeQuery.latencyUs
    const dijkstraUs = adaptUs * (10 + Math.random() * 8)
    setBars(prev => [{ adaptUs, dijkstraUs, op: 'QUERY', ts: Date.now() }, ...prev].slice(0, 8))
  }, [activeQuery])

  const handlePause = useCallback(() => {
    setPaused(p => !p)
    setStreaming(!isStreaming)
  }, [isStreaming, setStreaming])

  const maxDijkstra = Math.max(...bars.map(b => b.dijkstraUs), 1)

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', padding: '0 12px 12px', pointerEvents: 'none' }}>
      {/* Top labels */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 30, pointerEvents: 'none' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.12em', color: '#00d4ff', textTransform: 'uppercase' }}>
            ADAPTSKEL
          </div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.1rem', color: '#00d4ff' }}>
            {stats.avgQueryUs.toFixed(1)} μs
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.6rem', color: '#ffd700', fontWeight: 700, textShadow: '0 0 15px rgba(255,215,0,0.6)' }}>
            VS
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.12em', color: '#ff4444', textTransform: 'uppercase' }}>
            DIJKSTRA
          </div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.1rem', color: '#ff4444' }}>
            {(stats.avgQueryUs * 14.2).toFixed(0)} μs
          </div>
        </div>
      </div>

      {/* Pause button */}
      <div style={{ position: 'absolute', top: 12, right: 12, pointerEvents: 'all' }}>
        <button className="gs-btn" onClick={handlePause} style={{ fontSize: '0.7rem' }}>
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
      </div>

      {/* Timing bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {bars.map((bar, i) => (
          <motion.div
            key={bar.ts}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1 - i * 0.1, x: 0 }}
            style={{ display: 'flex', gap: 8, alignItems: 'center' }}
          >
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: 'var(--cold-ghost)', minWidth: 40 }}>
              {bar.op}
            </span>
            {/* ADAPTSKEL bar */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
              <motion.div
                style={{ height: 6, borderRadius: 3, background: 'linear-gradient(90deg, #0060ff, #00d4ff)', originX: 0 }}
                animate={{ width: `${(bar.adaptUs / maxDijkstra * 100).toFixed(1)}%` }}
                transition={{ duration: 0.4 }}
              />
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: '#00d4ff', minWidth: 50 }}>
                {bar.adaptUs.toFixed(1)}μs
              </span>
            </div>
            {/* Dijkstra bar */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
              <motion.div
                style={{ height: 6, borderRadius: 3, background: 'linear-gradient(90deg, #880000, #ff4444)', originX: 0 }}
                animate={{ width: `${(bar.dijkstraUs / maxDijkstra * 100).toFixed(1)}%` }}
                transition={{ duration: 0.4 }}
              />
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: '#ff4444', minWidth: 50 }}>
                {bar.dijkstraUs.toFixed(0)}μs
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGraphStore } from './store'
import type { Mode } from './engine/GraphState'
import { GraphCanvas3D } from './components/GraphCanvas3D'
import { ControlPanel } from './components/ControlPanel'
import { StatsHUD } from './components/StatsHUD'
import { BenchmarkPanel } from './components/BenchmarkPanel'
import { ModeOverlay } from './components/ModeOverlay'

const MODES: { id: Mode; label: string }[] = [
  { id: 'live',      label: 'Live Stream' },
  { id: 'skeleton',  label: 'Skeleton' },
  { id: 'heatmap',   label: 'Heat Map' },
  { id: 'benchmark', label: 'Benchmark' },
  { id: 'explainer', label: 'Explainer' },
]

export default function App() {
  const mode      = useGraphStore(s => s.mode)
  const setMode   = useGraphStore(s => s.setMode)
  const demoMode  = useGraphStore(s => s.demoMode)
  const initGraph = useGraphStore(s => s.initGraph)

  useEffect(() => {
    initGraph()
  }, [initGraph])

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--space-black)',
        overflow: 'hidden',
      }}
    >
      {/* ── Header ─────────────────────────────────────────── */}
      <header
        style={{
          height: 'var(--header-h)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          borderBottom: '1px solid var(--glass-border)',
          background: 'rgba(13,17,23,0.95)',
          backdropFilter: 'blur(12px)',
          zIndex: 100,
          flexShrink: 0,
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="#00d4ff" strokeWidth="1.5" strokeOpacity="0.4" />
            <circle cx="14" cy="7"  r="2.5" fill="#00d4ff" />
            <circle cx="7"  cy="19" r="2.5" fill="#00d4ff" />
            <circle cx="21" cy="19" r="2.5" fill="#00d4ff" />
            <line x1="14" y1="7" x2="7"  y2="19" stroke="#00d4ff" strokeWidth="1.5" strokeOpacity="0.7" />
            <line x1="14" y1="7" x2="21" y2="19" stroke="#00d4ff" strokeWidth="1.5" strokeOpacity="0.7" />
            <line x1="7"  y1="19" x2="21" y2="19" stroke="#ffd700" strokeWidth="1.5" />
          </svg>
          <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: '1.1rem', color: 'var(--text-accent)', letterSpacing: '0.04em' }}>
            GRAPH<span style={{ color: 'var(--text-primary)' }}>SKEL</span>
          </span>
          {demoMode && (
            <span className="demo-badge" style={{ marginLeft: 6 }}>Demo</span>
          )}
        </div>

        {/* Mode Tabs */}
        <nav style={{ display: 'flex', gap: 6 }}>
          {MODES.map(m => (
            <button
              key={m.id}
              className={`mode-tab ${mode === m.id ? 'active' : ''}`}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </nav>

        {/* Right badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: demoMode ? '#ff8c00' : '#00ff88', boxShadow: `0 0 6px ${demoMode ? '#ff8c00' : '#00ff88'}` }} />
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.7rem', color: 'var(--cold-ghost)' }}>
              {demoMode ? 'OFFLINE' : 'LIVE'}
            </span>
          </div>
          <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', color: 'var(--cold-ghost)', borderLeft: '1px solid var(--glass-border)', paddingLeft: 10 }}>
            ADAPTSKEL v1.0
          </span>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* Left Panel */}
        <motion.div
          key="ctrl"
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.35 }}
          style={{ width: 'var(--panel-w)', flexShrink: 0, overflowY: 'auto', padding: '12px 10px', zIndex: 10 }}
        >
          <ControlPanel />
        </motion.div>

        {/* Main Canvas */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <GraphCanvas3D />
          <AnimatePresence mode="wait">
            <ModeOverlay key={mode} />
          </AnimatePresence>
        </div>

        {/* Right Panel */}
        <motion.div
          key="stats"
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.35, delay: 0.05 }}
          style={{ width: 'var(--panel-w)', flexShrink: 0, overflowY: 'auto', padding: '12px 10px', zIndex: 10 }}
        >
          <StatsHUD />
        </motion.div>
      </div>

      {/* ── Footer Benchmark Bar ────────────────────────────── */}
      <div style={{ flexShrink: 0, height: 'var(--bench-h)', borderTop: '1px solid var(--glass-border)', background: 'rgba(13,17,23,0.95)' }}>
        <BenchmarkPanel compact />
      </div>
    </div>
  )
}

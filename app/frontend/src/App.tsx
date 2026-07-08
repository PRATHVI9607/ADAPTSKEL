import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGraphStore } from './store'
import type { Mode } from './engine/GraphState'
import { GraphCanvas3D } from './components/GraphCanvas3D'
import { ControlPanel } from './components/ControlPanel'
import { StatsHUD } from './components/StatsHUD'
import { BenchmarkPanel } from './components/BenchmarkPanel'
import { ModeOverlay } from './components/ModeOverlay'

const MODES: { id: Mode; label: string; desc: string }[] = [
  { id: 'live',      label: 'Live Stream',   desc: 'Real-time graph updates' },
  { id: 'skeleton',  label: 'Skeleton',      desc: 'F₁/F₂ layer explorer' },
  { id: 'heatmap',   label: 'Heat Map',      desc: 'Edge heat visualiser' },
  { id: 'benchmark', label: 'Benchmark',     desc: 'Performance comparison' },
  { id: 'explainer', label: 'Explainer',     desc: 'Step-by-step walkthrough' },
  { id: 'routing',   label: 'ISP Routing',   desc: 'ISP network backbone routing simulation' },
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
      className="app-shell"
      style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* ── Header ─────────────────────────────────────────────── */}
      <header
        style={{
          height: 'var(--header-h)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          borderBottom: '1px solid var(--sky-border)',
          background: 'rgba(10, 10, 16, 0.88)',
          backdropFilter: 'blur(18px)',
          boxShadow: '0 1px 8px rgba(0, 0, 0, 0.18)',
          zIndex: 100,
          flexShrink: 0,
          position: 'relative',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
            <circle cx="15" cy="15" r="14" stroke="var(--sky-blue)" strokeWidth="1.5" strokeOpacity="0.3" />
            <circle cx="15" cy="7"  r="3"   fill="var(--sky-blue)" />
            <circle cx="7"  cy="21" r="3"   fill="var(--eco-green)" />
            <circle cx="23" cy="21" r="3"   fill="var(--eco-green)" />
            <line x1="15" y1="7"  x2="7"  y2="21" stroke="var(--sky-blue)"  strokeWidth="1.8" strokeOpacity="0.7" />
            <line x1="15" y1="7"  x2="23" y2="21" stroke="var(--sky-blue)"  strokeWidth="1.8" strokeOpacity="0.7" />
            <line x1="7"  y1="21" x2="23" y2="21" stroke="var(--eco-green)" strokeWidth="1.8" />
          </svg>
          <div>
            <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-dark)', letterSpacing: '0.02em', lineHeight: 1.1 }}>
              GRAPH<span style={{ color: 'var(--sky-blue)' }}>SKEL</span>
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.6rem', color: 'var(--text-soft)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              ADAPTSKEL Visualiser
            </div>
          </div>
          {demoMode && (
            <span className="demo-badge" style={{ marginLeft: 6 }}>Demo</span>
          )}
        </div>

        {/* Mode Tabs */}
        <nav style={{ display: 'flex', gap: 4, flexWrap: 'nowrap', justifyContent: 'center', maxWidth: '52vw', overflowX: 'auto', minWidth: 0 }}>
          {MODES.map(m => (
            <button
              key={m.id}
              type="button"
              className={`mode-tab ${mode === m.id ? 'active' : ''}`}
              onClick={() => setMode(m.id)}
              title={m.desc}
            >
              {m.label}
            </button>
          ))}
        </nav>

        {/* Right status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: demoMode ? '#d97706' : '#16a34a',
              boxShadow: `0 0 6px ${demoMode ? '#d97706' : '#16a34a'}`,
            }} />
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', color: 'var(--text-mid)', fontWeight: 600 }}>
              {demoMode ? 'Offline Demo' : 'Live Backend'}
            </span>
          </div>
          <div style={{
            fontFamily: 'JetBrains Mono', fontSize: '0.68rem', color: 'var(--text-soft)',
            borderLeft: '1px solid var(--sky-border)', paddingLeft: 12,
          }}>
            ADAPTSKEL v1.0
          </div>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative', minWidth: 0 }}>
        {/* Left Panel */}
        <motion.div
          key="ctrl"
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.3 }}
          style={{
            width: 'var(--panel-w)', minWidth: 'var(--panel-w)', flexShrink: 0,
            overflowY: 'auto', padding: '10px 10px',
            zIndex: 10, borderRight: '1px solid var(--sky-border)',
            background: 'var(--bg-surface2)',
          }}
        >
          <ControlPanel />
        </motion.div>

        {/* Main Canvas */}
        <div style={{ flex: 1, minWidth: 0, position: 'relative', overflow: 'hidden' }}>
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
          transition={{ duration: 0.3, delay: 0.05 }}
          style={{
            width: 'var(--panel-w)', minWidth: 'var(--panel-w)', flexShrink: 0,
            overflowY: 'auto', padding: '10px 10px',
            zIndex: 10, borderLeft: '1px solid var(--sky-border)',
            background: 'var(--bg-surface2)',
          }}
        >
          <StatsHUD />
        </motion.div>
      </div>

      {/* ── Footer Benchmark Bar ──────────────────────────────── */}
      <div style={{
        flexShrink: 0, height: 'var(--bench-h)', minHeight: 'var(--bench-h)',
        borderTop: '1px solid var(--sky-border)',
        background: 'var(--bg-surface)',
      }}>
        <BenchmarkPanel compact />
      </div>
    </div>
  )
}

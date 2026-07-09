import { useState } from 'react'
import { Network, Zap, Trash2, Search, Play, Pause, SkipForward, Eye, EyeOff } from 'lucide-react'
import { useGraphStore } from '../store'
import { RoutingControlPanel } from './RoutingMode'

function SectionHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9, marginTop: 4 }}>
      <Icon size={13} color="var(--sky-blue)" />
      <span style={{
        fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700,
        letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-mid)',
      }}>
        {title}
      </span>
    </div>
  )
}

function Divider() {
  return <div className="gs-divider" />
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: 'Space Grotesk', fontSize: '0.65rem', color: 'var(--text-soft)',
      marginBottom: 4, letterSpacing: '0.04em',
    }}>
      {children}
    </div>
  )
}

export function ControlPanel() {
  const mode              = useGraphStore(s => s.mode)
  
  if (mode === 'routing') {
    return <RoutingControlPanel />
  }

  const loadPreset        = useGraphStore(s => s.loadPreset)
  const insertEdge        = useGraphStore(s => s.insertEdge)
  const deleteEdge        = useGraphStore(s => s.deleteEdge)
  const runQuery          = useGraphStore(s => s.runQuery)
  const setSimulatorSpeed = useGraphStore(s => s.setSimulatorSpeed)
  const showF1            = useGraphStore(s => s.showF1)
  const showF2            = useGraphStore(s => s.showF2)
  const setShowF1         = useGraphStore(s => s.setShowF1)
  const setShowF2         = useGraphStore(s => s.setShowF2)
  const isStreaming       = useGraphStore(s => s.isStreaming)
  const setStreaming       = useGraphStore(s => s.setStreaming)

  const [insertU, setInsertU] = useState('0')
  const [insertV, setInsertV] = useState('1')
  const [insertW, setInsertW] = useState('5')
  const [deleteU, setDeleteU] = useState('0')
  const [deleteV, setDeleteV] = useState('1')
  const [queryS,  setQueryS]  = useState('0')
  const [queryT,  setQueryT]  = useState('5')
  const [speed, setSpeed]     = useState<'slow' | 'normal' | 'fast'>('normal')

  const handleSpeed = (s: 'slow' | 'normal' | 'fast') => {
    setSpeed(s)
    const map = { slow: [1200, 4000], normal: [600, 2000], fast: [200, 800] } as const
    setSimulatorSpeed(map[s][0], map[s][1])
  }

  const handleInsert = () => {
    const u = parseInt(insertU), v = parseInt(insertV), w = parseFloat(insertW)
    if (!isNaN(u) && !isNaN(v) && !isNaN(w)) insertEdge(u, v, w)
  }

  const handleDelete = () => {
    const u = parseInt(deleteU), v = parseInt(deleteV)
    if (!isNaN(u) && !isNaN(v)) deleteEdge(u, v)
  }

  const handleQuery = () => {
    const s = parseInt(queryS), t = parseInt(queryT)
    if (!isNaN(s) && !isNaN(t)) runQuery(s, t)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

      {/* Algorithm brief */}
      <div style={{
        background: 'var(--sky-light)', border: '1px solid var(--sky-border)',
        borderRadius: 10, padding: '10px 12px', marginBottom: 4,
      }}>
        <div style={{
          fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: '0.78rem',
          color: 'var(--sky-dark)', marginBottom: 4,
        }}>
          ADAPTSKEL Algorithm
        </div>
        <div style={{ fontFamily: 'Inter', fontSize: '0.7rem', color: 'var(--text-mid)', lineHeight: 1.5 }}>
          Maintains exact shortest paths as edges are inserted/deleted.
          Source queries read a maintained label in <strong>O(1)</strong>; hot edges promote to the <strong>F₁</strong> skeleton.
        </div>
      </div>

      {/* ── Graph Presets ── */}
      <div className="glass-panel" style={{ padding: 12 }}>
        <SectionHeader icon={Network} title="Load Graph" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {[
            { label: 'Random 20',  p: 'random', n: 20 },
            { label: 'Random 50',  p: 'random', n: 50 },
            { label: 'Road Net',   p: 'road',   n: 30 },
            { label: 'Social Net', p: 'social', n: 40 },
          ].map(({ label, p, n }) => (
            <button
              key={label} type="button" className="gs-btn"
              onClick={() => loadPreset(p, n)}
              style={{ fontSize: '0.68rem', padding: '6px 6px' }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Stream Control ── */}
      <div className="glass-panel" style={{ padding: 12 }}>
        <SectionHeader icon={Zap} title="Stream Control" />

        <Label>Update speed</Label>
        <div style={{ display: 'flex', gap: 5, marginBottom: 8 }}>
          {(['slow', 'normal', 'fast'] as const).map(s => (
            <button
              key={s} type="button"
              className="gs-btn"
              onClick={() => handleSpeed(s)}
              style={{
                flex: 1, fontSize: '0.67rem', padding: '5px 4px',
                background: speed === s ? 'var(--sky-light)' : 'var(--bg-surface2)',
                borderColor: speed === s ? 'var(--sky-blue)' : 'var(--sky-border)',
                color: speed === s ? 'var(--sky-dark)' : 'var(--text-soft)',
                fontWeight: speed === s ? 700 : 500,
              }}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        <button
          type="button" className="gs-btn"
          onClick={() => setStreaming(!isStreaming)}
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
        >
          {isStreaming ? <Pause size={12} /> : <Play size={12} />}
          {isStreaming ? 'Pause Stream' : 'Resume Stream'}
        </button>
      </div>

      {/* ── Layer Visibility (skeleton mode only) ── */}
      {mode === 'skeleton' && (
        <div className="glass-panel" style={{ padding: 12 }}>
          <SectionHeader icon={Network} title="Layer Visibility" />
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button" className="gs-btn"
              onClick={() => setShowF1(!showF1)}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                background: showF1 ? 'var(--sky-light)' : 'var(--bg-surface2)',
                color: showF1 ? 'var(--sky-dark)' : 'var(--text-soft)',
                borderColor: showF1 ? 'var(--sky-blue)' : 'var(--sky-border)',
              }}
            >
              {showF1 ? <Eye size={12} /> : <EyeOff size={12} />}
              F₁ Skeleton
            </button>
            <button
              type="button" className="gs-btn"
              onClick={() => setShowF2(!showF2)}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                background: showF2 ? '#f0f4f8' : 'var(--bg-surface2)',
                color: showF2 ? 'var(--text-mid)' : 'var(--text-soft)',
                borderColor: showF2 ? '#9bb5cc' : 'var(--sky-border)',
              }}
            >
              {showF2 ? <Eye size={12} /> : <EyeOff size={12} />}
              F₂ Residual
            </button>
          </div>
          <div style={{ marginTop: 8, fontFamily: 'Inter', fontSize: '0.68rem', color: 'var(--text-soft)', lineHeight: 1.5 }}>
            Toggle layers to see how the skeleton separates hot edges from cold ones.
          </div>
        </div>
      )}

      {/* ── Insert Edge ── */}
      <div className="glass-panel" style={{ padding: 12 }}>
        <SectionHeader icon={SkipForward} title="Insert Edge" />
        <Label>Node u, node v, weight w</Label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5, marginBottom: 6 }}>
          <input className="gs-input" placeholder="u" value={insertU} onChange={e => setInsertU(e.target.value)} />
          <input className="gs-input" placeholder="v" value={insertV} onChange={e => setInsertV(e.target.value)} />
          <input className="gs-input" placeholder="w" value={insertW} onChange={e => setInsertW(e.target.value)} />
        </div>
        <button type="button" className="gs-btn success" onClick={handleInsert} style={{ width: '100%' }}>
          + Insert Edge (u, v, w)
        </button>
        <div style={{ marginTop: 5, fontFamily: 'Inter', fontSize: '0.67rem', color: 'var(--text-soft)' }}>
          Adds edge to F₂; promotes to F₁ if it improves distances.
        </div>
      </div>

      {/* ── Delete Edge ── */}
      <div className="glass-panel" style={{ padding: 12 }}>
        <SectionHeader icon={Trash2} title="Delete Edge" />
        <Label>Remove edge between nodes u and v</Label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5, marginBottom: 6 }}>
          <input className="gs-input" placeholder="u" value={deleteU} onChange={e => setDeleteU(e.target.value)} />
          <input className="gs-input" placeholder="v" value={deleteV} onChange={e => setDeleteV(e.target.value)} />
        </div>
        <button type="button" className="gs-btn danger" onClick={handleDelete} style={{ width: '100%' }}>
          − Delete Edge (u, v)
        </button>
        <div style={{ marginTop: 5, fontFamily: 'Inter', fontSize: '0.67rem', color: 'var(--text-soft)' }}>
          If deleted from F₁, ADAPTSKEL finds a replacement from F₂.
        </div>
      </div>

      {/* ── Query ── */}
      <div className="glass-panel" style={{ padding: 12 }}>
        <SectionHeader icon={Search} title="Query Shortest Path" />
        <Label>Find path from source to destination</Label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5, marginBottom: 6 }}>
          <input className="gs-input" placeholder="src" value={queryS} onChange={e => setQueryS(e.target.value)} />
          <input className="gs-input" placeholder="dst" value={queryT} onChange={e => setQueryT(e.target.value)} />
        </div>
        <button
          type="button" className="gs-btn" onClick={handleQuery}
          style={{
            width: '100%', color: 'var(--eco-dark)',
            borderColor: 'var(--eco-border)', background: 'var(--eco-light)',
          }}
        >
          ▶ Run Query (src → dst)
        </button>
        <div style={{ marginTop: 5, fontFamily: 'Inter', fontSize: '0.67rem', color: 'var(--text-soft)' }}>
          Result appears in the Query Trace panel →
        </div>
      </div>
    </div>
  )
}

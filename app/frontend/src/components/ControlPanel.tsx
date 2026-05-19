import { useState } from 'react'
import { motion } from 'framer-motion'
import { Network, Zap, Trash2, Search, Play, Pause, SkipForward } from 'lucide-react'
import { useGraphStore } from '../store'

function SectionHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10, marginTop: 4 }}>
      <Icon size={13} color="var(--skeleton-blue)" />
      <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--cold-ghost)' }}>
        {title}
      </span>
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--glass-border)', margin: '12px 0' }} />
}

export function ControlPanel() {
  const mode               = useGraphStore(s => s.mode)
  const loadPreset         = useGraphStore(s => s.loadPreset)
  const insertEdge         = useGraphStore(s => s.insertEdge)
  const deleteEdge         = useGraphStore(s => s.deleteEdge)
  const runQuery           = useGraphStore(s => s.runQuery)
  const setSimulatorSpeed  = useGraphStore(s => s.setSimulatorSpeed)
  const showF1             = useGraphStore(s => s.showF1)
  const showF2             = useGraphStore(s => s.showF2)
  const setShowF1          = useGraphStore(s => s.setShowF1)
  const setShowF2          = useGraphStore(s => s.setShowF2)
  const isStreaming        = useGraphStore(s => s.isStreaming)
  const setStreaming        = useGraphStore(s => s.setStreaming)

  const [insertU, setInsertU] = useState('0')
  const [insertV, setInsertV] = useState('1')
  const [insertW, setInsertW] = useState('5')
  const [deleteU, setDeleteU] = useState('0')
  const [deleteV, setDeleteV] = useState('1')
  const [queryS, setQueryS]   = useState('0')
  const [queryT, setQueryT]   = useState('5')
  const [speed, setSpeed]     = useState<'slow'|'normal'|'fast'>('normal')

  const handleSpeed = (s: 'slow'|'normal'|'fast') => {
    setSpeed(s)
    const map = { slow: [1200, 4000], normal: [600, 2000], fast: [200, 800] }
    setSimulatorSpeed(map[s][0], map[s][1])
  }

  const handleInsert = () => {
    const u = parseInt(insertU), v = parseInt(insertV), w = parseFloat(insertW)
    if (isNaN(u) || isNaN(v) || isNaN(w)) return
    insertEdge(u, v, w)
  }

  const handleDelete = () => {
    const u = parseInt(deleteU), v = parseInt(deleteV)
    if (isNaN(u) || isNaN(v)) return
    deleteEdge(u, v)
  }

  const handleQuery = () => {
    const s = parseInt(queryS), t = parseInt(queryT)
    if (isNaN(s) || isNaN(t)) return
    runQuery(s, t)
  }

  return (
    <div className="glass-panel" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Graph Presets */}
      <SectionHeader icon={Network} title="Graph Preset" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        {[
          { label: 'Random 20', p: 'random', n: 20 },
          { label: 'Random 50', p: 'random', n: 50 },
          { label: 'Road Net', p: 'road', n: 30 },
          { label: 'Social', p: 'social', n: 40 },
        ].map(({ label, p, n }) => (
          <button key={label} className="gs-btn" onClick={() => loadPreset(p, n)}
            style={{ fontSize: '0.68rem', padding: '6px 8px' }}>
            {label}
          </button>
        ))}
      </div>

      <Divider />

      {/* Stream Speed */}
      <SectionHeader icon={Zap} title="Stream Speed" />
      <div style={{ display: 'flex', gap: 6 }}>
        {(['slow','normal','fast'] as const).map(s => (
          <button key={s} className={`gs-btn ${speed === s ? 'active' : ''}`}
            onClick={() => handleSpeed(s)}
            style={{
              flex: 1, fontSize: '0.68rem', padding: '5px 4px',
              background: speed === s ? 'rgba(0,212,255,0.18)' : undefined,
              borderColor: speed === s ? 'var(--skeleton-blue)' : undefined,
              color: speed === s ? 'var(--skeleton-blue)' : undefined,
            }}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Pause/Resume */}
      <div style={{ marginTop: 8 }}>
        <button className="gs-btn" onClick={() => setStreaming(!isStreaming)}
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          {isStreaming ? <Pause size={12} /> : <Play size={12} />}
          {isStreaming ? 'Pause Stream' : 'Resume Stream'}
        </button>
      </div>

      {/* Skeleton visibility (skeleton mode) */}
      {mode === 'skeleton' && (
        <>
          <Divider />
          <SectionHeader icon={Network} title="Layer Visibility" />
          <div style={{ display: 'flex', gap: 8 }}>
            <button className={`gs-btn`} onClick={() => setShowF1(!showF1)}
              style={{ flex: 1, background: showF1 ? 'rgba(0,212,255,0.18)' : 'rgba(0,0,0,0.2)', color: showF1 ? '#00d4ff' : '#666', borderColor: showF1 ? '#00d4ff' : '#333' }}>
              F₁ Layer
            </button>
            <button className={`gs-btn`} onClick={() => setShowF2(!showF2)}
              style={{ flex: 1, background: showF2 ? 'rgba(144,144,160,0.15)' : 'rgba(0,0,0,0.2)', color: showF2 ? '#9090a0' : '#555', borderColor: showF2 ? '#9090a0' : '#333' }}>
              F₂ Layer
            </button>
          </div>
        </>
      )}

      <Divider />

      {/* Insert Edge */}
      <SectionHeader icon={SkipForward} title="Insert Edge" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
        <input className="gs-input" placeholder="u" value={insertU} onChange={e => setInsertU(e.target.value)} />
        <input className="gs-input" placeholder="v" value={insertV} onChange={e => setInsertV(e.target.value)} />
        <input className="gs-input" placeholder="w" value={insertW} onChange={e => setInsertW(e.target.value)} />
      </div>
      <button className="gs-btn success" onClick={handleInsert} style={{ marginTop: 5, width: '100%' }}>
        Insert (u, v, w)
      </button>

      <Divider />

      {/* Delete Edge */}
      <SectionHeader icon={Trash2} title="Delete Edge" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
        <input className="gs-input" placeholder="u" value={deleteU} onChange={e => setDeleteU(e.target.value)} />
        <input className="gs-input" placeholder="v" value={deleteV} onChange={e => setDeleteV(e.target.value)} />
      </div>
      <button className="gs-btn danger" onClick={handleDelete} style={{ marginTop: 5, width: '100%' }}>
        Delete (u, v)
      </button>

      <Divider />

      {/* Query */}
      <SectionHeader icon={Search} title="Query Path" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
        <input className="gs-input" placeholder="src" value={queryS} onChange={e => setQueryS(e.target.value)} />
        <input className="gs-input" placeholder="dst" value={queryT} onChange={e => setQueryT(e.target.value)} />
      </div>
      <button className="gs-btn" onClick={handleQuery} style={{ marginTop: 5, width: '100%', color: 'var(--path-gold)', borderColor: 'rgba(255,215,0,0.3)', background: 'rgba(255,215,0,0.06)' }}>
        Run Query
      </button>
    </div>
  )
}

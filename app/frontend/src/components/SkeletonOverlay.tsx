import { useGraphStore } from '../store'

export function SkeletonOverlay() {
  const stats        = useGraphStore(s => s.stats)
  const selectedEdge = useGraphStore(s => s.selectedEdge)

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      {/* Top info */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 20 }}>
        <div className="glass-panel" style={{ padding: '8px 16px', display: 'flex', gap: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 3, background: '#00d4ff', borderRadius: 2 }} />
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.72rem', color: '#00d4ff' }}>
              F₁ Skeleton ({stats.f1Edges} edges)
            </span>
          </div>
          <div style={{ width: 1, background: 'var(--glass-border)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 16, height: 3, background: '#9090a0', borderRadius: 2, opacity: 0.5 }} />
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.72rem', color: '#9090a0' }}>
              F₂ Cold ({stats.f2Edges} edges)
            </span>
          </div>
        </div>
      </div>

      {/* Selected edge info */}
      {selectedEdge && (
        <div className="glass-panel" style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', padding: '10px 20px', minWidth: 260 }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, color: 'var(--cold-ghost)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
            Selected Edge
          </div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            ({selectedEdge.u}, {selectedEdge.v}) — w = {selectedEdge.w}
          </div>
          <div style={{ marginTop: 4, display: 'flex', gap: 10 }}>
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: selectedEdge.inF1 ? 'rgba(0,212,255,0.15)' : 'rgba(144,144,160,0.1)', color: selectedEdge.inF1 ? '#00d4ff' : '#9090a0', border: `1px solid ${selectedEdge.inF1 ? 'rgba(0,212,255,0.3)' : 'rgba(144,144,160,0.2)'}` }}>
              {selectedEdge.inF1 ? 'F₁ Skeleton' : 'F₂ Cold'}
            </span>
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', padding: '2px 8px', borderRadius: 4, background: 'rgba(255,140,0,0.1)', color: '#ff8c00', border: '1px solid rgba(255,140,0,0.2)' }}>
              heat: {(selectedEdge.heat * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="glass-panel" style={{ position: 'absolute', bottom: 20, right: 12, padding: '10px 14px' }}>
        <div className="stat-label" style={{ marginBottom: 6 }}>Heat Scale</div>
        <div style={{ width: 120, height: 8, borderRadius: 4, background: 'linear-gradient(90deg, #00d4ff, #ff8c00, #ff3300)', marginBottom: 4 }} />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: '#00d4ff' }}>Cold</span>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: '#ff3300' }}>Hot</span>
        </div>
      </div>
    </div>
  )
}

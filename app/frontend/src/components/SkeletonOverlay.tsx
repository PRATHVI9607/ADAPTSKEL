import { useGraphStore } from '../store'

export function SkeletonOverlay() {
  const stats        = useGraphStore(s => s.stats)
  const selectedEdge = useGraphStore(s => s.selectedEdge)

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      {/* Top layer info bar */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)' }}>
        <div className="glass-panel" style={{ padding: '8px 20px', display: 'flex', gap: 20, alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 18, height: 3, background: 'var(--sky-blue)', borderRadius: 2 }} />
            <div>
              <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, color: 'var(--sky-blue)' }}>
                F₁ Skeleton
              </div>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.65rem', color: 'var(--text-soft)' }}>
                {stats.f1Edges} hot edges · Link-Cut Tree
              </div>
            </div>
          </div>

          <div style={{ width: 1, background: 'var(--sky-border)', height: 30 }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 18, height: 3, background: 'var(--f2-edge)', borderRadius: 2, opacity: 0.7 }} />
            <div>
              <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-mid)' }}>
                F₂ Residual
              </div>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.65rem', color: 'var(--text-soft)' }}>
                {stats.f2Edges} cold edges · Euler Tour Tree
              </div>
            </div>
          </div>

          <div style={{ width: 1, background: 'var(--sky-border)', height: 30 }} />

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.1rem', fontWeight: 600, color: 'var(--eco-green)' }}>
              {stats.totalEdges > 0 ? (stats.f1Edges / stats.totalEdges * 100).toFixed(0) : 0}%
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.6rem', color: 'var(--text-soft)' }}>skeleton fraction</div>
          </div>
        </div>
      </div>

      {/* Selected edge detail */}
      {selectedEdge && (
        <div className="glass-panel" style={{
          position: 'absolute', bottom: 20, left: '50%',
          transform: 'translateX(-50%)', padding: '12px 20px', minWidth: 280,
        }}>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.63rem', fontWeight: 700, color: 'var(--text-soft)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
            Selected Edge
          </div>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.9rem', color: 'var(--text-dark)', marginBottom: 8 }}>
            ({selectedEdge.u}, {selectedEdge.v}) — weight = {selectedEdge.w}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{
              fontFamily: 'Space Grotesk', fontSize: '0.7rem', padding: '3px 10px', borderRadius: 5, fontWeight: 600,
              background: selectedEdge.inF1 ? 'var(--sky-light)' : '#f0f4f8',
              color: selectedEdge.inF1 ? 'var(--sky-dark)' : 'var(--text-mid)',
              border: `1px solid ${selectedEdge.inF1 ? 'var(--sky-border)' : '#d1dce8'}`,
            }}>
              {selectedEdge.inF1 ? 'F₁ Skeleton' : 'F₂ Residual'}
            </span>
            <span style={{
              fontFamily: 'Space Grotesk', fontSize: '0.7rem', padding: '3px 10px', borderRadius: 5, fontWeight: 600,
              background: '#fff7ed',
              color: 'var(--heat-warm)',
              border: '1px solid rgba(217,119,6,0.2)',
            }}>
              heat: {(selectedEdge.heat * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {/* Heat legend */}
      <div className="glass-panel" style={{ position: 'absolute', bottom: 20, right: 12, padding: '10px 14px' }}>
        <div className="stat-label" style={{ marginBottom: 6 }}>Edge Heat Scale</div>
        <div style={{ width: 130, height: 8, borderRadius: 4, background: 'linear-gradient(90deg, var(--sky-blue), var(--heat-warm), var(--heat-hot))', marginBottom: 5 }} />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: 'var(--sky-blue)' }}>Cold (F₂)</span>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: 'var(--heat-hot)' }}>Hot (F₁)</span>
        </div>
      </div>
    </div>
  )
}

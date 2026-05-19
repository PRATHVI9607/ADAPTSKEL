import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useGraphStore } from '../store'

const TOOLTIP_STYLE = {
  backgroundColor: '#ffffff',
  border: '1px solid rgba(2,132,199,0.2)',
  borderRadius: 8,
  fontFamily: 'JetBrains Mono',
  fontSize: '0.72rem',
  color: 'var(--text-dark)',
  boxShadow: '0 4px 12px rgba(0,80,160,0.1)',
}

export function HeatMapOverlay() {
  const edges        = useGraphStore(s => [...s.edges.values()])
  const zipfAlpha    = useGraphStore(s => s.zipfAlpha)
  const setZipfAlpha = useGraphStore(s => s.setZipfAlpha)
  const stats        = useGraphStore(s => s.stats)

  const histogram = useMemo(() => {
    const buckets = Array.from({ length: 10 }, (_, i) => ({
      range: `${i * 10}–${(i + 1) * 10}%`,
      count: 0,
    }))
    for (const edge of edges) {
      const idx = Math.min(9, Math.floor(edge.heat * 10))
      buckets[idx].count++
    }
    return buckets
  }, [edges])

  const hotEdges   = edges.filter(e => e.heat > 0.5).length
  const totalEdges = edges.length

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      {/* Header stats */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)' }}>
        <div className="glass-panel" style={{ padding: '8px 24px', display: 'flex', gap: 24, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.3rem', fontWeight: 600, color: 'var(--heat-warm)' }}>
              {hotEdges}
            </div>
            <div className="stat-label">Hot edges (&gt;50%)</div>
          </div>
          <div style={{ width: 1, background: 'var(--sky-border)', height: 30 }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.3rem', fontWeight: 600, color: 'var(--sky-blue)' }}>
              {totalEdges > 0 ? ((hotEdges / totalEdges) * 100).toFixed(0) : 0}%
            </div>
            <div className="stat-label">Hot ratio</div>
          </div>
          <div style={{ width: 1, background: 'var(--sky-border)', height: 30 }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.3rem', fontWeight: 600, color: 'var(--eco-green)' }}>
              {stats.totalPromotions}
            </div>
            <div className="stat-label">Promotions to F₁</div>
          </div>
        </div>
      </div>

      {/* Histogram + Zipf control */}
      <div className="glass-panel" style={{
        position: 'absolute', bottom: 20, left: '50%',
        transform: 'translateX(-50%)', padding: 16, minWidth: 380,
        pointerEvents: 'all',
      }}>
        <div style={{
          fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700,
          color: 'var(--text-mid)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8,
        }}>
          Edge Heat Distribution (Zipf power-law)
        </div>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={histogram} margin={{ top: 0, right: 0, bottom: 0, left: -10 }}>
            <CartesianGrid stroke="rgba(2,132,199,0.06)" vertical={false} />
            <XAxis
              dataKey="range"
              tick={{ fontFamily: 'JetBrains Mono', fontSize: 9, fill: 'var(--text-soft)' }}
              interval={1}
            />
            <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 9, fill: 'var(--text-soft)' }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="count" fill="var(--heat-warm)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>

        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="stat-label" style={{ whiteSpace: 'nowrap' }}>Zipf α:</span>
          <input
            type="range" min={0.5} max={3.0} step={0.1}
            value={zipfAlpha}
            aria-label={`Zipf alpha: ${zipfAlpha.toFixed(1)}`}
            title={`Zipf alpha (skew): ${zipfAlpha.toFixed(1)}`}
            onChange={e => setZipfAlpha(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: 'var(--heat-warm)' }}
          />
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.82rem', color: 'var(--heat-warm)', minWidth: 30, fontWeight: 600 }}>
            {zipfAlpha.toFixed(1)}
          </span>
        </div>
        <div style={{ marginTop: 6, fontFamily: 'Inter', fontSize: '0.68rem', color: 'var(--text-soft)', lineHeight: 1.5 }}>
          Higher α → more skewed. A few edges get very hot (Zipf's law), forming a tight F₁ skeleton.
        </div>
      </div>

      {/* Heat colour legend */}
      <div className="glass-panel" style={{ position: 'absolute', bottom: 20, right: 12, padding: '10px 14px' }}>
        <div className="stat-label" style={{ marginBottom: 6 }}>Heat Colour</div>
        <div style={{
          width: 130, height: 9, borderRadius: 5,
          background: 'linear-gradient(90deg, var(--sky-blue) 0%, var(--heat-warm) 60%, var(--heat-hot) 100%)',
          marginBottom: 5,
        }} />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: 'var(--sky-blue)' }}>Cold</span>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', color: 'var(--heat-hot)' }}>Hot</span>
        </div>
      </div>
    </div>
  )
}

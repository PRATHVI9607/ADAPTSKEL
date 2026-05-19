import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useGraphStore } from '../store'

const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(13,17,23,0.95)',
  border: '1px solid rgba(0,212,255,0.2)',
  borderRadius: 8,
  fontFamily: 'JetBrains Mono',
  fontSize: '0.72rem',
  color: '#e0e8ff',
}

export function HeatMapOverlay() {
  const edges      = useGraphStore(s => [...s.edges.values()])
  const heatScores = useGraphStore(s => s.heatScores)
  const zipfAlpha  = useGraphStore(s => s.zipfAlpha)
  const setZipfAlpha = useGraphStore(s => s.setZipfAlpha)
  const stats      = useGraphStore(s => s.stats)

  // Build histogram of heat scores (10 buckets)
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

  const hotEdges = edges.filter(e => e.heat > 0.5).length
  const totalEdges = edges.length

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      {/* Header */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)' }}>
        <div className="glass-panel" style={{ padding: '8px 20px', display: 'flex', gap: 20, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.4rem', color: '#ff8c00' }}>
              {hotEdges}
            </div>
            <div className="stat-label">Hot edges (&gt;50%)</div>
          </div>
          <div style={{ width: 1, background: 'var(--glass-border)', height: 30 }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.4rem', color: '#00d4ff' }}>
              {totalEdges > 0 ? ((hotEdges / totalEdges) * 100).toFixed(0) : 0}%
            </div>
            <div className="stat-label">Hot ratio</div>
          </div>
          <div style={{ width: 1, background: 'var(--glass-border)', height: 30 }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.4rem', color: '#ffd700' }}>
              {stats.totalPromotions}
            </div>
            <div className="stat-label">Total promotions</div>
          </div>
        </div>
      </div>

      {/* Histogram + Zipf control */}
      <div className="glass-panel" style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', padding: 16, minWidth: 380, pointerEvents: 'all' }}>
        <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, color: 'var(--cold-ghost)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
          Edge Heat Distribution
        </div>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={histogram} margin={{ top: 0, right: 0, bottom: 0, left: -10 }}>
            <CartesianGrid stroke="rgba(0,212,255,0.05)" vertical={false} />
            <XAxis dataKey="range" tick={{ fontFamily: 'JetBrains Mono', fontSize: 9, fill: 'var(--cold-ghost)' }} interval={1} />
            <YAxis tick={{ fontFamily: 'JetBrains Mono', fontSize: 9, fill: 'var(--cold-ghost)' }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="count"
              fill="#ff8c00"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>

        {/* Zipf α */}
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="stat-label">Zipf α:</span>
          <input type="range" min={0.5} max={3.0} step={0.1}
            value={zipfAlpha} onChange={e => setZipfAlpha(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: '#ff8c00' }} />
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem', color: '#ff8c00', minWidth: 28 }}>
            {zipfAlpha.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Heat colour legend */}
      <div className="glass-panel" style={{ position: 'absolute', bottom: 20, right: 12, padding: '10px 14px' }}>
        <div className="stat-label" style={{ marginBottom: 6 }}>Heat Colour</div>
        <div style={{ width: 120, height: 10, borderRadius: 5, background: 'linear-gradient(90deg, #00d4ff 0%, #ff8c00 60%, #ff3300 100%)', marginBottom: 4 }} />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: '#00d4ff' }}>0</span>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.6rem', color: '#ff3300' }}>1</span>
        </div>
      </div>
    </div>
  )
}

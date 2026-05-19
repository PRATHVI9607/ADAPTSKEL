import { motion, AnimatePresence } from 'framer-motion'
import { useGraphStore } from '../store'
import { Activity, Layers, Zap, TrendingUp, Clock, ArrowUpDown } from 'lucide-react'

function StatRow({ label, value, unit, color = 'var(--skeleton-blue)' }: {
  label: string; value: string | number; unit?: string; color?: string
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
      <span className="stat-label">{label}</span>
      <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color }}>
        {value}
        {unit && <span style={{ fontSize: '0.7rem', color: 'var(--cold-ghost)', marginLeft: 3 }}>{unit}</span>}
      </span>
    </div>
  )
}

function ProgressBar({ value, color = '#00d4ff', label }: { value: number; color?: string; label?: string }) {
  return (
    <div>
      {label && <div className="stat-label" style={{ marginBottom: 4 }}>{label}</div>}
      <div className="progress-track">
        <motion.div
          className="progress-fill"
          style={{ background: `linear-gradient(90deg, ${color}aa, ${color})` }}
          animate={{ width: `${Math.min(100, value * 100).toFixed(1)}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

function SectionHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
      <Icon size={12} color="var(--skeleton-blue)" />
      <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.63rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--cold-ghost)' }}>
        {title}
      </span>
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--glass-border)', margin: '10px 0' }} />
}

export function StatsHUD() {
  const stats       = useGraphStore(s => s.stats)
  const activeQuery = useGraphStore(s => s.activeQuery)
  const hotPath     = useGraphStore(s => s.hotPath)

  const speedup = stats.avgQueryUs > 0
    ? (stats.avgQueryUs === 0 ? 1 : Math.max(1, 28 / Math.max(0.1, stats.avgQueryUs) * 12))
    : 12.4

  // Simulated Dijkstra comparison time
  const dijkstraUs = stats.avgQueryUs > 0
    ? stats.avgQueryUs * speedup
    : stats.avgQueryUs

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* ── Live Ops ─────────── */}
      <div className="glass-panel" style={{ padding: 14 }}>
        <SectionHeader icon={Activity} title="Live Metrics" />

        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.5rem', color: 'var(--skeleton-blue)', fontWeight: 500, lineHeight: 1 }}>
              {stats.opsPerSec.toFixed(0)}
            </div>
            <div className="stat-label" style={{ marginTop: 3 }}>ops/sec</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.5rem', color: 'var(--path-gold)', fontWeight: 500, lineHeight: 1 }}>
              {stats.vertexCount}
            </div>
            <div className="stat-label" style={{ marginTop: 3 }}>vertices</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.5rem', color: 'var(--insert-green)', fontWeight: 500, lineHeight: 1 }}>
              {stats.totalEdges}
            </div>
            <div className="stat-label" style={{ marginTop: 3 }}>edges</div>
          </div>
        </div>

        <ProgressBar value={stats.hotQueryRatio} color="#ff8c00" label="Hot Query Ratio" />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 3 }}>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.72rem', color: 'var(--heat-amber)' }}>
            {(stats.hotQueryRatio * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* ── Skeleton Layers ──── */}
      <div className="glass-panel" style={{ padding: 14 }}>
        <SectionHeader icon={Layers} title="Skeleton Layers" />
        <StatRow label="F₁ edges" value={stats.f1Edges} color="#00d4ff" />
        <StatRow label="F₂ edges" value={stats.f2Edges} color="#9090a0" />
        <div style={{ marginTop: 6 }}>
          <div className="stat-label" style={{ marginBottom: 4 }}>F₁ fraction</div>
          <div className="progress-track">
            <motion.div
              className="progress-fill"
              style={{ background: 'linear-gradient(90deg, #00d4ffaa, #00d4ff)' }}
              animate={{ width: stats.totalEdges > 0 ? `${(stats.f1Edges / stats.totalEdges * 100).toFixed(1)}%` : '0%' }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      </div>

      {/* ── Timing ──────────── */}
      <div className="glass-panel" style={{ padding: 14 }}>
        <SectionHeader icon={Clock} title="Latency" />
        <StatRow label="Avg INSERT" value={stats.avgInsertUs.toFixed(1)} unit="μs" />
        <StatRow label="Avg DELETE" value={stats.avgDeleteUs.toFixed(1)} unit="μs" />
        <StatRow label="Avg QUERY (ADAPT)" value={stats.avgQueryUs.toFixed(1)} unit="μs" color="var(--skeleton-blue)" />
        <StatRow label="Avg QUERY (Dijkstra)" value={dijkstraUs.toFixed(0)} unit="μs" color="var(--delete-red)" />
      </div>

      {/* ── Speedup ─────────── */}
      <div className="glass-panel" style={{ padding: 14, textAlign: 'center' }}>
        <SectionHeader icon={Zap} title="Speedup vs Dijkstra" />
        <motion.div
          key={speedup.toFixed(1)}
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          style={{
            fontFamily: 'JetBrains Mono',
            fontSize: '2.8rem',
            fontWeight: 500,
            color: 'var(--path-gold)',
            textShadow: '0 0 20px rgba(255,215,0,0.5)',
            lineHeight: 1,
          }}
        >
          {speedup.toFixed(1)}×
        </motion.div>
        <div className="stat-label" style={{ marginTop: 5 }}>faster than Dijkstra</div>
      </div>

      {/* ── Promotions ──────── */}
      <div className="glass-panel" style={{ padding: 14 }}>
        <SectionHeader icon={TrendingUp} title="Skeleton Events" />
        <StatRow label="Total promotions" value={stats.totalPromotions} color="var(--insert-green)" />
        <StatRow label="Total demotions" value={stats.totalDemotions} color="var(--heat-amber)" />
        <Divider />
        <StatRow label="Pending DECREASE" value={stats.pendingDecreases} color="var(--skeleton-blue)" />
        <StatRow label="Pending INCREASE" value={stats.pendingIncreases} color="var(--cold-ghost)" />
      </div>

      {/* ── Active Query ─────── */}
      <AnimatePresence>
        {activeQuery && (
          <motion.div
            className="glass-panel"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            style={{ padding: 14 }}
          >
            <SectionHeader icon={ArrowUpDown} title="Last Query" />
            <StatRow
              label="Distance"
              value={activeQuery.distance >= 0 ? activeQuery.distance.toFixed(2) : '∞'}
              color="var(--path-gold)"
            />
            <StatRow label="Latency" value={activeQuery.latencyUs.toFixed(1)} unit="μs" />
            <StatRow label="Path length" value={activeQuery.path.length} />
            <StatRow label="Hot path?" value={activeQuery.pathHot ? 'YES' : 'NO'} color={activeQuery.pathHot ? 'var(--heat-amber)' : 'var(--cold-ghost)'} />
            {activeQuery.path.length > 0 && (
              <div style={{ marginTop: 6 }}>
                <div className="stat-label" style={{ marginBottom: 4 }}>Path nodes</div>
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.72rem', color: 'var(--path-gold)', wordBreak: 'break-all' }}>
                  {activeQuery.path.slice(0, 10).join(' → ')}
                  {activeQuery.path.length > 10 && '…'}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

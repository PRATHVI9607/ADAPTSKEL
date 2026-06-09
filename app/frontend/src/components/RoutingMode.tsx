import { useEffect } from 'react'
import { Play, Pause, AlertTriangle, Activity, ShieldAlert, Cpu } from 'lucide-react'
import { useGraphStore } from '../store'

export function RoutingControlPanel() {
  const routingNodes = useGraphStore(s => s.routingNodes)
  const routingSource = useGraphStore(s => s.routingSource)
  const routingTarget = useGraphStore(s => s.routingTarget)
  const setRoutingSource = useGraphStore(s => s.setRoutingSource)
  const setRoutingTarget = useGraphStore(s => s.setRoutingTarget)
  
  const routingActive = useGraphStore(s => s.routingActive)
  const toggleRoutingSimulation = useGraphStore(s => s.toggleRoutingSimulation)
  const fetchRoutingTopology = useGraphStore(s => s.fetchRoutingTopology)

  useEffect(() => {
    // Poll topology updates every 2 seconds to reflect background Poisson events
    const timer = setInterval(() => {
      fetchRoutingTopology()
    }, 2000)
    return () => clearInterval(timer)
  }, [fetchRoutingTopology])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Simulation Control */}
      <div className="glass-panel" style={{ padding: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
          <Cpu size={14} color="var(--sky-blue)" />
          <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-mid)' }}>
            Simulation Control
          </span>
        </div>
        <div style={{ fontFamily: 'Inter', fontSize: '0.68rem', color: 'var(--text-soft)', lineHeight: 1.4, marginBottom: 12 }}>
          Simulates continuous Poisson-distributed fiber link cuts and recoveries in the network core.
        </div>
        <button
          type="button"
          className={`gs-btn ${routingActive ? 'danger' : 'success'}`}
          onClick={toggleRoutingSimulation}
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '7px 0' }}
        >
          {routingActive ? <Pause size={12} /> : <Play size={12} />}
          {routingActive ? 'Halt Simulation' : 'Launch Simulation'}
        </button>
      </div>

      {/* Reroute Core */}
      <div className="glass-panel" style={{ padding: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
          <Activity size={14} color="var(--sky-blue)" />
          <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-mid)' }}>
            Path Pathfinder
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.62rem', color: 'var(--text-soft)', marginBottom: 4 }}>
              ORIGIN ROUTER
            </div>
            <select
              className="gs-input"
              value={routingSource ?? ''}
              onChange={e => setRoutingSource(e.target.value === '' ? null : parseInt(e.target.value))}
              style={{ width: '100%', background: 'var(--bg-surface2)', color: 'var(--text-dark)', cursor: 'pointer', padding: 5, fontSize: '0.72rem' }}
            >
              <option value="">-- Choose City --</option>
              {routingNodes.map(n => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.62rem', color: 'var(--text-soft)', marginBottom: 4 }}>
              DESTINATION ROUTER
            </div>
            <select
              className="gs-input"
              value={routingTarget ?? ''}
              onChange={e => setRoutingTarget(e.target.value === '' ? null : parseInt(e.target.value))}
              style={{ width: '100%', background: 'var(--bg-surface2)', color: 'var(--text-dark)', cursor: 'pointer', padding: 5, fontSize: '0.72rem' }}
            >
              <option value="">-- Choose City --</option>
              {routingNodes.map(n => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Manual Link Failures */}
      <div className="glass-panel" style={{ padding: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
          <AlertTriangle size={14} color="var(--sky-blue)" />
          <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-mid)' }}>
            Active Link Management
          </span>
        </div>
        <div style={{ fontFamily: 'Inter', fontSize: '0.68rem', color: 'var(--text-soft)', lineHeight: 1.4, marginBottom: 8 }}>
          To simulate a manual failure, click any edge on the 3D map or select links in the dashboard.
        </div>
        <div style={{ maxHeight: 120, overflowY: 'auto', border: '1px solid var(--sky-border)', borderRadius: 6, background: 'var(--bg-surface)' }}>
          <LinkGrid />
        </div>
      </div>
    </div>
  )
}

function LinkGrid() {
  const routingEdges = useGraphStore(s => s.routingEdges)
  const routingNodes = useGraphStore(s => s.routingNodes)
  const triggerRoutingFailure = useGraphStore(s => s.triggerRoutingFailure)
  const triggerRoutingRecovery = useGraphStore(s => s.triggerRoutingRecovery)

  const nodeMap = new Map(routingNodes.map(n => [n.id, n.name]))

  if (routingEdges.length === 0) {
    return <div style={{ padding: 8, fontSize: '0.68rem', color: 'var(--text-soft)', textAlign: 'center' }}>No links configured.</div>
  }

  return (
    <table style={{ width: '100%', fontSize: '0.65rem', borderCollapse: 'collapse', textAlign: 'left' }}>
      <thead>
        <tr style={{ background: 'var(--bg-surface2)', borderBottom: '1px solid var(--sky-border)' }}>
          <th style={{ padding: '4px 6px', fontWeight: 600 }}>Link Segment</th>
          <th style={{ padding: '4px 6px', fontWeight: 600, textAlign: 'center' }}>Status</th>
        </tr>
      </thead>
      <tbody>
        {routingEdges.map((e, idx) => {
          const uName = nodeMap.get(e.u) || `Node ${e.u}`
          const vName = nodeMap.get(e.v) || `Node ${e.v}`
          const isFailed = e.status === 'failed'
          return (
            <tr key={idx} style={{ borderBottom: '1px solid var(--sky-border)', background: isFailed ? 'rgba(239, 68, 68, 0.05)' : 'none' }}>
              <td style={{ padding: '5px 6px', color: 'var(--text-mid)' }}>
                {uName} ↔ {vName}
              </td>
              <td style={{ padding: '5px 6px', textAlign: 'center' }}>
                <button
                  type="button"
                  onClick={() => isFailed ? triggerRoutingRecovery(e.u, e.v) : triggerRoutingFailure(e.u, e.v)}
                  style={{
                    fontSize: '0.55rem',
                    padding: '2px 6px',
                    borderRadius: 4,
                    border: '1px solid',
                    cursor: 'pointer',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    background: isFailed ? 'rgba(239, 68, 68, 0.12)' : 'rgba(22, 163, 74, 0.12)',
                    color: isFailed ? 'red' : 'green',
                    borderColor: isFailed ? 'rgba(239, 68, 68, 0.3)' : 'rgba(22, 163, 74, 0.3)'
                  }}
                >
                  {isFailed ? 'Restore' : 'Cut Link'}
                </button>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export function RoutingStatsHUD() {
  const routingMetrics = useGraphStore(s => s.routingMetrics)
  const routingPath = useGraphStore(s => s.routingPath)
  const routingNodes = useGraphStore(s => s.routingNodes)

  const nodeMap = new Map(routingNodes.map(n => [n.id, n.name]))

  if (!routingMetrics) {
    return (
      <div className="glass-panel" style={{ padding: 13, textAlign: 'center', color: 'var(--text-soft)', fontSize: '0.7rem' }}>
        Initialising backbone metrics...
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Active Routing Path Trace */}
      {routingPath.length > 0 && (
        <div className="glass-panel" style={{ padding: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Activity size={13} color="var(--eco-green)" />
            <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--eco-dark)' }}>
              Active Routing Path
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'center', fontSize: '0.67rem' }}>
            {routingPath.map((nid, idx) => (
              <span key={idx} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                <span style={{
                  background: idx === 0 || idx === routingPath.length - 1 ? 'var(--sky-dark)' : 'var(--eco-green)',
                  color: 'white',
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontWeight: 600,
                  fontSize: '0.6rem'
                }}>
                  {nodeMap.get(nid) || nid}
                </span>
                {idx < routingPath.length - 1 && <span style={{ color: 'var(--text-soft)' }}>→</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Network Resilience Status */}
      <div className="glass-panel" style={{ padding: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
          <ShieldAlert size={14} color="var(--sky-blue)" />
          <span style={{ fontFamily: 'Space Grotesk', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-mid)' }}>
            Network Resilience
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-soft)' }}>Convergence Time</span>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: 'var(--sky-blue)', fontWeight: 600 }}>
              {routingMetrics.avg_convergence_ms.toFixed(3)} <span style={{ fontSize: '0.65rem', fontWeight: 400 }}>ms</span>
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-soft)' }}>Estimated Packet Loss</span>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: 'var(--heat-warm)', fontWeight: 600 }}>
              {routingMetrics.traffic_loss_pct.toFixed(3)}%
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-soft)' }}>Path Optimality</span>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: 'var(--eco-green)', fontWeight: 600 }}>
              {routingMetrics.path_optimality_pct.toFixed(1)}%
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-soft)' }}>Active Link Failures</span>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: routingMetrics.active_failures > 0 ? 'red' : 'green', fontWeight: 600 }}>
              {routingMetrics.active_failures}
            </span>
          </div>
        </div>
      </div>

      {/* ISP Convergence Telemetry */}
      <div className="glass-panel" style={{ padding: 13, textAlign: 'center' }}>
        <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-mid)', marginBottom: 6 }}>
          Telemetry Benchmark
        </div>
        <div style={{ fontFamily: 'JetBrains Mono', fontSize: '1.8rem', fontWeight: 600, color: 'var(--eco-green)', lineHeight: 1 }}>
          &lt; 5.0ms
        </div>
        <div style={{ fontFamily: 'Space Grotesk', fontSize: '0.58rem', color: 'var(--text-soft)', marginTop: 4 }}>
          ADAPTSKEL target convergence threshold.
        </div>
      </div>
    </div>
  )
}

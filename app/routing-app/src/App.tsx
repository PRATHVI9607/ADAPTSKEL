import { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Play, Pause, RefreshCw, AlertTriangle, ShieldCheck, Activity, Download, Layers, MapPin, Globe } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'

const API_BASE = (import.meta as any).env.VITE_API_BASE || 'http://localhost:8000'

interface CityNode {
  id: number
  name: string
  lat: number
  lon: number
  population: number
  status: string
}

interface LinkEdge {
  u: number
  v: number
  w: number
  capacity: number
  status: string
  layer: string
}

interface TelemetryMetrics {
  total_failures: number
  total_recoveries: number
  avg_convergence_ms: number
  traffic_loss_pct: number
  path_optimality_pct: number
  active_failures: number
}

interface LogEvent {
  id: string
  time: string
  event: string
  message: string
  type: 'info' | 'warn' | 'success' | 'error'
}

interface HistoryPoint {
  tick: number
  convergence: number
  loss: number
}

// Map standardizer helper
function MapController({ center, zoom }: { center: [number, number], zoom: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, zoom)
  }, [center, zoom, map])
  return null
}

export default function App() {
  const [nodes, setNodes] = useState<CityNode[]>([])
  const [edges, setEdges] = useState<LinkEdge[]>([])
  const [metrics, setMetrics] = useState<TelemetryMetrics>({
    total_failures: 0,
    total_recoveries: 0,
    avg_convergence_ms: 0.0,
    traffic_loss_pct: 0.0,
    path_optimality_pct: 100.0,
    active_failures: 0
  })

  const [simActive, setSimActive] = useState(false)
  const [simInterval, setSimInterval] = useState(8.0)
  const [selectedSource, setSelectedSource] = useState<number | null>(null)
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null)
  const [activePath, setActivePath] = useState<number[]>([])
  const [pathDistance, setPathDistance] = useState<number | null>(null)
  const [bottleneck, setBottleneck] = useState<number | null>(null)
  const [queryTimeUs, setQueryTimeUs] = useState<number | null>(null)

  const [eventLog, setEventLog] = useState<LogEvent[]>([])
  const [chartHistory, setChartHistory] = useState<HistoryPoint[]>([])
  const tickCounter = useRef(0)

  // Map view config
  const mapCenter: [number, number] = [20.5937, 78.9629]
  const mapZoom = 5

  // Poll simulation status and topology
  const refreshTopology = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/routing/topology`)
      const data = await res.json()
      setNodes(data.nodes)
      setEdges(data.edges)
      setMetrics(data.metrics)
    } catch (err) {
      addLog('error', 'Failed to fetch network topology from backend service.')
    }
  }

  const checkSimStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/routing/simulation/status`)
      const data = await res.json()
      setSimActive(data.active)
    } catch (err) {}
  }

  // Effect to pull initial data and poll updates
  useEffect(() => {
    refreshTopology()
    checkSimStatus()
    const interval = setInterval(() => {
      refreshTopology()
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Update chart history when metrics change
  useEffect(() => {
    if (metrics.avg_convergence_ms > 0 || metrics.traffic_loss_pct > 0) {
      tickCounter.current += 1
      setChartHistory(prev => {
        const next = [...prev, {
          tick: tickCounter.current,
          convergence: metrics.avg_convergence_ms,
          loss: metrics.traffic_loss_pct
        }]
        return next.slice(-20) // Keep last 20 points
      })
    }
  }, [metrics])

  // Custom log system
  const addLog = (type: 'info' | 'warn' | 'success' | 'error', message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setEventLog(prev => [
      { id: Math.random().toString(), time: timestamp, event: type.toUpperCase(), message, type },
      ...prev.slice(0, 49)
    ])
  }

  // Toggle background Poisson process
  const toggleSimulation = async () => {
    try {
      const endpoint = simActive ? 'stop' : 'start'
      const body = simActive ? {} : { interval_sec: simInterval }
      const res = await fetch(`${API_BASE}/api/routing/simulation/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await res.json()
      if (data.status === 'started' || data.status === 'stopping') {
        setSimActive(!simActive)
        addLog(
          simActive ? 'warn' : 'success',
          simActive ? 'Poisson simulation loop halted.' : `Poisson simulation launched (speed scaling active).`
        )
      }
    } catch (err) {
      addLog('error', 'Simulation command failed to execute.')
    }
  }

  // Change simulation speed / interval
  const handleIntervalChange = async (val: number) => {
    setSimInterval(val)
    if (simActive) {
      try {
        await fetch(`${API_BASE}/api/routing/simulation/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ interval_sec: val })
        })
        addLog('info', `Simulation Poisson failure interval set to ${val}s.`)
      } catch (err) {}
    }
  }

  // Reset simulation state
  const resetSimulation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/routing/simulation/reset`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'reset') {
        setSelectedSource(null)
        setSelectedTarget(null)
        setActivePath([])
        setPathDistance(null)
        setBottleneck(null)
        setQueryTimeUs(null)
        setChartHistory([])
        setSimActive(false)
        await refreshTopology()
        addLog('success', 'Backbone simulation engine reset to initial clean state.')
      }
    } catch (err) {
      addLog('error', 'Failed to reset simulation.')
    }
  }

  // Query custom shortest path route between selected cities
  const runRoute = async (src: number, dst: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/routing/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: src, target: dst })
      })
      const data = await res.json()
      if (data.error) {
        setActivePath([])
        setPathDistance(null)
        setBottleneck(null)
        addLog('warn', `No path available: ${data.error}`)
      } else {
        setActivePath(data.path)
        setPathDistance(data.distance)
        setBottleneck(data.bottleneck_gbps)
        setQueryTimeUs(data.query_time_us)
        const pathNames = data.path.map((id: number) => nodes.find(n => n.id === id)?.name || id).join(' → ')
        addLog('success', `Reroute path computed in ${data.query_time_us}μs: ${pathNames}`)
      }
    } catch (err) {
      addLog('error', 'Routing request failed.')
    }
  }

  useEffect(() => {
    if (selectedSource !== null && selectedTarget !== null) {
      runRoute(selectedSource, selectedTarget)
    } else {
      setActivePath([])
      setPathDistance(null)
      setBottleneck(null)
    }
  }, [selectedSource, selectedTarget, edges])

  // Trigger manual link failure
  const toggleLink = async (u: number, v: number, currentStatus: string) => {
    try {
      const endpoint = currentStatus === 'failed' ? 'recovery' : 'failure'
      const res = await fetch(`${API_BASE}/api/routing/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ u, v })
      })
      const data = await res.json()
      if (data.success) {
        await refreshTopology()
        const uName = nodes.find(n => n.id === u)?.name || u
        const vName = nodes.find(n => n.id === v)?.name || v
        addLog(
          currentStatus === 'failed' ? 'success' : 'warn',
          currentStatus === 'failed'
            ? `Fiber link restored between ${uName} and ${vName}. Rerouted in ${data.convergence_time_ms}ms.`
            : `Fiber link CUT between ${uName} and ${vName}. Reconverged in ${data.convergence_time_ms}ms.`
        )
      }
    } catch (err) {
      addLog('error', 'Failed to toggle fiber link status.')
    }
  }

  // Export report to CSV
  const handleExportCSV = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/routing/simulation/export`)
      const csvContent = await res.text()
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.setAttribute('href', url)
      link.setAttribute('download', `routing_metrics_report.csv`)
      link.style.visibility = 'hidden'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      addLog('success', 'Simulation metrics report CSV downloaded successfully.')
    } catch (err) {
      addLog('error', 'CSV export failed.')
    }
  }

  // Leaflet custom divicon marker creator
  const createRouterIcon = (city: CityNode) => {
    const isSource = selectedSource === city.id
    const isTarget = selectedTarget === city.id
    const isNodeFailed = edges.some(e => e.status === 'failed' && (e.u === city.id || e.v === city.id))
    
    let stateClass = ''
    if (isSource || isTarget) stateClass = 'selected'
    else if (isNodeFailed) stateClass = 'failed'
    else stateClass = city.population > 1000000 ? 'hub' : 'spoke'

    return L.divIcon({
      html: `<div>${city.name.substring(0, 3).toUpperCase()}</div>`,
      className: `router-icon ${stateClass}`,
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    })
  }

  // Check SLO status
  const isConvergenceSloMet = metrics.avg_convergence_ms <= 10.0
  const isLossSloMet = metrics.traffic_loss_pct <= 0.1
  const isOptimalitySloMet = metrics.path_optimality_pct >= 95.0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', background: 'var(--bg-space)' }}>
      {/* Title Bar */}
      <header className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 24px', margin: 10, marginBottom: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Globe color="var(--sky-blue)" size={24} className="glow-text" />
          <div>
            <h1 style={{ fontFamily: 'Space Grotesk', fontSize: '1.2rem', fontWeight: 700, letterSpacing: '0.05em' }}>
              ADAPTSKEL <span style={{ color: 'var(--sky-blue)', fontWeight: 400 }}>Backbone Routing Application</span>
            </h1>
            <p style={{ fontSize: '0.65rem', color: 'var(--text-soft)' }}>
              Real-time dynamic SSSP ISP backbone simulator with Poisson-distributed link outages
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="gs-btn success" onClick={toggleSimulation} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {simActive ? <Pause size={14} /> : <Play size={14} />}
            {simActive ? 'Pause Simulation' : 'Launch Simulation'}
          </button>
          <button className="gs-btn secondary" onClick={resetSimulation} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={14} />
            Reset
          </button>
          <button className="gs-btn secondary" onClick={handleExportCSV} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Download size={14} />
            Export SLO Report
          </button>
        </div>
      </header>

      {/* Main Panel grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 340px', flex: 1, gap: 10, padding: 10, minHeight: 0 }}>
        {/* Left Side: Controls and Fiber Cuts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
          {/* Accelerator Panel */}
          <section className="glass-panel" style={{ padding: 16 }}>
            <h2 style={{ fontFamily: 'Space Grotesk', fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--sky-blue)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Layers size={14} /> Time Accelerator
            </h2>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-soft)', lineHeight: 1.4, marginBottom: 12 }}>
              Poisson outage schedules average 1 failure per 10 hours. Set Poisson mean delay to speed up event ticks.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                <span style={{ color: 'var(--text-mid)' }}>Outage Delay Interval:</span>
                <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--sky-blue)' }}>{simInterval}s</span>
              </div>
              <input
                type="range"
                min="1"
                max="30"
                step="1"
                value={simInterval}
                onChange={e => handleIntervalChange(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--sky-blue)', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.55rem', color: 'var(--text-soft)', textAlign: 'right' }}>
                Acc. Factor: ~{(400000.0 / simInterval).toLocaleString()}x
              </span>
            </div>
          </section>

          {/* Pathfinder Console */}
          <section className="glass-panel" style={{ padding: 16 }}>
            <h2 style={{ fontFamily: 'Space Grotesk', fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--sky-blue)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <MapPin size={14} /> Routing Pathfinder
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.62rem', color: 'var(--text-soft)', marginBottom: 4 }}>ORIGIN ROUTER</label>
                <select
                  className="gs-input"
                  value={selectedSource ?? ''}
                  onChange={e => setSelectedSource(e.target.value ? parseInt(e.target.value) : null)}
                  style={{ width: '100%', fontSize: '0.72rem' }}
                >
                  <option value="">-- Click on Map or Choose City --</option>
                  {nodes.map(n => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.62rem', color: 'var(--text-soft)', marginBottom: 4 }}>DESTINATION ROUTER</label>
                <select
                  className="gs-input"
                  value={selectedTarget ?? ''}
                  onChange={e => setSelectedTarget(e.target.value ? parseInt(e.target.value) : null)}
                  style={{ width: '100%', fontSize: '0.72rem' }}
                >
                  <option value="">-- Click on Map or Choose City --</option>
                  {nodes.map(n => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>

              {/* Path results cards */}
              {activePath.length > 0 && (
                <div style={{ background: 'rgba(0, 229, 255, 0.05)', border: '1px solid var(--sky-border)', borderRadius: 6, padding: 10, marginTop: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', marginBottom: 4 }}>
                    <span style={{ color: 'var(--text-soft)' }}>Latency cost:</span>
                    <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--sky-blue)', fontWeight: 600 }}>{pathDistance?.toFixed(1)} ms</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', marginBottom: 4 }}>
                    <span style={{ color: 'var(--text-soft)' }}>Bottleneck:</span>
                    <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--eco-green)', fontWeight: 600 }}>{bottleneck} Gbps</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: 'var(--text-soft)' }}>Compute Time:</span>
                    <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--text-bright)' }}>{queryTimeUs} μs</span>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Link manager list */}
          <section className="glass-panel" style={{ padding: 16, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 180 }}>
            <h2 style={{ fontFamily: 'Space Grotesk', fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--sky-blue)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={14} /> Fiber Segment Manager
            </h2>
            <p style={{ fontSize: '0.68rem', color: 'var(--text-soft)', marginBottom: 8 }}>
              Click edges on the map or cut segments manually:
            </p>
            <div style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--sky-border)', borderRadius: 6, background: 'rgba(0, 0, 0, 0.2)' }}>
              <table style={{ width: '100%', fontSize: '0.68rem', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ background: 'rgba(10, 10, 20, 0.9)', borderBottom: '1px solid var(--sky-border)' }}>
                    <th style={{ padding: 6, fontWeight: 600 }}>Segment</th>
                    <th style={{ padding: 6, fontWeight: 600, textAlign: 'center' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {edges.map((edge, idx) => {
                    const uName = nodes.find(n => n.id === edge.u)?.name || edge.u
                    const vName = nodes.find(n => n.id === edge.v)?.name || edge.v
                    const isFailed = edge.status === 'failed'
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(0, 229, 255, 0.05)', background: isFailed ? 'rgba(255, 23, 68, 0.05)' : 'none' }}>
                        <td style={{ padding: 6, color: 'var(--text-mid)' }}>
                          {uName} ↔ {vName}
                        </td>
                        <td style={{ padding: 4, textAlign: 'center' }}>
                          <button
                            onClick={() => toggleLink(edge.u, edge.v, edge.status)}
                            className="gs-btn"
                            style={{
                              fontSize: '0.55rem',
                              padding: '2px 6px',
                              background: isFailed ? 'rgba(255, 23, 68, 0.15)' : 'rgba(0, 230, 118, 0.15)',
                              color: isFailed ? 'var(--danger-red)' : 'var(--eco-green)',
                              borderColor: isFailed ? 'rgba(255, 23, 68, 0.4)' : 'rgba(0, 230, 118, 0.4)'
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
            </div>
          </section>
        </div>

        {/* Center: Interactive Leaflet Map */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="glass-panel" style={{ flex: 1, position: 'relative', overflow: 'hidden', padding: 5 }}>
            <MapContainer
              center={mapCenter}
              zoom={mapZoom}
              style={{ height: '100%', width: '100%' }}
              zoomControl={true}
              scrollWheelZoom={true}
              attributionControl={false}
            >
              <MapController center={mapCenter} zoom={mapZoom} />
              {/* Dark matter tile layer */}
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                subdomains="abcd"
              />

              {/* Render fiber polylines */}
              {edges.map((edge, idx) => {
                const nodeU = nodes.find(n => n.id === edge.u)
                const nodeV = nodes.find(n => n.id === edge.v)
                if (!nodeU || !nodeV) return null

                const isFailed = edge.status === 'failed'
                const isPathSegment = (() => {
                  for (let i = 0; i < activePath.length - 1; i++) {
                    const u = activePath[i]
                    const v = activePath[i + 1]
                    if ((u === edge.u && v === edge.v) || (u === edge.v && v === edge.u)) {
                      return true
                    }
                  }
                  return false
                })()

                // Polyline styles
                let color = 'rgba(0, 229, 255, 0.3)' // Default cold edge (F2)
                let weight = 1.5
                let dashArray = undefined

                if (isFailed) {
                  color = 'var(--danger-red)'
                  weight = 2
                  dashArray = '5, 8'
                } else if (isPathSegment) {
                  color = '#ffd700' // Gold path
                  weight = 4.5
                } else if (edge.layer === 'F1') {
                  color = 'var(--sky-blue)' // Active skeleton F1
                  weight = 2.5
                }

                return (
                  <Polyline
                    key={idx}
                    positions={[[nodeU.lat, nodeU.lon], [nodeV.lat, nodeV.lon]]}
                    color={color}
                    weight={weight}
                    dashArray={dashArray}
                    eventHandlers={{
                      click: () => toggleLink(edge.u, edge.v, edge.status)
                    }}
                  >
                    <Popup>
                      <div style={{ fontFamily: 'Inter', fontSize: '0.7rem', color: '#030307' }}>
                        <strong>{nodeU.name} ↔ {nodeV.name}</strong><br />
                        Latency: {edge.w} ms<br />
                        Capacity: {edge.capacity} Gbps<br />
                        Layer: {edge.layer}<br />
                        Status: <span style={{ color: isFailed ? 'red' : 'green', fontWeight: 600 }}>{edge.status.toUpperCase()}</span>
                      </div>
                    </Popup>
                  </Polyline>
                )
              })}

              {/* Render city nodes markers */}
              {nodes.map(city => (
                <Marker
                  key={city.id}
                  position={[city.lat, city.lon]}
                  icon={createRouterIcon(city)}
                  eventHandlers={{
                    click: () => {
                      if (selectedSource === null) {
                        setSelectedSource(city.id)
                      } else if (selectedSource === city.id) {
                        setSelectedSource(null)
                      } else if (selectedTarget === null) {
                        setSelectedTarget(city.id)
                      } else if (selectedTarget === city.id) {
                        setSelectedTarget(null)
                      } else {
                        setSelectedSource(city.id)
                        setSelectedTarget(null)
                      }
                    }
                  }}
                >
                  <Popup>
                    <div style={{ fontFamily: 'Inter', fontSize: '0.7rem', color: '#030307' }}>
                      <strong>{city.name} Router</strong><br />
                      Population: {city.population.toLocaleString()}<br />
                      ID: Node {city.id}
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>

          {/* Bottom Side: Simulation Log */}
          <section className="glass-panel" style={{ height: 160, display: 'flex', flexDirection: 'column', padding: 12 }}>
            <h2 style={{ fontFamily: 'Space Grotesk', fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-mid)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={12} /> Live Event Logger
            </h2>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4, fontFamily: 'JetBrains Mono', fontSize: '0.62rem' }}>
              {eventLog.length === 0 ? (
                <div style={{ color: 'var(--text-soft)', padding: '10px 0', textAlign: 'center' }}>Awaiting simulation outages and path events...</div>
              ) : (
                eventLog.map(log => {
                  let badgeColor = 'var(--text-soft)'
                  if (log.type === 'success') badgeColor = 'var(--eco-green)'
                  if (log.type === 'warn') badgeColor = 'var(--heat-warm)'
                  if (log.type === 'error') badgeColor = 'var(--danger-red)'

                  return (
                    <div key={log.id} className="timeline-event" style={{ display: 'flex', gap: 8, padding: '2px 4px', borderLeft: `2.5px solid ${badgeColor}`, background: 'rgba(255,255,255,0.02)' }}>
                      <span style={{ color: 'var(--text-soft)' }}>[{log.time}]</span>
                      <span style={{ color: badgeColor, fontWeight: 700 }}>{log.event}</span>
                      <span style={{ color: 'var(--text-mid)' }}>{log.message}</span>
                    </div>
                  )
                })
              )}
            </div>
          </section>
        </div>

        {/* Right Side: SLO Indicators and Telemetry Graphs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* SLO Compliance section */}
          <section className="glass-panel" style={{ padding: 16 }}>
            <h2 style={{ fontFamily: 'Space Grotesk', fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--sky-blue)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <ShieldCheck size={16} /> SLO Telemetry Console
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* SLO 1 */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0, 0, 0, 0.2)', padding: '8px 12px', borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.03)' }}>
                <div>
                  <h3 style={{ fontSize: '0.75rem', fontWeight: 600 }}>Convergence SLO</h3>
                  <p style={{ fontSize: '0.6rem', color: 'var(--text-soft)' }}>Outage re-route &lt; 10ms</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: isConvergenceSloMet ? 'var(--eco-green)' : 'var(--danger-red)', fontWeight: 600 }}>
                    {metrics.avg_convergence_ms.toFixed(3)} ms
                  </div>
                  <span style={{ fontSize: '0.55rem', padding: '1px 5px', borderRadius: 4, background: isConvergenceSloMet ? 'rgba(0,230,118,0.15)' : 'rgba(255,23,68,0.15)', color: isConvergenceSloMet ? 'var(--eco-green)' : 'var(--danger-red)', border: '1px solid' }}>
                    {isConvergenceSloMet ? 'MET' : 'VIOLATED'}
                  </span>
                </div>
              </div>

              {/* SLO 2 */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0, 0, 0, 0.2)', padding: '8px 12px', borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.03)' }}>
                <div>
                  <h3 style={{ fontSize: '0.75rem', fontWeight: 600 }}>Traffic Loss SLO</h3>
                  <p style={{ fontSize: '0.6rem', color: 'var(--text-soft)' }}>Outage packet drops &lt; 0.1%</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: isLossSloMet ? 'var(--eco-green)' : 'var(--danger-red)', fontWeight: 600 }}>
                    {metrics.traffic_loss_pct.toFixed(3)}%
                  </div>
                  <span style={{ fontSize: '0.55rem', padding: '1px 5px', borderRadius: 4, background: isLossSloMet ? 'rgba(0,230,118,0.15)' : 'rgba(255,23,68,0.15)', color: isLossSloMet ? 'var(--eco-green)' : 'var(--danger-red)', border: '1px solid' }}>
                    {isLossSloMet ? 'MET' : 'VIOLATED'}
                  </span>
                </div>
              </div>

              {/* SLO 3 */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0, 0, 0, 0.2)', padding: '8px 12px', borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.03)' }}>
                <div>
                  <h3 style={{ fontSize: '0.75rem', fontWeight: 600 }}>Path Optimality SLO</h3>
                  <p style={{ fontSize: '0.6rem', color: 'var(--text-soft)' }}>Shortest path accuracy &ge; 95%</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem', color: isOptimalitySloMet ? 'var(--eco-green)' : 'var(--danger-red)', fontWeight: 600 }}>
                    {metrics.path_optimality_pct.toFixed(1)}%
                  </div>
                  <span style={{ fontSize: '0.55rem', padding: '1px 5px', borderRadius: 4, background: isOptimalitySloMet ? 'rgba(0,230,118,0.15)' : 'rgba(255,23,68,0.15)', color: isOptimalitySloMet ? 'var(--eco-green)' : 'var(--danger-red)', border: '1px solid' }}>
                    {isOptimalitySloMet ? 'MET' : 'VIOLATED'}
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* Telemetry charts */}
          <section className="glass-panel" style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', minHeight: 250 }}>
            <h2 style={{ fontFamily: 'Space Grotesk', fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--sky-blue)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={16} /> Real-Time Telemetry Trend
            </h2>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
              {/* Convergence graph */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-soft)', marginBottom: 4 }}>CONVERGENCE TIME (MS)</span>
                <div style={{ flex: 1, background: 'rgba(0, 0, 0, 0.2)', borderRadius: 6, padding: 5 }}>
                  {chartHistory.length === 0 ? (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', color: 'var(--text-soft)' }}>
                      Awaiting metrics...
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartHistory}>
                        <XAxis dataKey="tick" hide />
                        <YAxis domain={[0, 'dataMax + 1']} fontSize={8} stroke="var(--text-soft)" />
                        <Tooltip contentStyle={{ background: '#0a0a14', border: '1px solid var(--sky-border)', fontSize: 10 }} />
                        <Line type="monotone" dataKey="convergence" stroke="var(--sky-blue)" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Traffic loss graph */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-soft)', marginBottom: 4 }}>ESTIMATED TRAFFIC LOSS (%)</span>
                <div style={{ flex: 1, background: 'rgba(0, 0, 0, 0.2)', borderRadius: 6, padding: 5 }}>
                  {chartHistory.length === 0 ? (
                    <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', color: 'var(--text-soft)' }}>
                      Awaiting metrics...
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartHistory}>
                        <XAxis dataKey="tick" hide />
                        <YAxis domain={[0, 'dataMax + 0.05']} fontSize={8} stroke="var(--text-soft)" />
                        <Tooltip contentStyle={{ background: '#0a0a14', border: '1px solid var(--sky-border)', fontSize: 10 }} />
                        <Line type="monotone" dataKey="loss" stroke="var(--danger-red)" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

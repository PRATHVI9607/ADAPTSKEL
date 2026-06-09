import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Line, Html } from '@react-three/drei'
import * as THREE from 'three'
import { useGraphStore } from '../store'
import type { Node3D, Edge3D, RoutingNode, RoutingEdge } from '../engine/GraphState'

// ── Geographic Projection for ISP Routing Mode ──────────────────────────────
export function projectGeographic(lat: number, lon: number): [number, number, number] {
  // Center map around -96 degrees Longitude and 38 degrees Latitude
  const x = (lon + 96) * 0.16
  const y = (lat - 38) * 0.22
  const z = -(x * x + y * y) * 0.025 // Curved Earth projection
  return [x, y, z]
}

// ── Curved Arc Generator for Premium 3D Connections ──────────────────────────
function getArcPoints(
  p0: [number, number, number],
  p1: [number, number, number],
  segments: number = 20
): THREE.Vector3[] {
  const start = new THREE.Vector3(...p0)
  const end = new THREE.Vector3(...p1)
  const points: THREE.Vector3[] = []

  for (let i = 0; i <= segments; i++) {
    const t = i / segments
    // Linear interpolation
    const p = new THREE.Vector3().lerpVectors(start, end, t)
    
    // Add height bow (parabolic curve peaking in the middle)
    const dist = start.distanceTo(end)
    const h = Math.sin(t * Math.PI) * dist * 0.15
    
    // Push curve outward in Z / normal direction
    p.y += h * 0.6
    p.z += h * 0.8
    points.push(p)
  }
  return points
}

// ── Colour helpers ──────────────────────────────────────────────────────────
function nodeColor(node: Node3D, onPath: boolean): string {
  if (onPath)          return '#10b981'  // neon emerald green
  if (node.heat > 0.6) return '#ef4444'  // hot red
  if (node.heat > 0.3) return '#f59e0b'  // warm amber
  return '#00d4ff'                        // electric cyan
}

function edgeColor(heat: number, inF1: boolean): THREE.Color {
  if (!inF1) return new THREE.Color('#3a3a4a')     // F₂ — dark gray-blue
  if (heat > 0.6) return new THREE.Color('#ef4444')  // very hot red
  if (heat > 0.3) return new THREE.Color('#f59e0b')  // warm amber
  return new THREE.Color('#00d4ff')                   // F₁ electric cyan
}

// ── Single node sphere ───────────────────────────────────────────────────────
function NodeSphere({ node, onPath }: { node: Node3D; onPath: boolean }) {
  const color  = nodeColor(node, onPath)
  const radius = 0.14 + node.degree * 0.02
  const scale  = onPath ? 1.4 : 1.0

  return (
    <group position={[node.x, node.y, node.z]}>
      {/* Glow aura */}
      <mesh scale={scale * 2.0}>
        <sphereGeometry args={[radius, 16, 12]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={onPath ? 0.22 : 0.07}
        />
      </mesh>

      {/* Core sphere */}
      <mesh scale={scale}>
        <sphereGeometry args={[radius, 16, 12]} />
        <meshStandardMaterial
          color={color}
          roughness={0.1}
          metalness={0.8}
          emissive={color}
          emissiveIntensity={onPath ? 0.8 : 0.3}
        />
      </mesh>

      <Html
        center
        distanceFactor={9}
        style={{ pointerEvents: 'none' }}
        position={[0, radius * scale + 0.18, 0]}
      >
        <div
          style={{
            background: 'rgba(5, 5, 10, 0.85)',
            color: color,
            borderRadius: '50%',
            width: 18,
            height: 18,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 9,
            fontWeight: 700,
            fontFamily: 'JetBrains Mono, monospace',
            border: `1.5px solid ${color}`,
            boxShadow: '0 0 8px rgba(0,212,255,0.3)',
            userSelect: 'none',
          }}
        >
          {node.id}
        </div>
      </Html>
    </group>
  )
}

// ── Routing Node sphere (Mode 6) ─────────────────────────────────────────────
function RoutingNodeSphere({ node, onPath }: { node: RoutingNode; onPath: boolean }) {
  const isFailed = node.status === 'failed'
  
  const color = isFailed 
    ? '#ef4444' // red
    : (onPath ? '#10b981' : '#00d4ff') // green / cyan

  const pos = projectGeographic(node.lat, node.lon)
  const radius = 0.12
  const scale = onPath ? 1.4 : 1.0

  return (
    <group position={pos}>
      {/* Glow aura */}
      <mesh scale={scale * 2.2}>
        <sphereGeometry args={[radius, 16, 12]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={onPath ? 0.25 : 0.08}
        />
      </mesh>

      {/* Core sphere */}
      <mesh scale={scale}>
        <sphereGeometry args={[radius, 16, 12]} />
        <meshStandardMaterial
          color={color}
          roughness={0.1}
          metalness={0.8}
          emissive={color}
          emissiveIntensity={onPath ? 0.9 : 0.3}
        />
      </mesh>

      <Html
        center
        distanceFactor={10}
        style={{ pointerEvents: 'none' }}
        position={[0, radius * scale + 0.18, 0]}
      >
        <div
          style={{
            background: 'rgba(5, 5, 10, 0.85)',
            backdropFilter: 'blur(4px)',
            color: color,
            padding: '2px 6px',
            borderRadius: 6,
            fontSize: 8,
            fontWeight: 700,
            fontFamily: 'Space Grotesk, sans-serif',
            border: `1px solid ${color}88`,
            boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
            whiteSpace: 'nowrap',
            userSelect: 'none',
          }}
        >
          {node.name}
        </div>
      </Html>
    </group>
  )
}

// ── Node Layer Router ────────────────────────────────────────────────────────
function NodeLayer() {
  const mode = useGraphStore(s => s.mode)
  const nodes = useGraphStore(s => [...s.nodes.values()])
  const hotPath = useGraphStore(s => s.hotPath)
  const pathSet = useMemo(() => new Set(hotPath), [hotPath])

  // Routing mode states
  const routingNodes = useGraphStore(s => s.routingNodes)
  const routingPath = useGraphStore(s => s.routingPath)
  const rPathSet = useMemo(() => new Set(routingPath), [routingPath])

  if (mode === 'routing') {
    return (
      <group>
        {routingNodes.map(n => (
          <RoutingNodeSphere key={n.id} node={n} onPath={rPathSet.has(n.id)} />
        ))}
      </group>
    )
  }

  return (
    <group>
      {nodes.map(n => (
        <NodeSphere key={n.id} node={n} onPath={pathSet.has(n.id)} />
      ))}
    </group>
  )
}

// ── Edge lines ───────────────────────────────────────────────────────────────
function EdgeLines() {
  const mode = useGraphStore(s => s.mode)
  const edges = useGraphStore(s => [...s.edges.values()])
  const skeletonEdges = useGraphStore(s => s.skeletonEdges)
  const nodes = useGraphStore(s => s.nodes)
  const showF1 = useGraphStore(s => s.showF1)
  const showF2 = useGraphStore(s => s.showF2)

  // Routing Mode states
  const routingEdges = useGraphStore(s => s.routingEdges)
  const routingNodes = useGraphStore(s => s.routingNodes)
  const rNodeMap = useMemo(() => new Map(routingNodes.map(n => [n.id, n])), [routingNodes])

  // Compute curved arcs for routing topology
  const routingArcs = useMemo(() => {
    if (mode !== 'routing') return []
    return routingEdges.map(edge => {
      const uNode = rNodeMap.get(edge.u)
      const vNode = rNodeMap.get(edge.v)
      if (!uNode || !vNode) return null

      const p0 = projectGeographic(uNode.lat, uNode.lon)
      const p1 = projectGeographic(vNode.lat, vNode.lon)
      const arcPoints = getArcPoints(p0, p1, 16)
      const isFailed = edge.status === 'failed'

      return {
        id: `${edge.u}-${edge.v}`,
        points: arcPoints,
        layer: edge.layer,
        status: edge.status,
        color: isFailed ? '#ef4444' : (edge.layer === 'F1' ? '#00d4ff' : '#2a2a35')
      }
    }).filter(Boolean)
  }, [mode, routingEdges, rNodeMap])

  // Standard edges
  const { f1Lines, f2Lines } = useMemo(() => {
    const f1: Array<{ p0: THREE.Vector3; p1: THREE.Vector3; color: THREE.Color }> = []
    const f2: Array<{ p0: THREE.Vector3; p1: THREE.Vector3 }> = []

    if (mode === 'routing') return { f1Lines: f1, f2Lines: f2 }

    for (const edge of edges) {
      const nu = nodes.get(edge.u)
      const nv = nodes.get(edge.v)
      if (!nu || !nv) continue

      const p0 = new THREE.Vector3(nu.x, nu.y, nu.z)
      const p1 = new THREE.Vector3(nv.x, nv.y, nv.z)

      if (skeletonEdges.has(edge.id)) {
        f1.push({ p0, p1, color: edgeColor(edge.heat, true) })
      } else {
        f2.push({ p0, p1 })
      }
    }
    return { f1Lines: f1, f2Lines: f2 }
  }, [mode, edges, nodes, skeletonEdges])

  if (mode === 'routing') {
    return (
      <group>
        {routingArcs.map((arc: any) => {
          const isF1 = arc.layer === 'F1'
          const isFailed = arc.status === 'failed'
          if (isF1 && !showF1) return null
          if (!isF1 && !showF2) return null

          return (
            <Line
              key={arc.id}
              points={arc.points}
              color={arc.color}
              lineWidth={isFailed ? 1.0 : (isF1 ? 2.2 : 0.8)}
              transparent
              opacity={isFailed ? 0.3 : (isF1 ? 0.95 : 0.4)}
              dashed={isFailed}
              dashSize={0.2}
              gapSize={0.1}
            />
          )
        })}
      </group>
    )
  }

  return (
    <group>
      {showF2 && f2Lines.map(({ p0, p1 }, i) => (
        <Line
          key={`f2-${i}`}
          points={[p0, p1]}
          color="#333346"
          lineWidth={0.8}
          transparent
          opacity={0.55}
        />
      ))}
      {showF1 && f1Lines.map(({ p0, p1, color }, i) => (
        <Line
          key={`f1-${i}`}
          points={[p0, p1]}
          color={color}
          lineWidth={2.2}
          transparent
          opacity={0.95}
        />
      ))}
    </group>
  )
}

// ── Hot / shortest path line ─────────────────────────────────────────────────
function HotPathLine() {
  const mode = useGraphStore(s => s.mode)
  const hotPath = useGraphStore(s => s.hotPath)
  const nodes = useGraphStore(s => s.nodes)

  // Routing Mode states
  const routingPath = useGraphStore(s => s.routingPath)
  const routingNodes = useGraphStore(s => s.routingNodes)
  const rNodeMap = useMemo(() => new Map(routingNodes.map(n => [n.id, n])), [routingNodes])

  // Curved path segments in routing mode
  const routingPathPoints = useMemo(() => {
    if (mode !== 'routing' || routingPath.length < 2) return []
    const pts: THREE.Vector3[] = []
    
    for (let i = 0; i < routingPath.length - 1; i++) {
      const uNode = rNodeMap.get(routingPath[i])
      const vNode = rNodeMap.get(routingPath[i + 1])
      if (!uNode || !vNode) continue
      
      const p0 = projectGeographic(uNode.lat, uNode.lon)
      const p1 = projectGeographic(vNode.lat, vNode.lon)
      const arc = getArcPoints(p0, p1, 12)
      // Append points excluding the last to avoid double endpoints
      pts.push(...arc.slice(0, -1))
    }
    // Append final node position
    const lastNode = rNodeMap.get(routingPath[routingPath.length - 1])
    if (lastNode) {
      const lp = projectGeographic(lastNode.lat, lastNode.lon)
      pts.push(new THREE.Vector3(...lp))
    }
    return pts
  }, [mode, routingPath, rNodeMap])

  // Standard path points
  const points = useMemo(() => {
    if (mode === 'routing') return []
    const pts: THREE.Vector3[] = []
    for (const id of hotPath) {
      const n = nodes.get(id)
      if (n) pts.push(new THREE.Vector3(n.x, n.y, n.z))
    }
    return pts
  }, [mode, hotPath, nodes])

  if (mode === 'routing') {
    if (routingPathPoints.length < 2) return null
    return (
      <Line
        points={routingPathPoints}
        color="#10b981" // emerald green
        lineWidth={3.8}
        transparent
        opacity={0.95}
      />
    )
  }

  if (points.length < 2) return null

  return (
    <Line
      points={points}
      color="#10b981"
      lineWidth={3.5}
      dashed
      dashSize={0.3}
      gapSize={0.12}
      transparent
      opacity={0.95}
    />
  )
}

// ── Path edge weight labels ──────────────────────────────────────────────────
function PathEdgeLabels() {
  const mode = useGraphStore(s => s.mode)
  const hotPath = useGraphStore(s => s.hotPath)
  const nodes = useGraphStore(s => s.nodes)
  const edges = useGraphStore(s => s.edges)

  // Routing Mode states
  const routingPath = useGraphStore(s => s.routingPath)
  const routingNodes = useGraphStore(s => s.routingNodes)
  const routingEdges = useGraphStore(s => s.routingEdges)
  const rNodeMap = useMemo(() => new Map(routingNodes.map(n => [n.id, n])), [routingNodes])
  const rEdgeMap = useMemo(() => new Map(routingEdges.map(e => [`${Math.min(e.u, e.v)}-${Math.max(e.u, e.v)}`, e])), [routingEdges])

  const labels = useMemo(() => {
    const items: Array<{ pos: THREE.Vector3; weight: number; key: string }> = []
    
    if (mode === 'routing') {
      for (let i = 0; i < routingPath.length - 1; i++) {
        const a = routingPath[i], b = routingPath[i + 1]
        const na = rNodeMap.get(a), nb = rNodeMap.get(b)
        if (!na || !nb) continue

        const key = `${Math.min(a, b)}-${Math.max(a, b)}`
        const edge = rEdgeMap.get(key)
        if (!edge) continue

        const p0 = projectGeographic(na.lat, na.lon)
        const p1 = projectGeographic(nb.lat, nb.lon)
        
        // Midpoint of arc
        const midX = (p0[0] + p1[0]) / 2
        const midY = (p0[1] + p1[1]) / 2 + 0.1
        const midZ = (p0[2] + p1[2]) / 2 + 0.2 // raise labels slightly

        items.push({
          pos: new THREE.Vector3(midX, midY, midZ),
          weight: edge.w,
          key: `r-${a}-${b}`
        })
      }
      return items
    }

    for (let i = 0; i < hotPath.length - 1; i++) {
      const a = hotPath[i], b = hotPath[i + 1]
      const na = nodes.get(a), nb = nodes.get(b)
      if (!na || !nb) continue
      const key = `${Math.min(a, b)}-${Math.max(a, b)}`
      const edge = edges.get(key)
      if (!edge) continue
      const mid = new THREE.Vector3(
        (na.x + nb.x) / 2,
        (na.y + nb.y) / 2 + 0.18,
        (na.z + nb.z) / 2,
      )
      items.push({ pos: mid, weight: edge.w, key: `${a}-${b}` })
    }
    return items
  }, [mode, hotPath, nodes, edges, routingPath, rNodeMap, rEdgeMap])

  return (
    <>
      {labels.map(({ pos, weight, key }) => (
        <Html key={key} position={pos.toArray()} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
          <div
            style={{
              background: 'rgba(5, 5, 10, 0.9)',
              border: '1.2px solid #10b981',
              borderRadius: 5,
              padding: '1px 5px',
              fontSize: 8,
              fontWeight: 700,
              fontFamily: 'JetBrains Mono, monospace',
              color: '#10b981',
              whiteSpace: 'nowrap',
              boxShadow: '0 2px 6px rgba(0,0,0,0.5)',
              userSelect: 'none',
            }}
          >
            {weight} ms
          </div>
        </Html>
      ))}
    </>
  )
}

// ── Scene lighting (optimized for dark glowing elements) ──────────────────────
function SceneLights() {
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[10, 10, 5]} intensity={0.5} color="#ffffff" />
      <pointLight position={[0, 0, 5]} intensity={0.4} color="#00d4ff" />
    </>
  )
}

// ── Legend overlay on canvas ─────────────────────────────────────────────────
function CanvasLegend() {
  const showF1 = useGraphStore(s => s.showF1)
  const showF2 = useGraphStore(s => s.showF2)
  const mode = useGraphStore(s => s.mode)
  const pathActive = useGraphStore(s => mode === 'routing' ? s.routingPath.length > 0 : s.hotPath.length > 0)

  return (
    <div
      style={{
        position: 'absolute', bottom: 12, left: 12,
        display: 'flex', flexDirection: 'column', gap: 5,
        zIndex: 20, pointerEvents: 'none',
      }}
    >
      {showF1 && (
        <LegendItem color="#00d4ff" label="F₁ Skeleton (hot fiber)" />
      )}
      {showF2 && (
        <LegendItem color="#333346" label="F₂ Residual (cold fiber)" />
      )}
      {pathActive && (
        <LegendItem color="#10b981" label="Active Shortest Path" />
      )}
      {mode === 'routing' && (
        <LegendItem color="#ef4444" label="Failed Link Segment (cut)" dashed />
      )}
    </div>
  )
}

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <div
        style={{
          width: 24, height: 3,
          background: dashed
            ? `repeating-linear-gradient(90deg, ${color} 0px, ${color} 6px, transparent 6px, transparent 10px)`
            : color,
          borderRadius: 2, flexShrink: 0,
        }}
      />
      <span
        style={{
          fontFamily: 'Space Grotesk, sans-serif',
          fontSize: 9,
          fontWeight: 600,
          color: 'var(--text-soft)',
          background: 'rgba(5, 5, 10, 0.75)',
          border: '1px solid var(--sky-border)',
          padding: '2px 6px',
          borderRadius: 4,
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </span>
    </div>
  )
}

// ── Orbit Camera Control ─────────────────────────────────────────────────────
function CameraRig() {
  const { camera } = useThree()
  const tick = useRef(0)
  const interacted = useRef(false)
  const mode = useGraphStore(s => s.mode)

  useEffect(() => {
    // Snap camera perspective for maps vs abstract graphs
    if (mode === 'routing') {
      camera.position.set(0, 0, 9)
    } else {
      camera.position.set(0, 2, 12)
    }
    camera.lookAt(0, 0, 0)
    interacted.current = false
  }, [camera, mode])

  useFrame((_, dt) => {
    if (interacted.current || mode === 'routing') return
    tick.current += dt * 0.04
    camera.position.x = Math.sin(tick.current) * 12
    camera.position.z = Math.cos(tick.current) * 12
    camera.lookAt(0, 0, 0)
  })

  return (
    <OrbitControls
      enableDamping
      dampingFactor={0.07}
      minDistance={4}
      maxDistance={25}
      enablePan={mode === 'routing'}
      onStart={() => { interacted.current = true }}
    />
  )
}

// ── Main Canvas export ───────────────────────────────────────────────────────
export function GraphCanvas3D() {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Canvas
        style={{ width: '100%', height: '100%' }}
        camera={{ position: [0, 2, 12], fov: 55 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={['#030307']} />
        <SceneLights />
        <NodeLayer />
        <EdgeLines />
        <HotPathLine />
        <PathEdgeLabels />
        <CameraRig />
      </Canvas>

      <CanvasLegend />
    </div>
  )
}

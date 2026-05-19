import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Line, Html } from '@react-three/drei'
import * as THREE from 'three'
import { useGraphStore } from '../store'
import type { Node3D, Edge3D } from '../engine/GraphState'

// ── Colour helpers ──────────────────────────────────────────────────────────
function nodeColor(node: Node3D, onPath: boolean): string {
  if (onPath)          return '#16a34a'  // eco green — on shortest path
  if (node.heat > 0.6) return '#dc2626'  // hot red
  if (node.heat > 0.35) return '#d97706' // warm amber
  return '#1d6fb5'                        // default sky blue
}

function edgeColor(heat: number, inF1: boolean): THREE.Color {
  if (!inF1) return new THREE.Color('#c8daea')     // F₂ — pale blue-gray
  if (heat > 0.6) return new THREE.Color('#dc2626')  // very hot
  if (heat > 0.3) return new THREE.Color('#d97706')  // warm
  return new THREE.Color('#1d6fb5')                   // F₁ default sky blue
}

// ── Single node sphere + HTML label ────────────────────────────────────────
function NodeSphere({ node, onPath }: { node: Node3D; onPath: boolean }) {
  const color  = nodeColor(node, onPath)
  const radius = 0.18 + node.degree * 0.025
  const scale  = onPath ? 1.35 : 1.0

  return (
    <group position={[node.x, node.y, node.z]}>
      {/* Glow ring for path nodes */}
      {onPath && (
        <mesh scale={scale * 2.5}>
          <sphereGeometry args={[radius, 16, 12]} />
          <meshStandardMaterial
            color="#16a34a"
            transparent
            opacity={0.12}
            side={THREE.BackSide}
          />
        </mesh>
      )}

      {/* Main sphere */}
      <mesh scale={scale}>
        <sphereGeometry args={[radius, 16, 12]} />
        <meshStandardMaterial
          color={color}
          roughness={0.25}
          metalness={0.15}
          emissive={color}
          emissiveIntensity={onPath ? 0.25 : 0.08}
        />
      </mesh>

      {/* Node ID label — always visible, scales with distance */}
      <Html
        center
        distanceFactor={10}
        style={{ pointerEvents: 'none' }}
        position={[0, radius * scale + 0.18, 0]}
      >
        <div
          style={{
            background: color,
            color: '#ffffff',
            borderRadius: '50%',
            width: 20,
            height: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 10,
            fontWeight: 700,
            fontFamily: 'JetBrains Mono, monospace',
            border: '2px solid white',
            boxShadow: '0 1px 5px rgba(0,0,0,0.22)',
            whiteSpace: 'nowrap',
            userSelect: 'none',
          }}
        >
          {node.id}
        </div>
      </Html>
    </group>
  )
}

// ── Node layer ──────────────────────────────────────────────────────────────
function NodeLayer() {
  const nodes   = useGraphStore(s => [...s.nodes.values()])
  const hotPath = useGraphStore(s => s.hotPath)
  const pathSet = useMemo(() => new Set(hotPath), [hotPath])

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
  const edges        = useGraphStore(s => [...s.edges.values()])
  const skeletonEdges = useGraphStore(s => s.skeletonEdges)
  const nodes        = useGraphStore(s => s.nodes)
  const showF1       = useGraphStore(s => s.showF1)
  const showF2       = useGraphStore(s => s.showF2)

  const { f1Lines, f2Lines } = useMemo(() => {
    const f1: Array<{ p0: THREE.Vector3; p1: THREE.Vector3; color: THREE.Color }> = []
    const f2: Array<{ p0: THREE.Vector3; p1: THREE.Vector3 }> = []

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
  }, [edges, nodes, skeletonEdges])

  return (
    <group>
      {showF2 && f2Lines.map(({ p0, p1 }, i) => (
        <Line
          key={`f2-${i}`}
          points={[p0, p1]}
          color="#b8d0e8"
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
          opacity={0.9}
        />
      ))}
    </group>
  )
}

// ── Hot / shortest path line ─────────────────────────────────────────────────
function HotPathLine() {
  const hotPath = useGraphStore(s => s.hotPath)
  const nodes   = useGraphStore(s => s.nodes)

  const points = useMemo(() => {
    const pts: THREE.Vector3[] = []
    for (const id of hotPath) {
      const n = nodes.get(id)
      if (n) pts.push(new THREE.Vector3(n.x, n.y, n.z))
    }
    return pts
  }, [hotPath, nodes])

  if (points.length < 2) return null

  return (
    <Line
      points={points}
      color="#16a34a"
      lineWidth={4}
      dashed
      dashSize={0.35}
      gapSize={0.14}
      transparent
      opacity={0.95}
    />
  )
}

// ── Edge weight labels on the path ──────────────────────────────────────────
function PathEdgeLabels() {
  const hotPath = useGraphStore(s => s.hotPath)
  const nodes   = useGraphStore(s => s.nodes)
  const edges   = useGraphStore(s => s.edges)

  const labels = useMemo(() => {
    const items: Array<{ pos: THREE.Vector3; weight: number }> = []
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
      items.push({ pos: mid, weight: edge.w })
    }
    return items
  }, [hotPath, nodes, edges])

  return (
    <>
      {labels.map(({ pos, weight }, i) => (
        <Html key={i} position={pos.toArray()} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
          <div
            style={{
              background: '#ffffff',
              border: '1.5px solid #16a34a',
              borderRadius: 5,
              padding: '1px 5px',
              fontSize: 9,
              fontWeight: 600,
              fontFamily: 'JetBrains Mono, monospace',
              color: '#15803d',
              whiteSpace: 'nowrap',
              boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
              userSelect: 'none',
            }}
          >
            {weight}
          </div>
        </Html>
      ))}
    </>
  )
}

// ── Scene lighting (soft white for light theme) ──────────────────────────────
function SceneLights() {
  return (
    <>
      <ambientLight intensity={1.1} />
      <directionalLight position={[8, 12, 8]}  intensity={0.6} color="#ffffff" />
      <directionalLight position={[-6, -4, -6]} intensity={0.25} color="#ddeeff" />
    </>
  )
}

// ── Legend overlay on canvas ─────────────────────────────────────────────────
function CanvasLegend() {
  const showF1 = useGraphStore(s => s.showF1)
  const showF2 = useGraphStore(s => s.showF2)
  const hotPath = useGraphStore(s => s.hotPath)

  return (
    <div
      style={{
        position: 'absolute', bottom: 12, left: 12,
        display: 'flex', flexDirection: 'column', gap: 5,
        zIndex: 20, pointerEvents: 'none',
      }}
    >
      {showF1 && (
        <LegendItem color="#1d6fb5" label="F₁ Skeleton (hot edges)" />
      )}
      {showF2 && (
        <LegendItem color="#b8d0e8" label="F₂ Residual (cold edges)" />
      )}
      {hotPath.length > 0 && (
        <LegendItem color="#16a34a" label="Shortest Path" dashed />
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
          fontSize: 10,
          fontWeight: 500,
          color: '#334e6b',
          background: 'rgba(255,255,255,0.85)',
          padding: '1px 5px',
          borderRadius: 4,
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </span>
    </div>
  )
}

// ── Slow auto-rotate (stops when user interacts) ─────────────────────────────
function CameraRig() {
  const { camera } = useThree()
  const tick = useRef(0)
  const interacted = useRef(false)

  useEffect(() => {
    camera.position.set(0, 2, 13)
    camera.lookAt(0, 0, 0)
  }, [camera])

  useFrame((_, dt) => {
    if (interacted.current) return
    tick.current += dt * 0.04
    camera.position.x = Math.sin(tick.current) * 13
    camera.position.z = Math.cos(tick.current) * 13
    camera.lookAt(0, 0, 0)
  })

  return (
    <OrbitControls
      enableDamping
      dampingFactor={0.1}
      minDistance={5}
      maxDistance={28}
      enablePan={false}
      onStart={() => { interacted.current = true }}
    />
  )
}

// ── Main export ──────────────────────────────────────────────────────────────
export function GraphCanvas3D() {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Canvas
        style={{ width: '100%', height: '100%' }}
        camera={{ position: [0, 2, 13], fov: 58 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={['#eef5fb']} />
        <SceneLights />
        <NodeLayer />
        <EdgeLines />
        <HotPathLine />
        <PathEdgeLabels />
        <CameraRig />
      </Canvas>

      {/* 2D overlay legend */}
      <CanvasLegend />
    </div>
  )
}

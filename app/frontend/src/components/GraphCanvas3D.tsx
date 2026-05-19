import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Stars, Line } from '@react-three/drei'
import * as THREE from 'three'
import { useGraphStore } from '../store'
import type { Node3D, Edge3D } from '../engine/GraphState'

// ── Colour helpers ──────────────────────────────────────────────────────────
function heatColor(heat: number, inF1: boolean): THREE.Color {
  if (inF1) {
    // F₁: blue → amber → red based on heat
    if (heat < 0.5) {
      return new THREE.Color().lerpColors(
        new THREE.Color('#00d4ff'),
        new THREE.Color('#ff8c00'),
        heat * 2
      )
    } else {
      return new THREE.Color().lerpColors(
        new THREE.Color('#ff8c00'),
        new THREE.Color('#ff3300'),
        (heat - 0.5) * 2
      )
    }
  }
  // F₂: cold ghost
  return new THREE.Color('#9090a0')
}

function nodeColor(node: Node3D): THREE.Color {
  if (node.heat > 0.6) return new THREE.Color('#ff3300')
  if (node.heat > 0.3) return new THREE.Color('#ff8c00')
  return new THREE.Color('#e0e8ff')
}

// ── InstancedMesh for nodes ─────────────────────────────────────────────────
function NodeMesh() {
  const nodes    = useGraphStore(s => [...s.nodes.values()])
  const hotPath  = useGraphStore(s => s.hotPath)
  const meshRef  = useRef<THREE.InstancedMesh>(null!)
  const colorRef = useRef<THREE.InstancedMesh>(null!)

  const maxNodes = 200
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const colorArr = useMemo(() => new Float32Array(maxNodes * 3), [])

  useFrame(() => {
    const mesh = meshRef.current
    if (!mesh) return

    nodes.slice(0, maxNodes).forEach((n, i) => {
      dummy.position.set(n.x, n.y, n.z)
      const onPath = hotPath.includes(n.id)
      const scale = onPath ? 0.22 + n.degree * 0.015 : 0.12 + n.degree * 0.012
      dummy.scale.setScalar(scale)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)

      const c = onPath ? new THREE.Color('#ffd700') : nodeColor(n)
      c.toArray(colorArr, i * 3)
      mesh.setColorAt(i, c)
    })

    mesh.count = Math.min(nodes.length, maxNodes)
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  })

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, maxNodes]} frustumCulled={false}>
      <sphereGeometry args={[1, 12, 8]} />
      <meshStandardMaterial
        vertexColors
        emissive="#00d4ff"
        emissiveIntensity={0.4}
        roughness={0.2}
        metalness={0.6}
      />
    </instancedMesh>
  )
}

// ── Individual edge lines ────────────────────────────────────────────────────
function EdgeLines() {
  const edges        = useGraphStore(s => [...s.edges.values()])
  const skeletonEdges = useGraphStore(s => s.skeletonEdges)
  const nodes        = useGraphStore(s => s.nodes)
  const showF1       = useGraphStore(s => s.showF1)
  const showF2       = useGraphStore(s => s.showF2)

  const { f1Lines, f2Lines } = useMemo(() => {
    const f1: Array<[THREE.Vector3, THREE.Vector3, THREE.Color]> = []
    const f2: Array<[THREE.Vector3, THREE.Vector3]> = []

    for (const edge of edges) {
      const nu = nodes.get(edge.u)
      const nv = nodes.get(edge.v)
      if (!nu || !nv) continue

      const p0 = new THREE.Vector3(nu.x, nu.y, nu.z)
      const p1 = new THREE.Vector3(nv.x, nv.y, nv.z)

      if (skeletonEdges.has(edge.id)) {
        f1.push([p0, p1, heatColor(edge.heat, true)])
      } else {
        f2.push([p0, p1])
      }
    }
    return { f1Lines: f1, f2Lines: f2 }
  }, [edges, nodes, skeletonEdges])

  return (
    <group>
      {showF1 && f1Lines.map(([p0, p1, color], i) => (
        <Line
          key={`f1-${i}`}
          points={[p0, p1]}
          color={color}
          lineWidth={1.8}
          transparent
          opacity={0.9}
        />
      ))}
      {showF2 && f2Lines.map(([p0, p1], i) => (
        <Line
          key={`f2-${i}`}
          points={[p0, p1]}
          color="#9090a0"
          lineWidth={0.6}
          transparent
          opacity={0.25}
        />
      ))}
    </group>
  )
}

// ── Animated gold path ───────────────────────────────────────────────────────
function HotPathLine() {
  const hotPath = useGraphStore(s => s.hotPath)
  const nodes   = useGraphStore(s => s.nodes)
  const timeRef = useRef(0)

  useFrame((_, dt) => {
    timeRef.current += dt
  })

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
      color="#ffd700"
      lineWidth={3}
      dashed
      dashSize={0.3}
      gapSize={0.15}
      transparent
      opacity={0.95}
    />
  )
}

// ── Scene lighting ───────────────────────────────────────────────────────────
function SceneLights() {
  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight position={[10, 10, 10]} intensity={1.2} color="#00d4ff" />
      <pointLight position={[-10, -5, -8]} intensity={0.8} color="#0040ff" />
      <pointLight position={[0, -10, 5]}   intensity={0.5} color="#ff8c00" />
    </>
  )
}

// ── Auto-rotate helper ───────────────────────────────────────────────────────
function CameraRig() {
  const { camera } = useThree()
  const tick = useRef(0)

  useEffect(() => {
    camera.position.set(0, 0, 12)
  }, [camera])

  useFrame((_, dt) => {
    tick.current += dt * 0.08
    camera.position.x = Math.sin(tick.current) * 12
    camera.position.z = Math.cos(tick.current) * 12
    camera.lookAt(0, 0, 0)
  })

  return null
}

// ── Main export ──────────────────────────────────────────────────────────────
export function GraphCanvas3D() {
  return (
    <Canvas
      style={{ width: '100%', height: '100%', background: '#0a0a0f' }}
      camera={{ position: [0, 0, 12], fov: 60 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: false }}
    >
      <color attach="background" args={['#0a0a0f']} />
      <SceneLights />
      <Stars radius={60} depth={40} count={4000} factor={3} saturation={0} fade speed={0.5} />
      <NodeMesh />
      <EdgeLines />
      <HotPathLine />
      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        minDistance={4}
        maxDistance={30}
        enablePan={false}
      />
    </Canvas>
  )
}

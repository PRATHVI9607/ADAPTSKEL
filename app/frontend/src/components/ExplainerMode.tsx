import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronLeft, ChevronRight, Play, RotateCcw } from 'lucide-react'

type OpType = 'INSERT' | 'DELETE' | 'QUERY'

interface Step {
  title: string
  description: string
  highlight: string
  cost?: string
}

const STEPS: Record<OpType, Step[]> = {
  INSERT: [
    {
      title: 'New Edge Arrives',
      description: 'Edge (u, v, w) is received from the update stream.',
      highlight: 'The edge weight w defines the path cost between vertices u and v.',
      cost: 'O(1)',
    },
    {
      title: 'Added to F₂ (Cold Layer)',
      description: 'The new edge is initially placed in F₂, the cold skeleton layer.',
      highlight: 'F₂ holds edges that are not yet part of the spanning-tree skeleton.',
      cost: 'O(1)',
    },
    {
      title: 'Connectivity Check in F₁',
      description: 'We check whether u and v are already connected in F₁.',
      highlight: 'If connected: the new edge is non-tree. If disconnected: it bridges a gap.',
      cost: 'O(log n) (LCT)',
    },
    {
      title: 'DECREASE Event Queued',
      description: 'A DECREASE event relaxes distances outward from the changed edge.',
      highlight: 'Only vertices whose distance actually improves are touched (output-sensitive).',
      cost: 'output-sensitive',
    },
    {
      title: 'Done ✓',
      description: 'Edge insertion complete. The skeleton self-adjusts lazily on next query.',
      highlight: 'Distance repair is output-sensitive — faster than a full Dijkstra rerun when the change is local.',
      cost: 'output-sensitive',
    },
  ],
  DELETE: [
    {
      title: 'Edge Removal Request',
      description: 'Edge (u, v) is marked for deletion from the graph.',
      highlight: 'The algorithm must determine if this edge is part of F₁ or only in F₂.',
    },
    {
      title: 'Was This an F₁ Skeleton Edge?',
      description: 'If the edge is in F₂ (cold layer), simply remove it — no structural change.',
      highlight: 'F₂ deletions are O(1). Only F₁ deletions require expensive repairs.',
      cost: 'F₂: O(1)',
    },
    {
      title: 'F₁ Split Detected',
      description: 'Removing an F₁ tree edge splits its tree component into two parts T₁ and T₂.',
      highlight: 'We must search F₂ for a "replacement" edge that reconnects T₁ and T₂.',
      cost: 'O(log² n) amortised (Holm)',
    },
    {
      title: 'Scanning F₂ for Replacement',
      description: 'F₂ edges crossing the (T₁, T₂) cut are searched via the Holm level structure.',
      highlight: 'The ETT + level trick bounds the total replacement-search cost to O(log² n) amortised.',
      cost: 'O(log² n) amortised',
    },
    {
      title: 'Replacement Promoted to F₁',
      description: 'The minimum-weight replacement edge is promoted from F₂ to F₁, restoring connectivity.',
      highlight: 'The demoted edges remain in F₂ as candidates for future promotions.',
      cost: 'O(log n)',
    },
    {
      title: 'Done ✓',
      description: 'Deletion complete. F₁ skeleton is again a spanning forest.',
      highlight: 'Distance repair (Ramalingam–Reps) touches only affected vertices — faster than a full rerun when the change is local.',
      cost: 'output-sensitive',
    },
  ],
  QUERY: [
    {
      title: 'Query(s, t) Received',
      description: 'A shortest-path query from the fixed source s to target t arrives.',
      highlight: 'The source distance is a label maintained incrementally — no recomputation needed.',
      cost: 'O(1)',
    },
    {
      title: 'Pending Updates Already Applied',
      description: 'Distance labels were repaired incrementally at insert/delete time, so the label is current.',
      highlight: 'Increase events are applied eagerly so a query never reads a stale (too-small) distance.',
      cost: 'O(1)',
    },
    {
      title: 'Read the Maintained Label',
      description: 'The source→t distance is read directly from the label table; the route is reconstructed via predecessors.',
      highlight: 'Distance is O(1); reconstructing the actual path costs O(path length). Arbitrary-pair (s≠source) queries fall back to one Dijkstra.',
      cost: 'O(1) distance · O(path length) route',
    },
    {
      title: 'Heat Scores Updated',
      description: 'Query edges receive a heat-score boost. Hot edges stay in F₁; cold edges are demoted.',
      highlight: 'The Zipf-skewed access pattern means a small fraction of edges handles most queries.',
      cost: 'O(path length)',
    },
  ],
}

const OP_COLORS: Record<OpType, string> = {
  INSERT: 'var(--insert-green)',
  DELETE: 'var(--delete-red)',
  QUERY:  'var(--path-gold)',
}

export function ExplainerMode() {
  const [op, setOp]         = useState<OpType>('INSERT')
  const [step, setStep]     = useState(0)
  const [playing, setPlaying] = useState(false)

  const steps  = STEPS[op]
  const current = steps[step]
  const isLast  = step === steps.length - 1
  const isFirst = step === 0

  const handleOp = (o: OpType) => { setOp(o); setStep(0) }
  const prev     = () => setStep(s => Math.max(0, s - 1))
  const next     = () => setStep(s => Math.min(steps.length - 1, s + 1))
  const reset    = () => { setStep(0); setPlaying(false) }

  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'flex-end',
      padding: 16,
      pointerEvents: 'none',
    }}>
      <motion.div
        className="glass-panel"
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        style={{ padding: 18, maxWidth: 520, width: '100%', margin: '0 auto', pointerEvents: 'all' }}
      >
        {/* Op selector */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          {(['INSERT','DELETE','QUERY'] as OpType[]).map(o => (
            <button key={o} type="button" className="gs-btn"
              onClick={() => handleOp(o)}
              style={{
                flex: 1,
                color: OP_COLORS[o],
                borderColor: op === o ? OP_COLORS[o] : 'var(--glass-border)',
                background: op === o ? `${OP_COLORS[o]}18` : 'transparent',
                fontWeight: op === o ? 700 : 400,
              }}>
              {o}
            </button>
          ))}
        </div>

        {/* Step progress */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 14 }}>
          {steps.map((_, i) => (
            <div key={i}
              style={{
                flex: 1,
                height: 3,
                borderRadius: 2,
                background: i <= step ? OP_COLORS[op] : 'rgba(0,80,160,0.08)',
                transition: 'background 0.3s',
                cursor: 'pointer',
              }}
              onClick={() => setStep(i)}
            />
          ))}
        </div>

        {/* Step content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={`${op}-${step}`}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.2 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
              <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: '1rem', color: OP_COLORS[op] }}>
                Step {step + 1}/{steps.length}: {current.title}
              </div>
              {current.cost && (
                <span style={{
                  fontFamily: 'JetBrains Mono',
                  fontSize: '0.72rem',
                  color: 'var(--eco-dark)',
                  background: 'var(--eco-light)',
                  border: '1px solid var(--eco-border)',
                  padding: '2px 8px',
                  borderRadius: 4,
                  whiteSpace: 'nowrap',
                }}>
                  {current.cost}
                </span>
              )}
            </div>

            <p style={{ fontFamily: 'Inter', fontSize: '0.82rem', color: 'var(--text-dark)', marginBottom: 8, lineHeight: 1.5 }}>
              {current.description}
            </p>

            <div style={{ background: 'var(--sky-light)', border: '1px solid var(--sky-border)', borderRadius: 6, padding: '8px 12px' }}>
              <p style={{ fontFamily: 'Inter', fontSize: '0.76rem', color: 'var(--text-mid)', lineHeight: 1.5, fontStyle: 'italic' }}>
                {current.highlight}
              </p>
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Controls */}
        <div style={{ display: 'flex', gap: 8, marginTop: 14, alignItems: 'center' }}>
          <button type="button" className="gs-btn" onClick={reset} style={{ padding: '6px 10px' }} aria-label="Reset to first step" title="Reset to first step">
            <RotateCcw size={13} />
          </button>
          <button type="button" className="gs-btn" onClick={prev} disabled={isFirst}
            style={{ flex: 1, opacity: isFirst ? 0.4 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
            <ChevronLeft size={13} /> Prev
          </button>
          <button type="button" className="gs-btn" onClick={next} disabled={isLast}
            style={{ flex: 1, opacity: isLast ? 0.4 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              color: OP_COLORS[op], borderColor: `${OP_COLORS[op]}60`, background: `${OP_COLORS[op]}10` }}>
            Next <ChevronRight size={13} />
          </button>
        </div>
      </motion.div>
    </div>
  )
}

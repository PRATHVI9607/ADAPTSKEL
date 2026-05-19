import { motion } from 'framer-motion'
import { useGraphStore } from '../store'
import { LiveStreamMode } from './LiveStreamMode'
import { ExplainerMode } from './ExplainerMode'
import { BenchmarkPanel } from './BenchmarkPanel'
import { SkeletonOverlay } from './SkeletonOverlay'
import { HeatMapOverlay } from './HeatMapOverlay'

const fadeIn = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -6 },
  transition: { duration: 0.25 },
}

export function ModeOverlay() {
  const mode = useGraphStore(s => s.mode)

  if (mode === 'live') {
    return (
      <motion.div {...fadeIn} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <LiveStreamMode />
      </motion.div>
    )
  }

  if (mode === 'skeleton') {
    return (
      <motion.div {...fadeIn} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <SkeletonOverlay />
      </motion.div>
    )
  }

  if (mode === 'heatmap') {
    return (
      <motion.div {...fadeIn} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <HeatMapOverlay />
      </motion.div>
    )
  }

  if (mode === 'benchmark') {
    return (
      <motion.div {...fadeIn} style={{ position: 'absolute', inset: 0, background: 'rgba(10,10,15,0.85)', zIndex: 20, overflowY: 'auto', pointerEvents: 'all' }}>
        <BenchmarkPanel compact={false} />
      </motion.div>
    )
  }

  if (mode === 'explainer') {
    return (
      <motion.div {...fadeIn} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <ExplainerMode />
      </motion.div>
    )
  }

  return null
}

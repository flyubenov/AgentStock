import { scoreToBgColor, scoreToLabel } from '../types'
import { cn } from '../lib/utils'

interface ScoreBadgeProps {
  score: number | null
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export default function ScoreBadge({ score, size = 'md', showLabel = false }: ScoreBadgeProps) {
  const label = scoreToLabel(score)
  const colorClass = scoreToBgColor(score)

  const sizeClass = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-1',
    lg: 'text-base px-3 py-1.5',
  }[size]

  return (
    <span className={cn('rounded font-mono font-semibold inline-flex items-center gap-1.5', colorClass, sizeClass)}>
      {score != null ? score.toFixed(2) : '—'}
      {showLabel && label && <span className="font-normal text-xs opacity-80">{label}</span>}
    </span>
  )
}

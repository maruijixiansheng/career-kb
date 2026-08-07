import type { RadarDimension } from '../../types'

interface Props {
  dimensions: RadarDimension[]
}

export default function GapRadarChart({ dimensions }: Props) {
  if (!dimensions.length) return null

  const size = 200; const cx = size / 2; const cy = size / 2; const r = 80
  const n = dimensions.length
  const angleStep = (2 * Math.PI) / n

  const getPoint = (i: number, value: number) => {
    const angle = i * angleStep - Math.PI / 2
    return { x: cx + r * value * Math.cos(angle), y: cy + r * value * Math.sin(angle) }
  }

  const jdPoints = dimensions.map((d, i) => getPoint(i, d.jd_weight / 100).x + ',' + getPoint(i, d.jd_weight / 100).y).join(' ')
  const myPoints = dimensions.map((d, i) => getPoint(i, d.my_level / 100).x + ',' + getPoint(i, d.my_level / 100).y).join(' ')

  return (
    <div className="bg-white rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">能力雷达图</h3>
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[300px] mx-auto">
        {/* Grid */}
        {[0.25, 0.5, 0.75].map(level => (
          <polygon
            key={level}
            points={dimensions.map((_, i) => {
              const p = getPoint(i, level)
              return `${p.x},${p.y}`
            }).join(' ')}
            fill="none" stroke="#e5e7eb" strokeWidth="1"
          />
        ))}
        {/* JD requirement */}
        <polygon points={jdPoints} fill="rgba(59,130,246,0.2)" stroke="#3B82F6" strokeWidth="2" />
        {/* My skills */}
        <polygon points={myPoints} fill="rgba(16,185,129,0.2)" stroke="#10B981" strokeWidth="2" />
        {/* Axis labels */}
        {dimensions.map((d, i) => {
          const p = getPoint(i, 1.15)
          return <text key={i} x={p.x} y={p.y} textAnchor="middle" className="text-[8px] fill-gray-500">{d.name}</text>
        })}
      </svg>
      <div className="flex justify-center gap-4 mt-2 text-xs">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-blue-500/30 border border-blue-500" />JD 要求</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-emerald-500/30 border border-emerald-500" />我的水平</span>
      </div>
    </div>
  )
}

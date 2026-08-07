import type { JDSkill } from '../../types'

interface Props {
  skills: JDSkill[]
  totalWeight: number
}

const COLORS = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316', '#6366F1', '#14B8A6']

export default function TechStackChart({ skills, totalWeight }: Props) {
  if (!skills.length) return null

  return (
    <div className="bg-white rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">JD 技术栈重要度分布</h3>
      <div className="space-y-2">
        {skills.slice(0, 10).map((s, i) => (
          <div key={s.skill} className="flex items-center gap-2">
            <span className="text-xs text-gray-600 w-20 truncate" title={s.skill}>{s.skill}</span>
            <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${s.importance_weight}%`, backgroundColor: COLORS[i % COLORS.length] }}
              />
            </div>
            <span className="text-xs font-mono text-gray-500 w-10 text-right">{s.importance_weight}%</span>
            {s.is_required && <span className="text-xs text-red-400">必需</span>}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1 mt-3">
        {skills.map((s, i) => (
          <span
            key={s.skill}
            className="text-xs px-1.5 py-0.5 rounded"
            style={{ backgroundColor: COLORS[i % COLORS.length] + '20', color: COLORS[i % COLORS.length] }}
          >
            {s.skill} {s.importance_weight}%
          </span>
        ))}
      </div>
    </div>
  )
}

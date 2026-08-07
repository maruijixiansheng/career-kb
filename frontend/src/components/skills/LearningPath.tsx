import type { GapAnalysisResult } from '../../types'

interface Props {
  result: GapAnalysisResult
}

export default function LearningPath({ result }: Props) {
  const lp = result.learning_path
  if (!lp?.phases?.length) return null

  return (
    <div className="bg-white rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-1">📚 学习路径</h3>
      <p className="text-xs text-gray-500 mb-3">{lp.summary} · 共 {lp.total_weeks} 周</p>

      <div className="relative">
        {lp.phases.map((phase, i) => (
          <div key={i} className="flex gap-3 mb-4">
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-bold">
                {phase.phase}
              </div>
              {i < lp.phases.length - 1 && <div className="w-0.5 flex-1 bg-blue-200 mt-1" />}
            </div>
            <div className="flex-1 bg-gray-50 rounded-lg p-3">
              <div className="flex justify-between items-start">
                <h4 className="text-sm font-medium text-gray-800">{phase.title}</h4>
                <span className="text-xs text-blue-500 bg-blue-50 px-2 py-0.5 rounded">{phase.duration_weeks}周</span>
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {phase.skills.map(s => (
                  <span key={s} className="text-xs bg-white border rounded px-1.5 py-0.5 text-gray-600">{s}</span>
                ))}
              </div>
              {phase.resources?.length > 0 && (
                <div className="mt-2 text-xs text-gray-500">
                  {phase.resources.map((r, j) => (
                    <span key={j} className="mr-2">
                      📖 {r.name}
                      {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-blue-500 ml-1">链接</a>}
                    </span>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-400 mt-1">🎯 {phase.milestone}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

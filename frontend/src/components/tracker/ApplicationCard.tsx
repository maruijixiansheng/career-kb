import type { Application } from '../../types'
import { STATUS_LABELS, STATUS_COLORS, CHANNELS } from '../../types'

interface Props {
  app: Application
  onStatusChange: (id: string, toStatus: string) => void
  onAnalyze: (app: Application) => void
  onFeedback: (app: Application) => void
}

export default function ApplicationCard({ app, onStatusChange, onAnalyze, onFeedback }: Props) {
  const daysSinceApply = app.applied_at
    ? Math.floor((Date.now() - new Date(app.applied_at).getTime()) / 86400000)
    : 0

  const needsFollowUp = app.status === 'waiting' && daysSinceApply >= 7

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-2 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="font-medium text-gray-900 text-sm">{app.position}</h4>
          <p className="text-gray-500 text-xs">{app.company}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[app.status] || 'bg-gray-100 text-gray-600'}`}>
          {STATUS_LABELS[app.status] || app.status}
        </span>
      </div>

      {app.applied_at && (
        <div className="text-xs text-gray-400 mb-1">
          投递: {new Date(app.applied_at).toLocaleDateString('zh-CN')}
          {app.channel && app.channel !== 'other' && (
            <span className="ml-1 text-gray-300">· {CHANNELS[app.channel] || app.channel}</span>
          )}
        </div>
      )}

      {app.interview_key_points && (
        <div className="text-xs text-blue-500 mb-1">📋 已有面试反馈</div>
      )}

      {needsFollowUp && (
        <button
          onClick={() => onAnalyze(app)}
          className="w-full text-xs bg-red-50 text-red-600 hover:bg-red-100 rounded px-2 py-1 mb-1 flex items-center justify-center gap-1"
        >
          <span className="inline-block w-1.5 h-1.5 bg-red-400 rounded-full animate-pulse" />
          无回应 {daysSinceApply} 天，点击分析
        </button>
      )}

      {(app.status.startsWith('interview_') || app.status === 'offer') && (
        <button
          onClick={() => onFeedback(app)}
          className="w-full text-xs bg-purple-50 text-purple-600 hover:bg-purple-100 rounded px-2 py-1 mb-1"
        >
          📝 记录面试反馈
        </button>
      )}

      <div className="flex flex-wrap gap-1">
        {STATUS_LABELS[app.status] && (
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) onStatusChange(app.id, e.target.value)
            }}
            className="text-xs border border-gray-200 rounded px-1 py-0.5 text-gray-500 w-full"
          >
            <option value="">变更状态...</option>
            {getNextStatusOptions(app.status)}
          </select>
        )}
      </div>
    </div>
  )
}

function getNextStatusOptions(currentStatus: string) {
  // Hard-coded transitions matching state machine
  const transitions: Record<string, string[]> = {
    applied: ['waiting', 'resume_screening', 'rejected', 'withdrawn'],
    waiting: ['no_response', 'resume_screening', 'written_test', 'interview_1', 'rejected', 'withdrawn'],
    no_response: ['waiting', 'applied', 'withdrawn'],
    resume_screening: ['written_test', 'interview_1', 'rejected', 'withdrawn'],
    written_test: ['interview_1', 'rejected', 'withdrawn'],
    interview_1: ['interview_2', 'offer', 'rejected', 'withdrawn'],
    interview_2: ['interview_3', 'offer', 'rejected', 'withdrawn'],
    interview_3: ['offer', 'rejected', 'withdrawn'],
    offer: ['accepted', 'rejected', 'withdrawn'],
  }

  return (transitions[currentStatus] || []).map(status => (
    <option key={status} value={status}>{STATUS_LABELS[status] || status}</option>
  ))
}

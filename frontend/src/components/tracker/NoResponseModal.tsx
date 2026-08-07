import { useState, useEffect } from 'react'
import type { Application, NoResponseAnalysisResponse } from '../../types'
import { runNoResponseAnalysis } from '../../services/api'

interface Props {
  application: Application | null
  onClose: () => void
  onAction: (action: string) => void
}

export default function NoResponseModal({ application, onClose, onAction }: Props) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<NoResponseAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'analysis' | 'followup' | 'suggest'>('analysis')

  useEffect(() => {
    if (application) {
      runAnalysis()
    }
  }, [application?.id])

  const runAnalysis = async () => {
    if (!application) return
    setLoading(true)
    setError(null)
    try {
      const daysSinceApply = application.applied_at
        ? Math.floor((Date.now() - new Date(application.applied_at).getTime()) / 86400000)
        : 7
      const res = await runNoResponseAnalysis(application.id, daysSinceApply)
      if (res.error) {
        setError(res.error)
      } else {
        setResult(res)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析失败')
    } finally {
      setLoading(false)
    }
  }

  if (!application) return null

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="p-4 border-b flex justify-between items-center">
          <div>
            <h2 className="text-lg font-bold text-gray-800">无回应分析</h2>
            <p className="text-sm text-gray-500">{application.company} — {application.position}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full mb-3" />
              <p className="text-gray-500 text-sm">AI 正在并行分析...</p>
              <p className="text-gray-400 text-xs mt-1">原因分析 · 跟进方案 · 策略建议</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 text-red-600 rounded-lg p-4 text-sm">{error}</div>
          )}

          {result && !loading && (
            <div>
              {/* Tabs */}
              <div className="flex gap-1 mb-4 border-b">
                {(['analysis', 'followup', 'suggest'] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === tab
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-400 hover:text-gray-600'
                    }`}
                  >
                    {{ analysis: '原因分析', followup: '跟进方案', suggest: '策略建议' }[tab]}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {activeTab === 'analysis' && result.analysis_result && (
                <AnalysisView data={result.analysis_result as Record<string, unknown>} />
              )}
              {activeTab === 'followup' && result.follow_up_result && (
                <FollowUpView data={result.follow_up_result as Record<string, unknown>} />
              )}
              {activeTab === 'suggest' && result.suggest_result && (
                <SuggestView data={result.suggest_result as Record<string, unknown>} />
              )}

              {/* Summary */}
              {result.merged_summary && (
                <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
                  <strong>综合建议：</strong>{result.merged_summary}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
            关闭
          </button>
          <button
            onClick={() => onAction('follow_up')}
            className="px-4 py-2 text-sm bg-blue-500 text-white hover:bg-blue-600 rounded-lg"
          >
            执行跟进
          </button>
          <button
            onClick={() => onAction('rewrite_resume')}
            className="px-4 py-2 text-sm bg-green-500 text-white hover:bg-green-600 rounded-lg"
          >
            修改简历重投
          </button>
        </div>
      </div>
    </div>
  )
}

function AnalysisView({ data }: { data: Record<string, unknown> }) {
  const dims = (data.dimensions as Record<string, Record<string, unknown>>) || {}
  const dimLabels: Record<string, string> = {
    resume_match: '简历匹配度',
    timing: '投递时机',
    competition: '竞争环境',
    presentation: '简历呈现',
    other_factors: '其他因素',
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-700"><strong>主要原因：</strong>{data.primary_reason as string}</p>
      {Object.entries(dims).map(([key, val]) => (
        <div key={key} className="bg-gray-50 rounded-lg p-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-sm font-medium text-gray-700">{dimLabels[key] || key}</span>
            <span className={`text-sm font-bold ${(val.score as number) < 50 ? 'text-red-500' : 'text-green-500'}`}>
              {val.score as number}/100
            </span>
          </div>
          <p className="text-xs text-gray-500">{val.analysis as string}</p>
          <p className="text-xs text-blue-600 mt-1">💡 {val.suggestion as string}</p>
        </div>
      ))}
      <p className="text-sm text-gray-600 italic">{data.overall_assessment as string}</p>
    </div>
  )
}

function FollowUpView({ data }: { data: Record<string, unknown> }) {
  const email = data.email_template as Record<string, unknown>
  return (
    <div className="space-y-3">
      <div className="bg-gray-50 rounded-lg p-3">
        <h4 className="text-sm font-medium text-gray-700 mb-1">📧 邮件模板</h4>
        {email && (
          <>
            <p className="text-xs text-gray-500 mb-1"><strong>主题：</strong>{email.subject as string}</p>
            <pre className="text-xs text-gray-600 whitespace-pre-wrap bg-white rounded p-2 border">{email.body as string}</pre>
            {Array.isArray(email.tips) && (
              <div className="mt-2 text-xs text-amber-600">
                {(email.tips as string[]).map((tip, i) => <p key={i}>• {tip}</p>)}
              </div>
            )}
          </>
        )}
      </div>
      <div className="text-xs text-gray-500 space-y-1">
        <p>💬 <strong>LinkedIn:</strong> {data.linkedin_message as string}</p>
        <p>📱 <strong>微信/脉脉:</strong> {data.wechat_message as string}</p>
        <p>📌 <strong>推荐渠道:</strong> {data.recommended_channel as string}</p>
        <p>⏰ <strong>最佳时间:</strong> {data.best_time as string}</p>
      </div>
    </div>
  )
}

function SuggestView({ data }: { data: Record<string, unknown> }) {
  const strategies = (data.strategies as Array<Record<string, unknown>>) || []
  const actionPlan = (data.action_plan as Array<Record<string, unknown>>) || []

  return (
    <div className="space-y-3">
      {strategies.map((s, i) => (
        <div key={i} className="bg-gray-50 rounded-lg p-3">
          <div className="flex justify-between items-start mb-1">
            <span className="text-sm font-medium text-gray-700">{s.title as string}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              s.priority === 'high' ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-500'
            }`}>{s.priority as string}</span>
          </div>
          <p className="text-xs text-gray-500">{s.description as string}</p>
          <p className="text-xs text-gray-400 mt-1">预计 {s.effort_days as number} 天 · {s.expected_impact as string}</p>
        </div>
      ))}
      <div className="bg-blue-50 rounded-lg p-3">
        <p className="text-sm font-medium text-blue-700 mb-2">📋 行动步骤</p>
        {actionPlan.map((step, i) => (
          <div key={i} className="flex gap-2 text-xs mb-1">
            <span className="text-blue-400 font-bold">{step.step as number}.</span>
            <span className="text-blue-600">{step.action as string}</span>
            <span className="text-blue-400 ml-auto">{step.deadline as string}</span>
          </div>
        ))}
      </div>
      <p className="text-sm text-center text-gray-500 italic">💪 {data.motivation as string}</p>
    </div>
  )
}

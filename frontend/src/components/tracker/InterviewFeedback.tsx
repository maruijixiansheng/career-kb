import { useState } from 'react'
import type { Application } from '../../types'
import { saveInterviewFeedback } from '../../services/api'
import VoiceInput from './VoiceInput'

interface Props {
  application: Application
  onClose: () => void
  onSaved: () => void
}

export default function InterviewFeedback({ application, onClose, onSaved }: Props) {
  const [feedback, setFeedback] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    if (!feedback.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await saveInterviewFeedback(application.id, feedback)
      if (res.error) {
        setError(res.error)
      } else {
        setResult(res.interview_key_points || null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    }
    setLoading(false)
  }

  const handleVoiceText = (text: string) => {
    setFeedback(prev => prev + text)
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b flex justify-between items-center">
          <div>
            <h2 className="text-lg font-bold text-gray-800">面试反馈</h2>
            <p className="text-sm text-gray-500">{application.company} — {application.position}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center gap-2 mb-2">
            <label className="text-sm text-gray-600">描述面试过程：</label>
            <VoiceInput onTextReady={handleVoiceText} disabled={loading} />
          </div>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            className="w-full border rounded-lg p-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="面试问了什么问题？你回答得怎么样？面试官给了什么反馈？"
          />

          {result && !loading && (() => {
            const r = result as any
            return (
              <div className="mt-4 bg-blue-50 rounded-lg p-3">
                <h4 className="text-sm font-medium text-blue-700 mb-2">🤖 AI 提取的关键信息</h4>
                {r.questions_asked && (
                  <div className="mb-2">
                    <span className="text-xs text-gray-500">被问到的问题：</span>
                    {(r.questions_asked as string[]).map((q: string, i: number) => (
                      <p key={i} className="text-xs text-gray-600 ml-2">• {q}</p>
                    ))}
                  </div>
                )}
                {r.key_learnings && (
                  <div className="mb-2">
                    <span className="text-xs text-gray-500">关键收获：</span>
                    {(r.key_learnings as string[]).map((k: string, i: number) => (
                      <p key={i} className="text-xs text-green-600 ml-2">✅ {k}</p>
                    ))}
                  </div>
                )}
                {r.areas_to_improve && (
                  <div>
                    <span className="text-xs text-gray-500">需要改进：</span>
                    {(r.areas_to_improve as string[]).map((a: string, i: number) => (
                      <p key={i} className="text-xs text-orange-600 ml-2">📝 {a}</p>
                    ))}
                  </div>
                )}
              </div>
            )
          })()}

          {error && <div className="mt-3 bg-red-50 text-red-600 rounded p-2 text-sm">{error}</div>}
        </div>

        <div className="p-4 border-t flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">关闭</button>
          <button
            onClick={handleSave}
            disabled={loading || !feedback.trim()}
            className="px-4 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'AI 分析中...' : '保存并分析'}
          </button>
        </div>
      </div>
    </div>
  )
}

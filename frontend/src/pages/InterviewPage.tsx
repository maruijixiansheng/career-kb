import { useState, useEffect, useRef, useCallback } from 'react'
import type { Resume, JobDescription } from '../types'
import { listResumes, listJDs, startInterview, respondInterview, getInterviewReport } from '../services/api'

interface Msg { role: 'interviewer' | 'candidate' | 'system'; content: string }

export default function InterviewPage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [jds, setJDs] = useState<JobDescription[]>([])
  const [selectedJD, setSelectedJD] = useState('')
  const [selectedResume, setSelectedResume] = useState('')
  const [mode, setMode] = useState('mixed')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [qNum, setQNum] = useState(0); const [qTotal, setQTotal] = useState(10)
  const [report, setReport] = useState<Record<string, unknown> | null>(null)
  const chatEnd = useRef<HTMLDivElement>(null)

  useEffect(() => { Promise.all([listResumes(), listJDs()]).then(([r, j]) => { setResumes(r); setJDs(j) }) }, [])
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const handleStart = async () => {
    if (!selectedJD || !selectedResume) return
    setLoading(true)
    try {
      const res = await startInterview(selectedJD, selectedResume, mode)
      setSessionId(res.session_id); setQNum(res.question_number); setQTotal(res.total_questions)
      setMessages([{ role: 'interviewer' as const, content: res.question }])
      setReport(null)
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handleSend = async () => {
    if (!input.trim() || !sessionId) return
    const answer = input; setInput(''); setLoading(true)
    const cMsg: Msg = { role: 'candidate', content: answer }
    setMessages(prev => [...prev, cMsg])
    try {
      const res = await respondInterview(sessionId, answer)
      if (res.finished) {
        setMessages(prev => [...prev, { role: 'system' as const, content: '面试结束！' }])
        setReport(res.report || null)
      } else {
        const updates: Msg[] = []
        if (res.feedback) updates.push({ role: 'system', content: `💬 ${res.feedback}` })
        if (res.question) updates.push({ role: 'interviewer', content: res.question })
        setMessages(prev => [...prev, ...updates])
        setQNum(res.question_number!); setQTotal(res.total_questions!)
      }
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handleRestart = () => { setSessionId(null); setMessages([]); setReport(null); setQNum(0) }

  return (
    <div className="h-full flex flex-col">
      <h1 className="text-xl font-bold text-gray-800 mb-4">面试模拟</h1>

      {!sessionId ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-sm border p-8 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4 text-center">开始模拟面试</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">选择 JD</label>
                <select value={selectedJD} onChange={e => setSelectedJD(e.target.value)} className="w-full border rounded px-3 py-2 text-sm">
                  <option value="">-- 选择 JD --</option>
                  {jds.map(jd => <option key={jd.id} value={jd.id}>{jd.title} - {jd.company}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">选择简历</label>
                <select value={selectedResume} onChange={e => setSelectedResume(e.target.value)} className="w-full border rounded px-3 py-2 text-sm">
                  <option value="">-- 选择简历 --</option>
                  {resumes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">面试模式</label>
                <div className="flex gap-2">
                  {[{ k: 'technical', l: '技术面' }, { k: 'behavioral', l: '行为面' }, { k: 'mixed', l: '综合' }].map(m => (
                    <button key={m.k} onClick={() => setMode(m.k)} className={`flex-1 py-2 rounded-lg text-sm border transition-colors ${mode === m.k ? 'bg-blue-50 border-blue-300 text-blue-600' : 'border-gray-200 text-gray-500'}`}>{m.l}</button>
                  ))}
                </div>
              </div>
              <button onClick={handleStart} disabled={loading || !selectedJD || !selectedResume}
                className="w-full py-2.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 disabled:opacity-50">
                🎯 开始面试
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col">
          {/* Progress */}
          <div className="bg-white rounded-lg shadow-sm border p-3 mb-3 flex justify-between items-center">
            <span className="text-sm text-gray-600">
              {report ? '✅ 面试完成' : `面试中 (${qNum}/${qTotal})`}
            </span>
            <div className="flex gap-2">
              {report && <button onClick={handleRestart} className="px-3 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200">重新开始</button>}
            </div>
          </div>

          {/* Chat */}
          <div className="flex-1 overflow-y-auto bg-white rounded-lg shadow-sm border p-4 mb-3 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'candidate' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                  m.role === 'interviewer' ? 'bg-gray-100 text-gray-800' :
                  m.role === 'candidate' ? 'bg-blue-500 text-white' :
                  'bg-yellow-50 text-yellow-700 text-center w-full'
                }`}>
                  {m.role === 'interviewer' && <span className="text-xs text-gray-400 block mb-0.5">🤖 面试官</span>}
                  {m.content}
                </div>
              </div>
            ))}
            {loading && <div className="text-center text-gray-400 text-sm">面试官正在思考...</div>}
            <div ref={chatEnd} />
          </div>

          {/* Report */}
          {report && (
            <div className="bg-white rounded-lg shadow-sm border p-4 mb-3">
              <h3 className="font-bold text-lg mb-3">📊 面试评估报告</h3>
              <div className="flex items-center gap-4 mb-4">
                <div className="text-center">
                  <span className={`text-3xl font-bold ${(report.overall_score as number) >= 80 ? 'text-green-500' : (report.overall_score as number) >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>{report.overall_score as number}</span>
                  <p className="text-xs text-gray-400">综合得分</p>
                </div>
                <div className="flex-1 grid grid-cols-5 gap-2">
                  {(report.dimension_scores as Record<string, number>) && Object.entries(report.dimension_scores as Record<string, number>).map(([k, v]) => (
                    <div key={k} className="text-center">
                      <div className="text-xs font-medium text-gray-500">{{ technical: '技术', communication: '沟通', project_experience: '项目', problem_solving: '解决', job_match: '匹配' }[k] || k}</div>
                      <div className="text-sm font-bold">{v}</div>
                    </div>
                  ))}
                </div>
              </div>
              {Array.isArray(report.strengths) && (report.strengths as string[]).length > 0 && (
                <div className="mb-2"><span className="text-xs text-gray-500">💪 优势: </span>{(report.strengths as string[]).map((s, i) => <span key={i} className="text-xs text-green-600 mr-2">{s}</span>)}</div>
              )}
              {Array.isArray(report.weaknesses) && (report.weaknesses as string[]).length > 0 && (
                <div className="mb-2"><span className="text-xs text-gray-500">📝 待改进: </span>{(report.weaknesses as string[]).map((w, i) => <span key={i} className="text-xs text-orange-600 mr-2">{w}</span>)}</div>
              )}
              {report.suggestions ? <p className="text-sm text-blue-600 mt-2">💡 {`${report.suggestions}`}</p> : null}

              {/* 参考答案 */}
              {Array.isArray(report.model_answers) && (report.model_answers as any[]).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <h4 className="font-semibold text-sm text-gray-700 mb-3">🎯 面试官问题 & 专业参考答案</h4>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {(report.model_answers as any[]).map((item, i) => (
                      <div key={i} className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                        <p className="text-xs font-medium text-blue-800 mb-1.5">
                          Q{item.question_number}: {item.question}
                        </p>
                        <div className="bg-white rounded p-2.5 text-xs text-gray-700 leading-relaxed">
                          <span className="text-green-600 font-medium">📝 参考回答: </span>
                          {item.model_answer}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Input */}
          {!report && (
            <div className="flex gap-2">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSend()}
                className="flex-1 border rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                placeholder="输入你的回答..."
              />
              <button onClick={handleSend} disabled={loading || !input.trim()}
                className="px-6 py-3 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 disabled:opacity-50">
                发送
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

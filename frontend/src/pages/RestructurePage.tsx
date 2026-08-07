import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, Copy, Check, ArrowLeft, FileText, AlertCircle, Wand2, Download, Eye, X, Save } from 'lucide-react'
import { getResume, listJDs, restructureResume, restructureResumeStream, downloadPdfResume, smartRestructure } from '../services/api'
import type { ResumeDetail, JobDescription, RestructureResponse, FactCheckResult } from '../types'

type Stage = 'config' | 'generating' | 'done'

export default function RestructurePage() {
  const { id: resumeId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preselectedJdId = searchParams.get('jd_id') || ''

  const [stage, setStage] = useState<Stage>('config')
  const [resume, setResume] = useState<ResumeDetail | null>(null)
  const [jds, setJds] = useState<JobDescription[]>([])
  const [loading, setLoading] = useState(true)

  // Config
  const [selectedJdId, setSelectedJdId] = useState('')
  const [jdText, setJdText] = useState('')
  const [jdTitle, setJdTitle] = useState('')
  const [jdCompany, setJdCompany] = useState('')
  const [usePastedJD, setUsePastedJD] = useState(false)
  const [useSmartMode, setUseSmartMode] = useState(true) // 默认开启智能模式

  // Result
  const [generatedMarkdown, setGeneratedMarkdown] = useState('')
  const [analysis, setAnalysis] = useState('')
  const [matchScore, setMatchScore] = useState<number | null>(null)
  const [factCheck, setFactCheck] = useState<FactCheckResult | null>(null)
  const [progress, setProgress] = useState(0)
  const [progressStage, setProgressStage] = useState('')
  const [copied, setCopied] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const streamContentRef = useRef('')

  useEffect(() => {
    if (!resumeId) return
    Promise.all([getResume(resumeId), listJDs()])
      .then(([resumeData, jdList]) => {
        setResume(resumeData)
        setJds(jdList)
        // 如果从 JD 页面跳转过来，自动选中对应 JD
        if (preselectedJdId && jdList.some(j => j.id === preselectedJdId)) {
          setSelectedJdId(preselectedJdId)
          setUsePastedJD(false)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [resumeId])

  const handleJDSelect = (jdId: string) => {
    setSelectedJdId(jdId)
    setUsePastedJD(false)
  }

  const handleStartGeneration = async () => {
    const jdPayload = usePastedJD
      ? { jd_text: jdText, jd_title: jdTitle, jd_company: jdCompany }
      : { jd_id: selectedJdId }

    if (!usePastedJD && !selectedJdId) return
    if (usePastedJD && !jdText.trim()) return

    setStage('generating')
    setProgress(0)
    setProgressStage('准备中...')
    setGeneratedMarkdown('')
    setError('')
    streamContentRef.current = ''

    try {
      // 智能模式: 跨简历+技能库检索
      if (useSmartMode) {
        setProgressStage('智能检索中...')
        const result = await smartRestructure({
          ...jdPayload,
          resume_id: resumeId,
        })
        setGeneratedMarkdown(result.restructured_markdown)
        setAnalysis(result.changes_summary || '')
        setMatchScore(result.match_score ?? null)
        setFactCheck(result.fact_check as FactCheckResult || null)
        setProgress(100)
        setStage('done')
        return
      }

      // 传统模式: 流式生成
      const controller = restructureResumeStream(
        resumeId!,
        jdPayload,
        (event) => {
          switch (event.type) {
            case 'progress':
              setProgressStage((event.stage as string) || '')
              setProgress((event.progress as number) || 0)
              break
            case 'content':
              streamContentRef.current += (event.text as string) || ''
              setGeneratedMarkdown(streamContentRef.current)
              break
            case 'complete':
              setGeneratedMarkdown((event.resume_markdown as string) || streamContentRef.current)
              setAnalysis((event.analysis as string) || '')
              setProgress(100)
              setStage('done')
              break
            case 'fact_check_result':
              setFactCheck(event.data as FactCheckResult)
              break
            case 'error':
              setError(event.message as string || '生成失败')
              setStage('done')
              break
          }
        },
        (err) => {
          setError(err.message)
          setStage('done')
        }
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误')
      setStage('done')
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(generatedMarkdown)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSave = async () => {
    if (!resumeId || !generatedMarkdown) return
    setSaving(true)
    try {
      const title = jdTitle || jds.find(j => j.id === selectedJdId)?.title || '定制'
      const name = `${title}-${new Date().toLocaleDateString('zh-CN')}`
      const form = new FormData()
      form.append('name', name)
      form.append('markdown', generatedMarkdown)
      const token = localStorage.getItem('access_token')
      const resp = await fetch('/api/resumes/save-generated', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      })
      if (!resp.ok) throw new Error((await resp.json()).detail || '保存失败')
      const result = await resp.json()
      setError('')
      alert(`已保存到简历库「${result.name}」(${result.chunk_count} 个分块)`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!resumeId || !generatedMarkdown) return
    setPdfLoading(true)
    try {
      const title = jdTitle || (usePastedJD ? '' : jds.find(j => j.id === selectedJdId)?.title) || '定制'
      await downloadPdfResume(resumeId, generatedMarkdown, title)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PDF 下载失败')
    } finally {
      setPdfLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-gray-300" />
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400">简历不存在</p>
        <button onClick={() => navigate('/resumes')} className="mt-4 text-primary-600 text-sm">
          ← 返回简历列表
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => navigate('/resumes')}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft size={20} className="text-gray-500" />
        </button>
        <div>
          <h2 className="text-2xl font-bold text-gray-800">简历动态重组</h2>
          <p className="text-sm text-gray-500 mt-1">
            源简历: {resume.name} · {resume.source_format?.toUpperCase()}
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle size={18} className="text-red-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-700">生成失败</p>
            <p className="text-sm text-red-600 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Stage: Config */}
      {stage === 'config' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Source Resume */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <FileText size={16} />
              源简历
            </h3>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm font-medium text-gray-700">{resume.name}</p>
              <p className="text-xs text-gray-400 mt-1">
                {resume.chunk_count} 个分块 · {resume.source_format?.toUpperCase()}
              </p>
            </div>
          </div>

          {/* JD Selection */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">选择目标 JD</h3>

            {/* Toggle */}
            <div className="flex mb-4 bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setUsePastedJD(false)}
                className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  !usePastedJD ? 'bg-white shadow text-gray-700' : 'text-gray-500'
                }`}
              >
                从JD库选择
              </button>
              <button
                onClick={() => setUsePastedJD(true)}
                className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  usePastedJD ? 'bg-white shadow text-gray-700' : 'text-gray-500'
                }`}
              >
                粘贴新JD
              </button>
            </div>

            {!usePastedJD ? (
              <div className="space-y-2 max-h-48 overflow-auto">
                {jds.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">暂无保存的 JD，请先添加</p>
                ) : (
                  jds.map((jd) => (
                    <button
                      key={jd.id}
                      onClick={() => handleJDSelect(jd.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedJdId === jd.id
                          ? 'border-primary-400 bg-primary-50'
                          : 'border-gray-100 hover:bg-gray-50'
                      }`}
                    >
                      <p className="text-sm font-medium text-gray-700">{jd.title}</p>
                      <p className="text-xs text-gray-400">{jd.company || '未指定公司'}</p>
                    </button>
                  ))
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={jdTitle}
                    onChange={(e) => setJdTitle(e.target.value)}
                    placeholder="职位名称"
                    className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                  <input
                    type="text"
                    value={jdCompany}
                    onChange={(e) => setJdCompany(e.target.value)}
                    placeholder="公司名称"
                    className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <textarea
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  placeholder="粘贴职位描述全文..."
                  rows={8}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-vertical"
                />
              </div>
            )}
          </div>

          {/* Smart mode toggle + Generate Button */}
          <div className="col-span-2 flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-600">
              <input
                type="checkbox"
                checked={useSmartMode}
                onChange={(e) => setUseSmartMode(e.target.checked)}
                className="w-4 h-4 text-primary-600 rounded"
              />
              <span>智能模式</span>
              <span className="text-xs text-gray-400">（跨简历+技能库检索，扬长避短）</span>
            </label>
            <button
              onClick={handleStartGeneration}
              disabled={
                (!usePastedJD && !selectedJdId) ||
                (usePastedJD && !jdText.trim())
              }
              className="w-full py-3 bg-primary-600 text-white rounded-xl text-sm font-semibold hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              <Wand2 size={18} />
              生成定制简历
            </button>
          </div>
        </div>
      )}

      {/* Stage: Generating */}
      {stage === 'generating' && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-8">
          <div className="text-center mb-8">
            <Loader2 size={36} className="animate-spin text-primary-500 mx-auto mb-4" />
            <p className="text-lg font-medium text-gray-700">{progressStage || '生成中...'}</p>
            <p className="text-sm text-gray-400 mt-1">正在为你的简历匹配最佳内容</p>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-gray-100 rounded-full h-2 mb-6">
            <div
              className="bg-primary-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Streaming Preview */}
          {generatedMarkdown && (
            <div className="border border-gray-200 rounded-lg p-4 max-h-96 overflow-auto">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">
                {generatedMarkdown}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Stage: Done */}
      {stage === 'done' && generatedMarkdown && (
        <div className="space-y-6">
          {/* Result */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
              <div className="flex items-center gap-4">
                <h3 className="text-sm font-semibold text-gray-700">生成的简历</h3>
                {matchScore !== null && (
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                    匹配度: {matchScore}%
                  </span>
                )}
                {factCheck && (
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      factCheck.is_factual
                        ? 'bg-green-100 text-green-700'
                        : 'bg-yellow-100 text-yellow-700'
                    }`}
                  >
                    事实核查: {factCheck.score}分
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green-600 border border-green-200 hover:bg-green-50 rounded-lg transition-colors disabled:opacity-50"
                >
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {saving ? '保存中...' : '保存'}
                </button>
                <button
                  onClick={async () => {
                    setShowPreview(true)
                    setPreviewLoading(true)
                    try {
                      const token = localStorage.getItem('access_token')
                      const resp = await fetch(`/api/resumes/${resumeId}/styled`, {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          ...(token ? { Authorization: `Bearer ${token}` } : {}),
                        },
                        body: JSON.stringify({ markdown: generatedMarkdown }),
                      })
                      if (!resp.ok) throw new Error('预览加载失败')
                      const html = await resp.text()
                      setPreviewHtml(html)
                    } catch {
                      setPreviewHtml('')
                    } finally {
                      setPreviewLoading(false)
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-primary-600 border border-primary-200 hover:bg-primary-50 rounded-lg transition-colors"
                >
                  <Eye size={14} />
                  预览
                </button>
                <button
                  onClick={handleDownloadPdf}
                  disabled={pdfLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 rounded-lg transition-colors"
                >
                  {pdfLoading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      下载中...
                    </>
                  ) : (
                    <>
                      <Download size={14} />
                      下载简历
                    </>
                  )}
                </button>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  {copied ? (
                    <>
                      <Check size={14} className="text-green-500" />
                      已复制
                    </>
                  ) : (
                    <>
                      <Copy size={14} />
                      复制 Markdown
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Editable Markdown Content */}
            <div className="p-6">
              <textarea
                value={generatedMarkdown}
                onChange={(e) => setGeneratedMarkdown(e.target.value)}
                className="w-full min-h-[500px] text-sm text-gray-700 font-sans leading-relaxed p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-300 resize-vertical"
                placeholder="生成的简历内容..."
              />
            </div>
          </div>

          {/* Analysis */}
          {analysis && (
            <div className="bg-blue-50 rounded-xl border border-blue-100 p-5">
              <h4 className="text-sm font-semibold text-blue-800 mb-2">生成分析</h4>
              <p className="text-sm text-blue-700 whitespace-pre-wrap">{analysis}</p>
            </div>
          )}

          {/* Fact Check Issues */}
          {factCheck && factCheck.issues.length > 0 && (
            <div className="bg-yellow-50 rounded-xl border border-yellow-100 p-5">
              <h4 className="text-sm font-semibold text-yellow-800 mb-3">
                事实核查警告 ({factCheck.issues.length})
              </h4>
              <div className="space-y-2">
                {factCheck.issues.map((issue, i) => (
                  <div key={i} className="p-3 bg-white rounded-lg border border-yellow-200">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          issue.severity === 'error'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}
                      >
                        {issue.severity === 'error' ? '错误' : '警告'}
                      </span>
                      <span className="text-xs text-gray-500">{issue.location}</span>
                    </div>
                    <p className="text-sm text-gray-700">{issue.problem}</p>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 bg-red-50 rounded">
                        <span className="text-red-500 font-medium">原文:</span>{' '}
                        <span className="text-gray-600">{issue.original}</span>
                      </div>
                      <div className="p-2 bg-gray-50 rounded">
                        <span className="text-gray-500 font-medium">生成:</span>{' '}
                        <span className="text-gray-600">{issue.generated}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={() => { setStage('config'); setGeneratedMarkdown(''); setError(''); setShowPreview(false) }}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              重新生成
            </button>
            <button
              onClick={() => navigate('/resumes')}
              className="flex-1 py-2.5 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700 transition-colors"
            >
              返回简历列表
            </button>
          </div>

          {/* PDF 预览模态框 */}
          {showPreview && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowPreview(false)}>
              <div className="bg-white rounded-xl shadow-2xl w-[95vw] h-[95vh] flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-700">简历预览（打印即为PDF效果）</h3>
                  <button onClick={() => { setShowPreview(false); setPreviewHtml('') }} className="p-1 hover:bg-gray-100 rounded-lg">
                    <X size={18} className="text-gray-400" />
                  </button>
                </div>
                {previewLoading ? (
                  <div className="flex-1 flex items-center justify-center">
                    <Loader2 size={28} className="animate-spin text-gray-300" />
                  </div>
                ) : previewHtml ? (
                  <iframe
                    srcDoc={previewHtml}
                    className="flex-1 w-full border-0"
                    title="简历预览"
                  />
                ) : (
                  <div className="flex-1 flex items-center justify-center text-gray-400">
                    加载预览失败
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

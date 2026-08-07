import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Loader2, Copy, Check, ArrowLeft, AlertCircle, Download, Eye, X, Save } from 'lucide-react'
import { getJD, smartRestructure, listResumes, downloadPdfResume } from '../services/api'
import type { JDDetail, RestructureResponse, FactCheckResult, Resume } from '../types'

export default function JDRestructurePage() {
  const { jdId } = useParams<{ jdId: string }>()
  const navigate = useNavigate()

  const [jd, setJD] = useState<JDDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [generatedMarkdown, setGeneratedMarkdown] = useState('')
  const [analysis, setAnalysis] = useState('')
  const [matchScore, setMatchScore] = useState<number | null>(null)
  const [factCheck, setFactCheck] = useState<FactCheckResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [firstResumeId, setFirstResumeId] = useState<string>('')

  useEffect(() => {
    if (!jdId) return
    Promise.all([getJD(jdId), listResumes()])
      .then(([jdData, resumeList]) => {
        setJD(jdData)
        setResumes(resumeList)
        // 优先选择有证件照的简历，用于预览时显示照片
        if (resumeList.length > 0) {
          const photoResume = resumeList.find(r => r.has_photo) || resumeList[0]
          setFirstResumeId(photoResume.id)
        }
        // 自动开始生成
        startGeneration(jdData)
      })
      .catch(err => { setError('加载失败: ' + (err instanceof Error ? err.message : '')); setLoading(false) })
  }, [jdId])

  const startGeneration = async (jdData: JDDetail) => {
    setGenerating(true)
    setError('')
    try {
      const result = await smartRestructure({
        jd_id: jdData.id,
        jd_text: jdData.raw_text,
        jd_title: jdData.title,
        jd_company: jdData.company || '',
      })
      setGeneratedMarkdown(result.restructured_markdown)
      setAnalysis(result.changes_summary || '')
      setMatchScore(result.match_score ?? null)
      setFactCheck(result.fact_check as FactCheckResult || null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenerating(false)
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(generatedMarkdown)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSave = async () => {
    if (!generatedMarkdown) return
    setSaving(true)
    try {
      const title = jd?.title || '定制'
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

  const handleDownload = async () => {
    if (!generatedMarkdown) return
    if (!firstResumeId) { setError('没有可用简历来生成 PDF'); return }
    setPdfLoading(true)
    try {
      await downloadPdfResume(firstResumeId, generatedMarkdown, jd?.title)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PDF 下载失败')
    } finally {
      setPdfLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 size={32} className="animate-spin text-primary-500" />
      </div>
    )
  }

  if (!jd) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400">JD 不存在</p>
        <button onClick={() => navigate('/resumes')} className="mt-4 text-primary-600 text-sm">← 返回</button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/resumes')} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft size={20} className="text-gray-500" />
        </button>
        <div>
          <h2 className="text-2xl font-bold text-gray-800">智能简历生成</h2>
          <p className="text-sm text-gray-500 mt-1">
            {jd.title} {jd.company ? `@ ${jd.company}` : ''} · 跨全部简历+技能库检索
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle size={18} className="text-red-500 shrink-0 mt-0.5" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {generating && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-8 text-center">
          <Loader2 size={36} className="animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-700">AI 正在生成简历...</p>
          <p className="text-sm text-gray-400 mt-1">正在从所有简历和技能库中检索最佳素材</p>
        </div>
      )}

      {generatedMarkdown && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
              <div className="flex items-center gap-4">
                <h3 className="text-sm font-semibold text-gray-700">生成的简历</h3>
                {matchScore !== null && (
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                    匹配度: {matchScore}%
                  </span>
                )}
                {factCheck && (
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${factCheck.is_factual ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                    事实核查: {factCheck.score}分
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green-600 border border-green-200 hover:bg-green-50 rounded-lg disabled:opacity-50">
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {saving ? '保存中...' : '保存'}
                </button>
                <button onClick={async () => {
                  setShowPreview(true)
                  setPreviewLoading(true)
                  try {
                    const rid = firstResumeId
                    if (!rid) throw new Error('请先上传一份简历')
                    const token = localStorage.getItem('access_token')
                    const resp = await fetch(`/api/resumes/${rid}/styled`, {
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
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-primary-600 border border-primary-200 hover:bg-primary-50 rounded-lg">
                  <Eye size={14} />预览
                </button>
                <button onClick={handleDownload} disabled={pdfLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 rounded-lg">
                  {pdfLoading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                  下载简历
                </button>
                <button onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 rounded-lg">
                  {copied ? <><Check size={14} className="text-green-500" />已复制</> : <><Copy size={14} />复制</>}
                </button>
              </div>
            </div>
            <div className="p-6">
              <textarea
                value={generatedMarkdown}
                onChange={(e) => setGeneratedMarkdown(e.target.value)}
                className="w-full min-h-[500px] text-sm text-gray-700 font-sans leading-relaxed p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-300 resize-vertical"
              />
            </div>
          </div>

          {analysis && (
            <div className="bg-blue-50 rounded-xl border border-blue-100 p-5">
              <h4 className="text-sm font-semibold text-blue-800 mb-2">生成分析</h4>
              <p className="text-sm text-blue-700 whitespace-pre-wrap">{analysis}</p>
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={() => startGeneration(jd)} disabled={generating}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 disabled:opacity-50">
              {generating ? '生成中...' : '重新生成'}
            </button>
            <button onClick={() => navigate('/resumes')}
              className="flex-1 py-2.5 bg-primary-600 text-white rounded-xl text-sm font-medium hover:bg-primary-700">
              返回JD列表
            </button>
          </div>

          {showPreview && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowPreview(false)}>
              <div className="bg-white rounded-xl shadow-2xl w-[95vw] h-[95vh] flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-700">简历预览</h3>
                  <button onClick={() => { setShowPreview(false); setPreviewHtml('') }} className="p-1 hover:bg-gray-100 rounded-lg"><X size={18} className="text-gray-400" /></button>
                </div>
                {previewLoading ? (
                  <div className="flex-1 flex items-center justify-center">
                    <Loader2 size={28} className="animate-spin text-gray-300" />
                  </div>
                ) : previewHtml ? (
                  <iframe srcDoc={previewHtml} className="flex-1 w-full border-0" title="预览" />
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

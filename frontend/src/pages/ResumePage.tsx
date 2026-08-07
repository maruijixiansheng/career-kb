import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Upload,
  FileText,
  Trash2,
  Loader2,
  Wand2,
  Plus,
  Eye,
  Image,
  X,
  ScanLine,
} from 'lucide-react'
import {
  listResumes,
  uploadResume,
  deleteResume,
  listJDs,
  createJD,
  deleteJD,
  getJD,
  ocrJD,
} from '../services/api'
import type { Resume, JobDescription, JDDetail } from '../types'

export default function ResumePage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [jds, setJDs] = useState<JobDescription[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [resumeName, setResumeName] = useState('')
  const [jdText, setJdText] = useState('')
  const [jdTitle, setJdTitle] = useState('')
  const [jdCompany, setJdCompany] = useState('')
  const [activeTab, setActiveTab] = useState<'resumes' | 'jds'>('resumes')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [selectedPhoto, setSelectedPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [viewingJD, setViewingJD] = useState<JDDetail | null>(null)
  const [jdLoading, setJdLoading] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [resumeList, jdList] = await Promise.all([listResumes(), listJDs()])
      setResumes(resumeList)
      setJDs(jdList)
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3000)
  }

  const handleUpload = async () => {
    if (!selectedFile || !resumeName.trim()) return
    setUploading(true)
    try {
      await uploadResume(selectedFile, resumeName.trim(), selectedPhoto)
      showMessage('success', `简历 "${resumeName}" 上传成功`)
      setSelectedFile(null)
      setResumeName('')
      setSelectedPhoto(null)
      setPhotoPreview(null)
      await loadData()
    } catch (err) {
      showMessage('error', `上传失败: ${err instanceof Error ? err.message : '未知错误'}`)
    } finally {
      setUploading(false)
    }
  }

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      showMessage('error', '仅支持 JPG/PNG 格式的照片')
      return
    }
    if (file.size > 2 * 1024 * 1024) {
      showMessage('error', '照片大小不能超过 2MB')
      return
    }
    setSelectedPhoto(file)
    setPhotoPreview(URL.createObjectURL(file))
  }

  const handleDeleteResume = async (id: string, name: string) => {
    if (!confirm(`确定删除简历 "${name}"？此操作不可恢复。`)) return
    try {
      await deleteResume(id)
      showMessage('success', '简历已删除')
      await loadData()
    } catch (err) {
      showMessage('error', '删除失败')
    }
  }

  const handleCreateJD = async () => {
    if (!jdText.trim() || !jdTitle.trim()) return
    try {
      await createJD(jdTitle.trim(), jdText.trim(), jdCompany.trim() || undefined)
      showMessage('success', `JD "${jdTitle}" 已保存`)
      setJdText('')
      setJdTitle('')
      setJdCompany('')
      await loadData()
    } catch (err) {
      showMessage('error', 'JD保存失败')
    }
  }

  const handleDeleteJD = async (id: string, title: string) => {
    if (!confirm(`确定删除 JD "${title}"？`)) return
    try {
      await deleteJD(id)
      showMessage('success', 'JD已删除')
      await loadData()
    } catch (err) {
      showMessage('error', '删除失败')
    }
  }

  const handleViewJD = async (id: string) => {
    setJdLoading(true)
    try {
      const detail = await getJD(id)
      setViewingJD(detail)
    } catch {
      showMessage('error', '加载JD失败')
    } finally {
      setJdLoading(false)
    }
  }

  const handleOCR = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      showMessage('error', '仅支持 JPG/PNG/WebP 格式')
      return
    }
    setOcrLoading(true)
    try {
      const base64 = await fileToBase64(file)
      await doOCR(base64)
    } finally {
      setOcrLoading(false)
      e.target.value = ''
    }
  }

  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (!file) continue
        setOcrLoading(true)
        try {
          const base64 = await fileToBase64(file)
          await doOCR(base64)
        } finally {
          setOcrLoading(false)
        }
        return
      }
    }
  }

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        resolve(result.split(',')[1])
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  const doOCR = async (base64: string) => {
    try {
      const result = await ocrJD(base64)
      if (result.success && result.text) {
        setJdText(prev => prev ? prev + '\n' + result.text : result.text)
        showMessage('success', '图片识别成功，已填入文本框')
      } else {
        const errMsg = (result as any)?.error || '识别失败'
        showMessage('error', `OCR 失败: ${errMsg}`)
      }
    } catch (err) {
      showMessage('error', `OCR 请求失败: ${err instanceof Error ? err.message : '网络错误'}`)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">简历RAG库</h2>

      {/* Message */}
      {message && (
        <div
          className={`mb-4 px-4 py-3 rounded-lg text-sm ${
            message.type === 'success'
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('resumes')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'resumes'
              ? 'border-primary-600 text-primary-700'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          我的简历 ({resumes.length})
        </button>
        <button
          onClick={() => setActiveTab('jds')}
          className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'jds'
              ? 'border-primary-600 text-primary-700'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          JD库 ({jds.length})
        </button>
      </div>

      {/* Resume Tab */}
      {activeTab === 'resumes' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Upload Section */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <Upload size={16} />
              上传新简历
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">版本名称</label>
                <input
                  type="text"
                  value={resumeName}
                  onChange={(e) => setResumeName(e.target.value)}
                  placeholder="如：通用版、Java后端岗"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">简历文件</label>
                <div className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center hover:border-primary-400 transition-colors cursor-pointer">
                  <input
                    type="file"
                    accept=".pdf,.docx,.md,.txt"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <Upload size={28} className="mx-auto text-gray-300 mb-2" />
                    <p className="text-sm text-gray-500">
                      {selectedFile ? selectedFile.name : '点击上传 PDF / DOCX / Markdown'}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">最大 10MB</p>
                  </label>
                </div>
              </div>
              {/* Photo Upload */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">证件照（可选）</label>
                {photoPreview ? (
                  <div className="relative inline-block">
                    <img
                      src={photoPreview}
                      alt="证件照预览"
                      className="w-20 h-26 object-cover rounded-lg border border-gray-200"
                    />
                    <button
                      onClick={() => {
                        setSelectedPhoto(null)
                        setPhotoPreview(null)
                      }}
                      className="absolute -top-1 -right-1 p-0.5 bg-red-500 text-white rounded-full"
                      title="移除照片"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <div className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center hover:border-primary-400 transition-colors cursor-pointer">
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png"
                      onChange={handlePhotoChange}
                      className="hidden"
                      id="photo-upload"
                    />
                    <label htmlFor="photo-upload" className="cursor-pointer">
                      <Image size={22} className="mx-auto text-gray-300 mb-1" />
                      <p className="text-xs text-gray-400">上传证件照</p>
                      <p className="text-xs text-gray-300">JPG/PNG · 最大 2MB</p>
                    </label>
                  </div>
                )}
              </div>

              <button
                onClick={handleUpload}
                disabled={!selectedFile || !resumeName.trim() || uploading}
                className="w-full py-2.5 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    解析中...
                  </>
                ) : (
                  <>
                    <Plus size={16} />
                    上传并解析
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Resume List */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <FileText size={16} />
              简历列表
            </h3>
            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2 size={24} className="animate-spin text-gray-300" />
              </div>
            ) : resumes.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <FileText size={40} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">还没有简历</p>
                <p className="text-xs mt-1">上传第一份简历开始使用</p>
              </div>
            ) : (
              <div className="space-y-2">
                {resumes.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-700 truncate">{r.name}</p>
                      <p className="text-xs text-gray-400">
                        {r.source_format?.toUpperCase()} · {r.chunk_count} chunks ·{' '}
                        {r.created_at ? new Date(r.created_at).toLocaleDateString('zh-CN') : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 ml-3">
                      <button
                        onClick={() => handleDeleteResume(r.id, r.name)}
                        className="p-2 text-red-400 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* JD Tab */}
      {activeTab === 'jds' && (
        <div className="grid grid-cols-2 gap-6">
          {/* JD Input */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">新增 JD</h3>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">职位名称 *</label>
                  <input
                    type="text"
                    value={jdTitle}
                    onChange={(e) => setJdTitle(e.target.value)}
                    placeholder="如：Java后端开发工程师"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">公司名称</label>
                  <input
                    type="text"
                    value={jdCompany}
                    onChange={(e) => setJdCompany(e.target.value)}
                    placeholder="如：字节跳动"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">JD 原文 *</label>
                  <label className="flex items-center gap-1 text-xs text-primary-600 cursor-pointer hover:text-primary-700">
                    {ocrLoading ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <ScanLine size={14} />
                    )}
                    {ocrLoading ? '识别中...' : '上传图片识别'}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleOCR}
                      className="hidden"
                    />
                  </label>
                </div>
                <textarea
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  onPaste={handlePaste}
                  placeholder="粘贴职位描述文本，或直接 Ctrl+V 粘贴截图..."
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-vertical"
                />
              </div>
              <button
                onClick={handleCreateJD}
                disabled={!jdText.trim() || !jdTitle.trim()}
                className="w-full py-2.5 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                保存并解析 JD
              </button>
            </div>
          </div>

          {/* JD List */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">JD 列表</h3>
            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2 size={24} className="animate-spin text-gray-300" />
              </div>
            ) : jds.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <FileText size={40} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">还没有保存的 JD</p>
              </div>
            ) : (
              <div className="space-y-2">
                {jds.map((jd) => (
                  <div
                    key={jd.id}
                    className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-700 truncate">{jd.title}</p>
                      <p className="text-xs text-gray-400">
                        {jd.company || '未指定公司'} ·{' '}
                        {jd.created_at ? new Date(jd.created_at).toLocaleDateString('zh-CN') : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 ml-2">
                      <Link
                        to={`/jd-restructure/${jd.id}`}
                        className="px-2.5 py-1.5 text-xs font-medium text-primary-600 bg-primary-50 hover:bg-primary-100 rounded-lg transition-colors"
                        title="基于此JD自动生成简历"
                      >
                        <Wand2 size={14} className="inline mr-1" />
                        制作简历
                      </Link>
                      <button
                        onClick={() => handleViewJD(jd.id)}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors"
                        title="查看详情"
                      >
                        <Eye size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteJD(jd.id, jd.title)}
                        className="p-2 text-red-400 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* JD 详情弹窗 */}
      {viewingJD && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setViewingJD(null)}>
          <div className="bg-white rounded-xl shadow-2xl w-[700px] max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 shrink-0">
              <div>
                <h3 className="text-sm font-semibold text-gray-800">{viewingJD.title}</h3>
                {viewingJD.company && <p className="text-xs text-gray-400 mt-0.5">{viewingJD.company}</p>}
              </div>
              <button onClick={() => setViewingJD(null)} className="p-1 hover:bg-gray-100 rounded-lg">
                <X size={18} className="text-gray-400" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-5">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">{viewingJD.raw_text}</pre>
            </div>
            {viewingJD.structured_requirements && (
              <div className="border-t border-gray-100 p-5 bg-gray-50 shrink-0">
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">AI 解析结果</h4>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono max-h-40 overflow-auto">
                  {JSON.stringify(viewingJD.structured_requirements, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      {/* JD 加载中 */}
      {jdLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <Loader2 size={32} className="animate-spin text-white" />
        </div>
      )}
    </div>
  )
}

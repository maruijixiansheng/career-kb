import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Edit3, Loader2, BookOpen, Code, Briefcase, FolderGit2, Award, Tag } from 'lucide-react'
import { listSkillEntries, createSkillEntry, deleteSkillEntry, updateSkillEntry } from '../services/api'
import type { SkillLibraryEntry } from '../types'

const TYPE_ICONS: Record<string, React.ReactNode> = {
  skill: <Code size={16} />,
  project: <FolderGit2 size={16} />,
  internship: <Briefcase size={16} />,
  certificate: <Award size={16} />,
  other: <Tag size={16} />,
}
const TYPE_LABELS: Record<string, string> = {
  skill: '技术栈', project: '项目', internship: '实习',
  certificate: '证书', other: '其他',
}

export default function SkillLibraryPage() {
  const [entries, setEntries] = useState<SkillLibraryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [filter, setFilter] = useState<string>('')

  // Form state
  const [editId, setEditId] = useState<string | null>(null)
  const [entryType, setEntryType] = useState('skill')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')
  const [importance, setImportance] = useState(3)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const list = await listSkillEntries(filter || undefined)
      setEntries(list)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  const showMsg = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3000)
  }

  const resetForm = () => {
    setEditId(null); setEntryType('skill'); setTitle(''); setContent(''); setTags(''); setImportance(3)
  }

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim()) return
    try {
      if (editId) {
        await updateSkillEntry(editId, { title: title.trim(), content: content.trim(), tags: tags.trim(), importance })
        showMsg('success', '已更新')
      } else {
        await createSkillEntry({
          entry_type: entryType, title: title.trim(), content: content.trim(),
          tags: tags.trim(), importance,
        })
        showMsg('success', '已添加')
      }
      resetForm(); setShowForm(false); await load()
    } catch {
      showMsg('error', '操作失败')
    }
  }

  const handleEdit = (e: SkillLibraryEntry) => {
    setEditId(e.id); setEntryType(e.entry_type); setTitle(e.title)
    setContent(e.content); setTags(e.tags || ''); setImportance(e.importance)
    setShowForm(true)
  }

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`删除 "${title}"？`)) return
    try { await deleteSkillEntry(id); showMsg('success', '已删除'); await load() }
    catch { showMsg('error', '删除失败') }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <BookOpen size={24} />
          技能库
        </h2>
        <button onClick={() => { resetForm(); setShowForm(!showForm) }}
          className="flex items-center gap-1 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700">
          <Plus size={16} /> 添加条目
        </button>
      </div>

      {message && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      {/* Add/Edit Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            {editId ? '编辑条目' : '新条目'}
          </h3>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">类型</label>
              <select value={entryType} onChange={e => setEntryType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
                {Object.entries(TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">标题 *</label>
              <input value={title} onChange={e => setTitle(e.target.value)}
                placeholder="技能名/项目名/公司名" className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">标签</label>
              <input value={tags} onChange={e => setTags(e.target.value)}
                placeholder="Python, CV, YOLO..." className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">重要度 {importance}</label>
              <input type="range" min={1} max={5} value={importance}
                onChange={e => setImportance(Number(e.target.value))} className="w-full" />
            </div>
          </div>
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-1">详细内容 *</label>
            <textarea value={content} onChange={e => setContent(e.target.value)}
              rows={5} placeholder="详细描述技能、项目职责、实习内容等..."
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-vertical" />
          </div>
          <div className="flex gap-2">
            <button onClick={handleSubmit}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700">
              {editId ? '更新' : '添加'}
            </button>
            <button onClick={() => { setShowForm(false); resetForm() }}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600">
              取消
            </button>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {['', 'skill', 'project', 'internship', 'certificate', 'other'].map(t => (
          <button key={t} onClick={() => setFilter(t)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${
              filter === t ? 'bg-primary-100 text-primary-700 border-primary-300'
                : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-50'}`}>
            {t ? TYPE_LABELS[t] : '全部'} {t ? `(${entries.filter(e => e.entry_type === t).length})` : `(${entries.length})`}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-gray-300" /></div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <BookOpen size={40} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">技能库为空</p>
          <p className="text-xs mt-1">手动添加技术栈、项目经历等内容，重组简历时会自动检索匹配</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {entries.map(e => (
            <div key={e.id} className="bg-white rounded-lg border border-gray-100 shadow-sm p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">{TYPE_ICONS[e.entry_type]}</span>
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{TYPE_LABELS[e.entry_type]}</span>
                  <span className="text-xs text-gray-400">{'⭐'.repeat(e.importance)}</span>
                </div>
                <div className="flex gap-1">
                  <button onClick={() => handleEdit(e)} className="p-1 text-gray-400 hover:text-primary-600"><Edit3 size={14} /></button>
                  <button onClick={() => handleDelete(e.id, e.title)} className="p-1 text-gray-400 hover:text-red-500"><Trash2 size={14} /></button>
                </div>
              </div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">{e.title}</h4>
              <p className="text-xs text-gray-500 line-clamp-3">{e.content}</p>
              {e.tags && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {e.tags.split(',').filter(Boolean).slice(0, 5).map((t, i) => (
                    <span key={i} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">{t.trim()}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

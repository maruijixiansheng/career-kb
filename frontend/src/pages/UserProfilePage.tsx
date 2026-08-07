import { useState, useEffect } from 'react'
import {
  User, Mail, Phone, MapPin, Briefcase, GraduationCap,
  Building, BookOpen, FileText, Target, DollarSign, Clock,
  Edit3, Save, X, Loader2,
} from 'lucide-react'
import { getUserProfile, updateUserProfile } from '../services/api'
import type { UserProfile, UserProfileUpdate } from '../types'
import { EDUCATION_OPTIONS, JOB_STATUS_OPTIONS } from '../types'

export default function UserProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [form, setForm] = useState<UserProfileUpdate>({})

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    setLoading(true)
    try {
      const data = await getUserProfile()
      setProfile(data)
    } catch {
      showMsg('error', '加载失败')
    } finally {
      setLoading(false)
    }
  }

  const showMsg = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 3000)
  }

  const handleEdit = () => {
    setForm({
      name: profile?.name || '',
      email: profile?.email || '',
      phone: profile?.phone || '',
      city: profile?.city || '',
      current_role: profile?.current_role || '',
      years_of_experience: profile?.years_of_experience ?? undefined,
      education: profile?.education || '',
      school: profile?.school || '',
      major: profile?.major || '',
      summary: profile?.summary || '',
      expected_role: profile?.expected_role || '',
      expected_salary: profile?.expected_salary || '',
      job_status: profile?.job_status || '',
    })
    setMode('edit')
  }

  const handleCancel = () => {
    setMode('view')
  }

  const handleSave = async () => {
    if (!form.name?.trim()) {
      showMsg('error', '请至少填写姓名')
      return
    }
    setSaving(true)
    try {
      const updated = await updateUserProfile(form)
      setProfile(updated)
      showMsg('success', '保存成功')
      setMode('view')
    } catch {
      showMsg('error', '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const updateField = (field: keyof UserProfileUpdate, value: string | number | undefined) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 size={32} className="animate-spin text-primary-500" />
      </div>
    )
  }

  const fieldValue = (key: keyof UserProfile) => {
    const val = profile?.[key]
    if (!val && val !== 0) return <span className="text-gray-300">未填写</span>
    return <span className="text-gray-800">{String(val)}</span>
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
          <User size={24} />
          个人信息
        </h2>
        {mode === 'view' && (
          <button
            onClick={handleEdit}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors"
          >
            <Edit3 size={16} />
            编辑资料
          </button>
        )}
      </div>

      {/* Message Toast */}
      {message && (
        <div
          className={`mb-4 px-4 py-2.5 rounded-lg text-sm font-medium ${
            message.type === 'success'
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Content */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
        {mode === 'view' ? (
          /* ===== View Mode ===== */
          <div className="p-6">
            {/* Basic Info Section */}
            <Section title="基本信息">
              <div className="grid grid-cols-2 gap-4">
                <Field icon={<User size={16} />} label="姓名" value={fieldValue('name')} />
                <Field icon={<Mail size={16} />} label="邮箱" value={fieldValue('email')} />
                <Field icon={<Phone size={16} />} label="手机号" value={fieldValue('phone')} />
                <Field icon={<MapPin size={16} />} label="所在城市" value={fieldValue('city')} />
              </div>
            </Section>

            <Section title="职业背景">
              <div className="grid grid-cols-2 gap-4">
                <Field icon={<Briefcase size={16} />} label="当前职位" value={fieldValue('current_role')} />
                <Field icon={<Clock size={16} />} label="工作年限" value={fieldValue('years_of_experience')} />
                <Field icon={<GraduationCap size={16} />} label="最高学历" value={fieldValue('education')} />
                <Field icon={<Building size={16} />} label="毕业院校" value={fieldValue('school')} />
                <Field icon={<BookOpen size={16} />} label="专业" value={fieldValue('major')} />
              </div>
            </Section>

            <Section title="个人简介">
              <Field
                icon={<FileText size={16} />}
                label="简介"
                value={
                  profile?.summary ? (
                    <span className="text-gray-800 whitespace-pre-wrap">{profile.summary}</span>
                  ) : (
                    <span className="text-gray-300">未填写</span>
                  )
                }
              />
            </Section>

            <Section title="求职意向">
              <div className="grid grid-cols-2 gap-4">
                <Field icon={<Target size={16} />} label="期望职位" value={fieldValue('expected_role')} />
                <Field icon={<DollarSign size={16} />} label="期望薪资" value={fieldValue('expected_salary')} />
                <Field icon={<Briefcase size={16} />} label="求职状态" value={fieldValue('job_status')} />
              </div>
            </Section>
          </div>
        ) : (
          /* ===== Edit Mode ===== */
          <div className="p-6">
            <Section title="基本信息">
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  icon={<User size={16} />}
                  label="姓名"
                  value={form.name || ''}
                  onChange={v => updateField('name', v)}
                  placeholder="请输入姓名"
                  required
                />
                <InputField
                  icon={<Mail size={16} />}
                  label="邮箱"
                  value={form.email || ''}
                  onChange={v => updateField('email', v)}
                  placeholder="请输入邮箱"
                />
                <InputField
                  icon={<Phone size={16} />}
                  label="手机号"
                  value={form.phone || ''}
                  onChange={v => updateField('phone', v)}
                  placeholder="请输入手机号"
                />
                <InputField
                  icon={<MapPin size={16} />}
                  label="所在城市"
                  value={form.city || ''}
                  onChange={v => updateField('city', v)}
                  placeholder="请输入所在城市"
                />
              </div>
            </Section>

            <Section title="职业背景">
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  icon={<Briefcase size={16} />}
                  label="当前职位"
                  value={form.current_role || ''}
                  onChange={v => updateField('current_role', v)}
                  placeholder="例如：前端开发工程师"
                />
                <div className="space-y-1">
                  <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1">
                    <Clock size={16} className="text-gray-400" />
                    工作年限
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={50}
                    value={form.years_of_experience ?? ''}
                    onChange={e => updateField('years_of_experience', e.target.value ? Number(e.target.value) : undefined)}
                    placeholder="例如：3"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400"
                  />
                </div>
                <div className="space-y-1">
                  <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1">
                    <GraduationCap size={16} className="text-gray-400" />
                    最高学历
                  </label>
                  <select
                    value={form.education || ''}
                    onChange={e => updateField('education', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400"
                  >
                    <option value="">请选择</option>
                    {EDUCATION_OPTIONS.map(opt => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
                <InputField
                  icon={<Building size={16} />}
                  label="毕业院校"
                  value={form.school || ''}
                  onChange={v => updateField('school', v)}
                  placeholder="请输入毕业院校"
                />
                <InputField
                  icon={<BookOpen size={16} />}
                  label="专业"
                  value={form.major || ''}
                  onChange={v => updateField('major', v)}
                  placeholder="请输入专业"
                />
              </div>
            </Section>

            <Section title="个人简介">
              <div className="space-y-1">
                <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1">
                  <FileText size={16} className="text-gray-400" />
                  简介
                </label>
                <textarea
                  value={form.summary || ''}
                  onChange={e => updateField('summary', e.target.value)}
                  rows={4}
                  placeholder="简单介绍一下自己，例如：5年前端开发经验，熟悉React和TypeScript..."
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400 resize-none"
                />
              </div>
            </Section>

            <Section title="求职意向">
              <div className="grid grid-cols-2 gap-4">
                <InputField
                  icon={<Target size={16} />}
                  label="期望职位"
                  value={form.expected_role || ''}
                  onChange={v => updateField('expected_role', v)}
                  placeholder="例如：高级前端工程师"
                />
                <InputField
                  icon={<DollarSign size={16} />}
                  label="期望薪资"
                  value={form.expected_salary || ''}
                  onChange={v => updateField('expected_salary', v)}
                  placeholder="例如：25K-35K"
                />
                <div className="space-y-1">
                  <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1">
                    <Briefcase size={16} className="text-gray-400" />
                    求职状态
                  </label>
                  <select
                    value={form.job_status || ''}
                    onChange={e => updateField('job_status', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400"
                  >
                    <option value="">请选择</option>
                    {JOB_STATUS_OPTIONS.map(opt => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                </div>
              </div>
            </Section>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-gray-100">
              <button
                onClick={handleCancel}
                className="flex items-center gap-1.5 px-4 py-2 text-gray-600 bg-gray-100 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                <X size={16} />
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors disabled:opacity-50"
              >
                {saving ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ===== Sub-components =====

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h3>
      {children}
    </div>
  )
}

function Field({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span className="text-gray-400 mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <p className="text-xs text-gray-400 mb-0.5">{label}</p>
        <p className="text-sm">{value}</p>
      </div>
    </div>
  )
}

function InputField({
  icon,
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  icon: React.ReactNode
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  required?: boolean
}) {
  return (
    <div className="space-y-1">
      <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1">
        {icon && <span className="text-gray-400">{icon}</span>}
        {label}
        {required && <span className="text-red-400">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400"
      />
    </div>
  )
}

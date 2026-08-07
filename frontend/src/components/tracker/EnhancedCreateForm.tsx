import { useState, useRef } from 'react'
import type { CompanyAutocompleteResponse, PositionAutocompleteResponse } from '../../types'
import { CHANNELS } from '../../types'
import { autocompleteCompany, autocompletePosition, ocrJD } from '../../services/api'

interface Props {
  onCreated: () => void
  onCancel: () => void
}

export default function EnhancedCreateForm({ onCreated, onCancel }: Props) {
  const [form, setForm] = useState({
    company: '', position: '', channel: 'other', notes: '', jdText: '',
  })
  const [companyInfo, setCompanyInfo] = useState<CompanyAutocompleteResponse | null>(null)
  const [positionInfo, setPositionInfo] = useState<PositionAutocompleteResponse | null>(null)
  const [companyLoading, setCompanyLoading] = useState(false)
  const [positionLoading, setPositionLoading] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleCompanyBlur = async () => {
    if (!form.company.trim() || form.company.length < 2) return
    setCompanyLoading(true)
    try {
      const info = await autocompleteCompany(form.company)
      setCompanyInfo(info)
    } catch { /* ignore */ }
    setCompanyLoading(false)
  }

  const handlePositionBlur = async () => {
    if (!form.position.trim() || form.position.length < 2) return
    setPositionLoading(true)
    try {
      const info = await autocompletePosition(form.position, companyInfo?.industry)
      setPositionInfo(info)
    } catch { /* ignore */ }
    setPositionLoading(false)
  }

  const handleOCR = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setOcrLoading(true)
    try {
      const reader = new FileReader()
      reader.onload = async () => {
        const base64 = (reader.result as string).split(',')[1]
        const result = await ocrJD(base64)
        if (result.success && result.text) {
          setForm(f => ({ ...f, jdText: result.text }))
        }
      }
      reader.readAsDataURL(file)
    } catch { /* ignore */ }
    setOcrLoading(false)
  }

  const handleSubmit = async () => {
    if (!form.company || !form.position) return
    setSubmitting(true)
    try {
      const { createApplication } = await import('../../services/api')
      await createApplication({
        company: form.company,
        position: form.position,
        channel: form.channel,
        notes: form.jdText || form.notes || undefined,
        status: 'applied',
      })
      onCreated()
    } catch { /* ignore */ }
    setSubmitting(false)
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border p-4 mb-4">
      <h3 className="font-medium text-gray-700 mb-3">新增投递</h3>

      <div className="grid grid-cols-2 gap-3">
        {/* 公司名 + AI 补全 */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">公司名称 *</label>
          <div className="flex gap-1">
            <input
              value={form.company}
              onChange={e => { setForm({ ...form, company: e.target.value }); setCompanyInfo(null) }}
              onBlur={handleCompanyBlur}
              className="flex-1 border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              placeholder="如: 字节跳动"
            />
            {companyLoading && <span className="text-xs text-gray-400 self-center">查询中...</span>}
          </div>
          {companyInfo && companyInfo.confidence !== 'low' && (
            <div className="mt-1 text-xs text-gray-500 bg-blue-50 rounded p-2">
              {companyInfo.industry && <span className="mr-2">📌 {companyInfo.industry}</span>}
              {companyInfo.company_size && <span className="mr-2">👥 {companyInfo.company_size}</span>}
              {companyInfo.headquarters && <span>📍 {companyInfo.headquarters}</span>}
            </div>
          )}
        </div>

        {/* 岗位名 + AI 补全 */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">岗位名称 *</label>
          <input
            value={form.position}
            onChange={e => { setForm({ ...form, position: e.target.value }); setPositionInfo(null) }}
            onBlur={handlePositionBlur}
            className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="如: 高级后端工程师"
          />
          {positionLoading && <span className="text-xs text-gray-400">查询中...</span>}
          {positionInfo?.typical_requirements && (() => {
            const req = positionInfo.typical_requirements as any
            return (
              <div className="mt-1 text-xs text-gray-500 bg-green-50 rounded p-2">
                {req.key_skills && <p>🛠 {req.key_skills}</p>}
                {positionInfo.salary_range && <p className="mt-1">💰 {positionInfo.salary_range}</p>}
              </div>
            )
          })()}
        </div>

        {/* 投递渠道 */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">投递渠道</label>
          <select
            value={form.channel}
            onChange={e => setForm({ ...form, channel: e.target.value })}
            className="w-full border rounded px-3 py-1.5 text-sm"
          >
            {Object.entries(CHANNELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        {/* JD 截图 OCR */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">JD 截图 (OCR)</label>
          <div className="flex gap-1">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleOCR}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-1.5 text-sm border rounded text-gray-600 hover:bg-gray-50"
              disabled={ocrLoading}
            >
              {ocrLoading ? '识别中...' : '📷 上传截图'}
            </button>
            {form.jdText && <span className="text-xs text-green-500 self-center">已识别 {form.jdText.length} 字</span>}
          </div>
        </div>
      </div>

      {/* JD 文本 (OCR 结果或手动粘贴) */}
      <div className="mt-3">
        <label className="block text-xs text-gray-500 mb-1">JD 文本 / 备注</label>
        <textarea
          value={form.jdText || form.notes}
          onChange={e => setForm({ ...form, notes: e.target.value, jdText: e.target.value })}
          className="w-full border rounded px-3 py-1.5 text-sm h-20 focus:outline-none focus:ring-2 focus:ring-blue-300"
          placeholder="粘贴 JD 文本或备注信息..."
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 mt-3">
        <button onClick={onCancel} className="px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700">取消</button>
        <button
          onClick={handleSubmit}
          disabled={submitting || !form.company || !form.position}
          className="px-4 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {submitting ? '添加中...' : '添加投递'}
        </button>
      </div>
    </div>
  )
}

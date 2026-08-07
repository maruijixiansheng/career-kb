import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Briefcase, Target, MessageSquare, ArrowRight } from 'lucide-react'
import { listResumes } from '../services/api'
import type { Resume } from '../types'

export default function Dashboard() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listResumes()
      .then(setResumes)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const stats = [
    { label: '简历版本', value: resumes.length, icon: FileText, color: 'blue' },
    { label: '投递记录', value: 0, icon: Briefcase, color: 'green' },
    { label: '技能分析', value: 0, icon: Target, color: 'purple' },
    { label: '模拟面试', value: 0, icon: MessageSquare, color: 'orange' },
  ]

  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">仪表盘</h2>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className="text-3xl font-bold text-gray-800 mt-1">
                  {loading ? '-' : stat.value}
                </p>
              </div>
              <div className={`p-3 rounded-lg ${colorMap[stat.color]}`}>
                <stat.icon size={24} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mb-8">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">快捷操作</h3>
        <div className="flex gap-3">
          <Link
            to="/resumes"
            className="flex items-center gap-2 px-4 py-2.5 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors"
          >
            <FileText size={16} />
            管理简历
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>

      {/* Recent Resumes */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-800">我的简历</h3>
          <Link to="/resumes" className="text-sm text-primary-600 hover:text-primary-700">
            查看全部 →
          </Link>
        </div>
        {loading ? (
          <p className="text-gray-400 text-sm">加载中...</p>
        ) : resumes.length === 0 ? (
          <div className="text-center py-8">
            <FileText size={48} className="mx-auto text-gray-300 mb-3" />
            <p className="text-gray-400">还没有上传简历</p>
            <Link
              to="/resumes"
              className="inline-block mt-3 text-sm text-primary-600 hover:text-primary-700"
            >
              立即上传 →
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {resumes.slice(0, 5).map((r) => (
              <Link
                key={r.id}
                to="/resumes"
                className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-gray-700">{r.name}</p>
                  <p className="text-xs text-gray-400">
                    {r.source_format?.toUpperCase()} · {r.chunk_count} 个分块
                  </p>
                </div>
                <ArrowRight size={16} className="text-gray-300" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

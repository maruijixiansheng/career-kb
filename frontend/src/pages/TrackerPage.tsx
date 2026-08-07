import { useState, useEffect, useCallback } from 'react'
import type { Application, ApplicationStats } from '../types'
import { KANBAN_COLUMNS } from '../types'
import {
  listApplications,
  updateApplication,
  deleteApplication,
  getApplicationStats,
} from '../services/api'
import KanbanColumn from '../components/tracker/KanbanColumn'
import NoResponseModal from '../components/tracker/NoResponseModal'
import EnhancedCreateForm from '../components/tracker/EnhancedCreateForm'
import InterviewFeedback from '../components/tracker/InterviewFeedback'

export default function TrackerPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [stats, setStats] = useState<ApplicationStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyzingApp, setAnalyzingApp] = useState<Application | null>(null)
  const [feedbackApp, setFeedbackApp] = useState<Application | null>(null)

  // 新建投递表单
  const [showForm, setShowForm] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [apps, s] = await Promise.all([listApplications(), getApplicationStats()])
      setApplications(apps)
      setStats(s)
    } catch (e) {
      console.error('Failed to load applications:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleStatusChange = async (id: string, toStatus: string) => {
    try {
      await updateApplication(id, { status: toStatus })
      loadData()
    } catch (e) {
      console.error('Failed to update status:', e)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除这条投递记录？')) return
    try {
      await deleteApplication(id)
      loadData()
    } catch (e) {
      console.error('Failed to delete:', e)
    }
  }

  const handleAnalyzeAction = (action: string) => {
    if (action === 'follow_up') {
      handleStatusChange(analyzingApp!.id, 'waiting')
    }
    setAnalyzingApp(null)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-6 w-6 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  // 按看板列分组
  const columns = KANBAN_COLUMNS.map(col => ({
    ...col,
    items: applications.filter(a => {
      if (col.key === 'interview_1') return ['interview_1', 'interview_2', 'interview_3'].includes(a.status)
      if (col.key === 'rejected') return a.status === 'rejected'
      if (col.key === 'accepted') return a.status === 'accepted'
      return a.status === col.key
    }),
  }))

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-800">求职追踪</h1>
          {stats && (
            <p className="text-sm text-gray-500 mt-1">
              共投递 <strong>{stats.total}</strong> 份 |{' '}
              初筛 {stats.by_status.resume_screening || 0} |{' '}
              面试 {stats.by_status.interview_1 || 0} |{' '}
              Offer {stats.by_status.offer || 0}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600"
        >
          + 新增投递
        </button>
      </div>

      {/* Enhanced Create Form */}
      {showForm && (
        <EnhancedCreateForm
          onCreated={() => { setShowForm(false); loadData() }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto">
        <div className="flex gap-3 pb-4 min-w-max">
          {columns.map(col => (
            <KanbanColumn
              key={col.key}
              title={col.label}
              color={col.color}
              applications={col.items}
              onStatusChange={handleStatusChange}
              onAnalyze={setAnalyzingApp}
              onFeedback={setFeedbackApp}
            />
          ))}
        </div>
      </div>

      {/* No Response Analysis Modal */}
      {analyzingApp && (
        <NoResponseModal
          application={analyzingApp}
          onClose={() => setAnalyzingApp(null)}
          onAction={handleAnalyzeAction}
        />
      )}

      {/* Interview Feedback Modal */}
      {feedbackApp && (
        <InterviewFeedback
          application={feedbackApp}
          onClose={() => setFeedbackApp(null)}
          onSaved={() => { setFeedbackApp(null); loadData() }}
        />
      )}
    </div>
  )
}

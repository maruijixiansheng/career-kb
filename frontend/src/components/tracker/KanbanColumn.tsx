import type { Application } from '../../types'
import ApplicationCard from './ApplicationCard'

interface Props {
  title: string
  color: string
  applications: Application[]
  onStatusChange: (id: string, toStatus: string) => void
  onAnalyze: (app: Application) => void
  onFeedback: (app: Application) => void
}

export default function KanbanColumn({ title, color, applications, onStatusChange, onAnalyze, onFeedback }: Props) {
  return (
    <div className={`flex-shrink-0 w-64 bg-gray-50 rounded-lg border-t-2 ${color} flex flex-col`}>
      <div className="p-3 flex items-center justify-between">
        <h3 className="font-medium text-gray-700 text-sm">{title}</h3>
        <span className="text-xs text-gray-400 bg-gray-200 rounded-full px-2 py-0.5">
          {applications.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 min-h-[200px]">
        {applications.map(app => (
          <ApplicationCard
            key={app.id}
            app={app}
            onStatusChange={onStatusChange}
            onAnalyze={onAnalyze}
            onFeedback={onFeedback}
          />
        ))}
        {applications.length === 0 && (
          <div className="text-center text-gray-300 text-xs py-8">暂无</div>
        )}
      </div>
    </div>
  )
}

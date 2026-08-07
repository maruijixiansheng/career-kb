import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  KanbanSquare,
  Radar,
  MessageSquare,
  BookOpen,
  User,
  LogOut,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/profile', icon: User, label: '个人信息' },
  { to: '/resumes', icon: FileText, label: '简历RAG库' },
  { to: '/skill-library', icon: BookOpen, label: '技能库' },
  { to: '/tracker', icon: KanbanSquare, label: '求职追踪' },
  { to: '/skills', icon: Radar, label: '技能Gap分析' },
  { to: '/interview', icon: MessageSquare, label: '面试模拟' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-gray-100">
        <h1 className="text-sm font-bold text-primary-700 truncate">
          职业知识管家
        </h1>
      </div>

      {/* User Info */}
      {user && (
        <div className="px-4 py-2 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-700 truncate">{user.name}</p>
          <p className="text-xs text-gray-400 truncate">{user.email}</p>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <item.icon size={18} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-gray-100 space-y-2">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
        >
          <LogOut size={14} />
          <span>退出登录</span>
        </button>
        <p className="text-xs text-gray-400 text-center">v0.2.0 · Phase 2</p>
      </div>
    </aside>
  )
}

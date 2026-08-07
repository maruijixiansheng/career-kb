import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import ProtectedRoute from './components/auth/ProtectedRoute'
import Dashboard from './pages/Dashboard'
import ResumePage from './pages/ResumePage'
import RestructurePage from './pages/RestructurePage'
import TrackerPage from './pages/TrackerPage'
import SkillsPage from './pages/SkillsPage'
import InterviewPage from './pages/InterviewPage'
import SkillLibraryPage from './pages/SkillLibraryPage'
import UserProfilePage from './pages/UserProfilePage'
import JDRestructurePage from './pages/JDRestructurePage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

export default function App() {
  return (
    <Routes>
      {/* 公开路由（无需登录） */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* 受保护路由（需登录） */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/resumes" element={<ResumePage />} />
        <Route path="/resumes/:id/restructure" element={<RestructurePage />} />
        <Route path="/skill-library" element={<SkillLibraryPage />} />
        <Route path="/tracker" element={<TrackerPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/interview" element={<InterviewPage />} />
        <Route path="/profile" element={<UserProfilePage />} />
        <Route path="/jd-restructure/:jdId" element={<JDRestructurePage />} />
      </Route>
    </Routes>
  )
}


import axios from 'axios'
import type {
  Resume,
  ResumeDetail,
  ResumeChunk,
  JobDescription,
  JDDetail,
  RestructureRequest,
  RestructureResponse,
  Application,
  ApplicationStats,
  ApplicationCreate,
  ApplicationUpdate,
  NoResponseAnalysisRequest,
  NoResponseAnalysisResponse,
  ApplicationTimelineEvent,
  CompanyAutocompleteResponse,
  PositionAutocompleteResponse,
  InterviewFeedbackResponse,
  JDTechStack,
  GapAnalysisResult,
  UserProfile,
  UserProfileUpdate,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 请求拦截器：自动附加 JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 自动跳转登录页
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      // 避免在登录页本身触发循环跳转
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

// ===== 简历 API =====

export async function uploadResume(file: File, name: string, photo?: File | null): Promise<Resume> {
  const form = new FormData()
  form.append('file', file)
  form.append('name', name)
  if (photo) form.append('photo', photo)
  const { data } = await api.post('/resumes/upload', form)
  return data
}

export async function listResumes(): Promise<Resume[]> {
  const { data } = await api.get('/resumes')
  return data
}

export async function getResume(id: string): Promise<ResumeDetail> {
  const { data } = await api.get(`/resumes/${id}`)
  return data
}

export async function getResumeChunks(id: string): Promise<ResumeChunk[]> {
  const { data } = await api.get(`/resumes/${id}/chunks`)
  return data
}

export async function deleteResume(id: string): Promise<void> {
  await api.delete(`/resumes/${id}`)
}

export async function restructureResume(
  resumeId: string,
  request: RestructureRequest
): Promise<RestructureResponse> {
  const { data } = await api.post(`/resumes/${resumeId}/restructure`, request)
  return data
}

export async function downloadPdfResume(
  resumeId: string,
  markdown: string,
  title?: string,
): Promise<void> {
  const token = localStorage.getItem('access_token')
  const response = await fetch(`/api/resumes/${resumeId}/generate-pdf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ markdown, title }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'PDF 生成失败' }))
    throw new Error(err.detail || `HTTP ${response.status}`)
  }
  const blob = await response.blob()
  // 从 Content-Disposition 头提取文件名，或使用默认名
  const disposition = response.headers.get('Content-Disposition')
  let filename = '定制简历.pdf'
  if (disposition) {
    const match = disposition.match(/filename\*=UTF-8''(.+)/)
    if (match) {
      filename = decodeURIComponent(match[1])
    }
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ===== JD API =====

export async function createJD(title: string, rawText: string, company?: string): Promise<JobDescription> {
  const { data } = await api.post('/jds', { title, raw_text: rawText, company })
  return data
}

export async function listJDs(): Promise<JobDescription[]> {
  const { data } = await api.get('/jds')
  return data
}

export async function getJD(id: string): Promise<JDDetail> {
  const { data } = await api.get(`/jds/${id}`)
  return data
}

export async function deleteJD(id: string): Promise<void> {
  await api.delete(`/jds/${id}`)
}

// ===== 流式简历重组 =====

export function restructureResumeStream(
  resumeId: string,
  request: RestructureRequest,
  onEvent: (event: { type: string; [key: string]: unknown }) => void,
  onError: (error: Error) => void,
): AbortController {
  const controller = new AbortController()

  const token = localStorage.getItem('access_token')
  fetch(`/api/resumes/${resumeId}/restructure/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const reader = response.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              onEvent(event)
            } catch {
              // 跳过解析失败的行
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err)
      }
    })

  return controller
}

// ===== 求职追踪 API =====

export async function createApplication(data: ApplicationCreate): Promise<Application> {
  const { data: result } = await api.post('/applications', data)
  return result
}

export async function listApplications(status?: string): Promise<Application[]> {
  const params = status ? { status } : {}
  const { data } = await api.get('/applications', { params })
  return data
}

export async function getApplication(id: string): Promise<Application> {
  const { data } = await api.get(`/applications/${id}`)
  return data
}

export async function updateApplication(id: string, data: ApplicationUpdate): Promise<Application> {
  const { data: result } = await api.patch(`/applications/${id}`, data)
  return result
}

export async function deleteApplication(id: string): Promise<void> {
  await api.delete(`/applications/${id}`)
}

export async function getApplicationStats(): Promise<ApplicationStats> {
  const { data } = await api.get('/applications/stats')
  return data
}

export async function runNoResponseAnalysis(
  applicationId: string,
  days_since_apply: number,
): Promise<NoResponseAnalysisResponse> {
  const { data } = await api.post(`/applications/${applicationId}/no-response-analysis`, {
    days_since_apply,
  })
  return data
}

export async function getApplicationTimeline(id: string): Promise<ApplicationTimelineEvent[]> {
  const { data } = await api.get(`/applications/${id}/timeline`)
  return data
}

// ===== AI 辅助录入 API =====

export async function autocompleteCompany(name: string): Promise<CompanyAutocompleteResponse> {
  const { data } = await api.post('/ai/company-autocomplete', { company_name: name })
  return data
}

export async function autocompletePosition(name: string, industry?: string): Promise<PositionAutocompleteResponse> {
  const { data } = await api.post('/ai/position-autocomplete', { position_name: name, industry })
  return data
}

export async function ocrJD(imageBase64: string): Promise<{ text: string; success: boolean }> {
  const { data } = await api.post('/ai/ocr-jd', { image_base64: imageBase64 })
  return data
}

export async function speechToText(audioBase64: string): Promise<{ text: string; success: boolean }> {
  const { data } = await api.post('/ai/speech-to-text', { audio_base64: audioBase64 })
  return data
}

export async function saveInterviewFeedback(
  applicationId: string,
  feedback: string,
): Promise<InterviewFeedbackResponse> {
  const { data } = await api.post(`/applications/${applicationId}/interview-feedback`, { feedback })
  return data
}

// ===== 技能 Gap 分析 API (Phase 3) =====

export async function getJDTechStack(jdId: string): Promise<JDTechStack> {
  const { data } = await api.get(`/skills/jd/${jdId}/tech-stack`)
  return data
}

export async function runGapAnalysis(jdId: string, resumeId: string): Promise<{ jd_tech_stack: JDTechStack['tech_stack']; gap_analysis: GapAnalysisResult }> {
  const { data } = await api.post('/skills/gap-analysis', { jd_id: jdId, resume_id: resumeId })
  return data
}

// ===== 面试模拟 API (Phase 4) =====

export async function startInterview(jdId: string, resumeId: string, mode: string = 'mixed'): Promise<{
  session_id: string; question: string; question_number: number; total_questions: number
}> {
  const { data } = await api.post('/interview/start', { jd_id: jdId, resume_id: resumeId, mode })
  return data
}

export async function respondInterview(sessionId: string, answer: string): Promise<{
  finished: boolean; feedback?: string; question?: string; question_number?: number; total_questions?: number; report?: Record<string, unknown>
}> {
  const { data } = await api.post(`/interview/${sessionId}/respond`, { answer })
  return data
}

export async function getInterviewReport(sessionId: string): Promise<Record<string, unknown>> {
  const { data } = await api.get(`/interview/${sessionId}/report`)
  return data
}

// ===== 技能库 API =====
import type { SkillLibraryEntry } from '../types'

export async function createSkillEntry(params: {
  entry_type: string; title: string; content: string;
  tags?: string; start_date?: string; end_date?: string; importance?: number
}): Promise<SkillLibraryEntry> {
  const { data } = await api.post('/skill-library', params)
  return data
}

export async function listSkillEntries(entry_type?: string): Promise<SkillLibraryEntry[]> {
  const params = entry_type ? { entry_type } : {}
  const { data } = await api.get('/skill-library', { params })
  return data
}

export async function updateSkillEntry(id: string, params: Record<string, unknown>): Promise<void> {
  await api.put(`/skill-library/${id}`, null, { params })
}

export async function deleteSkillEntry(id: string): Promise<void> {
  await api.delete(`/skill-library/${id}`)
}

// ===== 智能重组 API =====

export async function smartRestructure(
  request: RestructureRequest & { resume_id?: string }
): Promise<RestructureResponse> {
  const { data } = await api.post('/resumes/smart-restructure', request)
  return data
}

// ===== 用户基本信息 API =====

export async function getUserProfile(): Promise<UserProfile> {
  const { data } = await api.get('/user-profile')
  return data
}

export async function updateUserProfile(update: UserProfileUpdate): Promise<UserProfile> {
  const { data } = await api.put('/user-profile', update)
  return data
}

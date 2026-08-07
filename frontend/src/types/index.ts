// ===== 简历 =====
export interface Resume {
  id: string
  name: string
  source_filename?: string
  source_format?: string
  chunk_count: number
  photo_url?: string
  has_photo?: boolean
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface ResumeDetail extends Resume {
  raw_text?: string
  structured_data?: Record<string, unknown>
}

export interface ResumeChunk {
  id: string
  section_type: string
  section_title?: string
  chunk_index: number
  content: string
  metadata?: Record<string, unknown>
  token_count?: number
}

// ===== JD =====
export interface JobDescription {
  id: string
  title: string
  company?: string
  created_at?: string
}

export interface JDDetail extends JobDescription {
  raw_text: string
  structured_requirements?: Record<string, unknown>
}

// ===== 简历重组 =====
export interface RestructureRequest {
  jd_id?: string
  jd_text?: string
  jd_title?: string
  jd_company?: string
}

export interface RestructureResponse {
  restructured_markdown: string
  changes_summary?: string
  match_score?: number
  fact_check?: FactCheckResult
}

export interface FactCheckResult {
  is_factual: boolean
  score: number
  issues: FactIssue[]
}

export interface FactIssue {
  location: string
  severity: 'error' | 'warning'
  original: string
  generated: string
  problem: string
}

// ===== 求职追踪 =====
export interface Application {
  id: string
  company: string
  position: string
  status: string
  channel?: string
  resume_id?: string
  jd_id?: string
  applied_at?: string
  next_action?: string
  next_due_date?: string
  salary_offer?: string
  notes?: string
  follow_up_notes?: string
  interview_feedback?: string
  interview_key_points?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface ApplicationStats {
  total: number
  by_status: Record<string, number>
  conversion_rates: Record<string, number>
}

// ===== PDF 生成 =====
export interface GeneratePdfRequest {
  markdown: string
}

// ===== Application API =====
export interface ApplicationCreate {
  jd_id?: string
  resume_id?: string
  company: string
  position: string
  status?: string
  channel?: string
  applied_at?: string
  notes?: string
}

export interface ApplicationUpdate {
  company?: string
  position?: string
  status?: string
  channel?: string
  next_action?: string
  next_due_date?: string
  salary_offer?: string
  notes?: string
  follow_up_notes?: string
}

// ===== AI 辅助录入 =====
export interface CompanyAutocompleteResponse {
  company_name: string
  industry?: string
  company_size?: string
  headquarters?: string
  is_listed?: boolean
  brief?: string
  confidence: string
}

export interface PositionAutocompleteResponse {
  position_name: string
  typical_requirements?: Record<string, unknown>
  typical_responsibilities?: string[]
  salary_range?: string
  career_path?: string
}

export interface InterviewFeedbackResponse {
  interview_key_points?: Record<string, unknown>
  error?: string
}

export const CHANNELS: Record<string, string> = {
  boss: 'BOSS直聘',
  website: '官网',
  referral: '内推',
  liepin: '猎聘',
  other: '其他',
}

// ===== 技能 Gap 分析 (Phase 3) =====
export interface JDSkill {
  skill: string
  category: string
  level_required: string
  is_required: boolean
  importance_weight: number
  reason: string
}

export interface JDTechStack {
  tech_stack: JDSkill[]
  total_weight: number
  primary_stack: string[]
  nice_to_have: string[]
  industry_context?: string
}

export interface GapMatchedSkill {
  skill: string
  jd_weight: number
  my_level: string
  required_level: string
  score_contribution: number
}

export interface GapPartialSkill {
  skill: string
  jd_weight: number
  my_level: string
  required_level: string
  gap_description: string
  effort_weeks: number
  score_contribution: number
}

export interface GapMissingSkill {
  skill: string
  jd_weight: number
  importance: string
  effort_weeks: number
  prerequisites: string[]
  score_contribution: number
}

export interface RadarDimension {
  name: string
  jd_weight: number
  my_level: number
}

export interface LearningPhase {
  phase: number
  title: string
  duration_weeks: number
  skills: string[]
  resources: { name: string; type: string; url: string; description: string }[]
  milestone: string
}

export interface GapAnalysisResult {
  weighted_score: number
  score_breakdown: { matched_weight: number; partial_weight: number; missing_weight: number; total_weight: number }
  matched_skills: GapMatchedSkill[]
  partial_skills: GapPartialSkill[]
  missing_skills: GapMissingSkill[]
  radar_data: { dimensions: RadarDimension[] }
  learning_path: { summary: string; total_weeks: number; phases: LearningPhase[] }
  weekly_plan: { week: number; focus: string; tasks: string[]; expected_hours: number }[]
}

// ===== 无回应分析 (Phase 2) =====
export interface NoResponseAnalysisRequest {
  days_since_apply: number
}

export interface NoResponseAnalysisResponse {
  analysis_result?: Record<string, unknown>
  follow_up_result?: Record<string, unknown>
  suggest_result?: Record<string, unknown>
  merged_summary?: string
  error?: string | null
}

export interface ApplicationTimelineEvent {
  id: string
  from_status?: string
  to_status: string
  comment?: string
  changed_at?: string
}

// ===== 状态映射 =====
export const STATUS_LABELS: Record<string, string> = {
  applied: '已投递',
  waiting: '等待回应',
  no_response: '无回应',
  resume_screening: '初筛中',
  written_test: '笔试',
  interview_1: '一面',
  interview_2: '二面',
  interview_3: '三面/终面',
  offer: '收到Offer',
  accepted: '已接受',
  rejected: '已拒绝',
  withdrawn: '已撤回',
}

export const STATUS_COLORS: Record<string, string> = {
  applied: 'bg-blue-100 text-blue-700',
  waiting: 'bg-yellow-100 text-yellow-700',
  no_response: 'bg-red-100 text-red-700',
  resume_screening: 'bg-purple-100 text-purple-700',
  written_test: 'bg-orange-100 text-orange-700',
  interview_1: 'bg-cyan-100 text-cyan-700',
  interview_2: 'bg-cyan-100 text-cyan-700',
  interview_3: 'bg-cyan-100 text-cyan-700',
  offer: 'bg-green-100 text-green-700',
  accepted: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  withdrawn: 'bg-gray-100 text-gray-700',
}

export const KANBAN_COLUMNS = [
  { key: 'applied', label: '已投递', color: 'border-blue-300' },
  { key: 'waiting', label: '等待回应', color: 'border-yellow-300' },
  { key: 'resume_screening', label: '初筛中', color: 'border-purple-300' },
  { key: 'written_test', label: '笔试', color: 'border-orange-300' },
  { key: 'interview_1', label: '面试', color: 'border-cyan-300' },
  { key: 'offer', label: 'Offer', color: 'border-green-300' },
  { key: 'rejected', label: '已拒绝', color: 'border-red-300' },
  { key: 'accepted', label: '已接受', color: 'border-green-300' },
] as const

// ===== SSE 事件 =====
export interface SSEEvent {
  type: 'progress' | 'content' | 'complete' | 'error' | 'fact_check_result'
  stage?: string
  progress?: number
  text?: string
  resume_markdown?: string
  analysis?: string
  message?: string
  data?: Record<string, unknown>
}

// ===== 用户基本信息 =====
export interface UserProfile {
  id: string
  name: string
  email?: string
  phone?: string
  city?: string
  current_role?: string
  years_of_experience?: number
  education?: string
  school?: string
  major?: string
  summary?: string
  expected_role?: string
  expected_salary?: string
  job_status?: string
  created_at?: string
  updated_at?: string
}

export interface UserProfileUpdate {
  name?: string
  email?: string
  phone?: string
  city?: string
  current_role?: string
  years_of_experience?: number
  education?: string
  school?: string
  major?: string
  summary?: string
  expected_role?: string
  expected_salary?: string
  job_status?: string
}

export const EDUCATION_OPTIONS = ['高中', '大专', '本科', '硕士', '博士'] as const
export const JOB_STATUS_OPTIONS = ['在职看机会', '已离职', '应届生'] as const

// ===== 技能库 =====
export interface SkillLibraryEntry {
  id: string
  entry_type: 'skill' | 'project' | 'internship' | 'certificate' | 'other'
  title: string
  content: string
  tags?: string
  start_date?: string
  end_date?: string
  importance: number
  is_active: boolean
  created_at?: string
  updated_at?: string
}

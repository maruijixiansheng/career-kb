import { useState, useEffect, useCallback } from 'react'
import type { Resume, JobDescription, JDTechStack, GapAnalysisResult } from '../types'
import { listResumes, listJDs, getJDTechStack, runGapAnalysis } from '../services/api'
import TechStackChart from '../components/skills/TechStackChart'
import GapRadarChart from '../components/skills/GapRadarChart'
import LearningPath from '../components/skills/LearningPath'

export default function SkillsPage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [jds, setJDs] = useState<JobDescription[]>([])
  const [selectedJD, setSelectedJD] = useState('')
  const [selectedResume, setSelectedResume] = useState('')
  const [loading, setLoading] = useState(false)
  const [techStack, setTechStack] = useState<JDTechStack | null>(null)
  const [gapResult, setGapResult] = useState<GapAnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'details' | 'path'>('overview')

  useEffect(() => {
    Promise.all([listResumes(), listJDs()]).then(([r, j]) => {
      setResumes(r); setJDs(j)
    })
  }, [])

  const handleJDChange = useCallback(async (jdId: string) => {
    setSelectedJD(jdId); setTechStack(null); setGapResult(null)
    if (!jdId) return
    try {
      const ts = await getJDTechStack(jdId)
      setTechStack(ts)
    } catch { /* ignore */ }
  }, [])

  const handleAnalyze = async () => {
    if (!selectedJD || !selectedResume) return
    setLoading(true); setError(null)
    try {
      const result = await runGapAnalysis(selectedJD, selectedResume)
      setGapResult(result.gap_analysis)
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析失败')
    }
    setLoading(false)
  }

  const ScoreRing = ({ score }: { score: number }) => {
    const color = score >= 80 ? '#10B981' : score >= 60 ? '#F59E0B' : '#EF4444'
    return (
      <div className="flex flex-col items-center">
        <svg width="80" height="80">
          <circle cx="40" cy="40" r="32" fill="none" stroke="#e5e7eb" strokeWidth="8" />
          <circle cx="40" cy="40" r="32" fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={`${score * 2.01} 201`} strokeLinecap="round" transform="rotate(-90 40 40)" />
          <text x="40" y="44" textAnchor="middle" className="text-lg font-bold" fill={color}>{score}</text>
        </svg>
        <span className="text-xs text-gray-500 mt-1">综合匹配度</span>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <h1 className="text-xl font-bold text-gray-800 mb-4">技能 Gap 分析</h1>

      {/* Controls */}
      <div className="flex gap-3 items-end mb-4 bg-white rounded-lg p-4 shadow-sm">
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">选择 JD</label>
          <select value={selectedJD} onChange={e => handleJDChange(e.target.value)}
            className="w-full border rounded px-3 py-1.5 text-sm">
            <option value="">-- 选择 JD --</option>
            {jds.map(jd => <option key={jd.id} value={jd.id}>{jd.title} - {jd.company}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">选择简历</label>
          <select value={selectedResume} onChange={e => setSelectedResume(e.target.value)}
            className="w-full border rounded px-3 py-1.5 text-sm">
            <option value="">-- 选择简历 --</option>
            {resumes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </div>
        <button onClick={handleAnalyze} disabled={loading || !selectedJD || !selectedResume}
          className="px-6 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 disabled:opacity-50">
          {loading ? '分析中...' : '🔍 开始分析'}
        </button>
      </div>

      {error && <div className="bg-red-50 text-red-600 rounded-lg p-3 mb-4 text-sm">{error}</div>}

      {/* Results */}
      {gapResult && (
        <div className="flex-1 overflow-y-auto space-y-4">
          {/* Score + Radar */}
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-1 flex justify-center items-center">
              <ScoreRing score={gapResult.weighted_score} />
            </div>
            <div className="col-span-2">
              <GapRadarChart dimensions={gapResult.radar_data?.dimensions || []} />
            </div>
          </div>

          {/* Score Breakdown */}
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="bg-green-50 rounded p-2">
              <span className="text-green-600 font-bold text-lg">{gapResult.score_breakdown.matched_weight}%</span>
              <p className="text-green-500">已匹配</p>
            </div>
            <div className="bg-yellow-50 rounded p-2">
              <span className="text-yellow-600 font-bold text-lg">{gapResult.score_breakdown.partial_weight}%</span>
              <p className="text-yellow-500">部分匹配</p>
            </div>
            <div className="bg-red-50 rounded p-2">
              <span className="text-red-600 font-bold text-lg">{gapResult.score_breakdown.missing_weight}%</span>
              <p className="text-red-500">完全缺失</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b">
            {(['overview', 'details', 'path'] as const).map(tab => {
              const label = { overview: '概览', details: '技能详情', path: '学习路径' }[tab]
              const isActive = activeTab === tab
              return (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={'px-3 py-1.5 text-sm border-b-2 transition-colors ' + (isActive ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-400')}
                >{label}</button>
              )
            })}
          </div>

          {activeTab === 'overview' && techStack && (
            <TechStackChart skills={techStack.tech_stack} totalWeight={techStack.total_weight} />
          )}

          {activeTab === 'details' && (
            <div className="space-y-4">
              {gapResult.matched_skills.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-green-700 mb-2">✅ 已匹配 ({gapResult.matched_skills.length})</h4>
                  {gapResult.matched_skills.map(s => (
                    <div key={s.skill} className="flex justify-between text-xs py-1 border-b">
                      <span>{s.skill} <span className="text-gray-400">权重 {s.jd_weight}%</span></span>
                      <span className="text-green-600">{s.my_level} (+{s.score_contribution}分)</span>
                    </div>
                  ))}
                </div>
              )}
              {gapResult.partial_skills.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-yellow-700 mb-2">⚠️ 部分匹配 ({gapResult.partial_skills.length})</h4>
                  {gapResult.partial_skills.map(s => (
                    <div key={s.skill} className="text-xs py-2 border-b">
                      <div className="flex justify-between">
                        <span>{s.skill} <span className="text-gray-400">权重 {s.jd_weight}%</span></span>
                        <span>{s.my_level} → {s.required_level}</span>
                      </div>
                      <p className="text-gray-500 mt-0.5">{s.gap_description} · 预计 {s.effort_weeks} 周</p>
                    </div>
                  ))}
                </div>
              )}
              {gapResult.missing_skills.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-red-700 mb-2">❌ 缺失 ({gapResult.missing_skills.length})</h4>
                  {gapResult.missing_skills.map(s => (
                    <div key={s.skill} className="flex justify-between text-xs py-1.5 border-b">
                      <div>
                        <span>{s.skill}</span>
                        <span className={`ml-2 px-1 py-0.5 rounded text-xs ${
                          s.importance === 'high' ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-500'
                        }`}>{s.importance}</span>
                      </div>
                      <span className="text-gray-400">权重 {s.jd_weight}% · {s.effort_weeks}周</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'path' && <LearningPath result={gapResult} />}
        </div>
      )}

      {!gapResult && !loading && (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          {techStack ? '请选择简历并点击"开始分析"' : '请先选择一个 JD 查看技术栈分布'}
        </div>
      )}
    </div>
  )
}

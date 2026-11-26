export type SymptomCategory =
  | 'Headache / Neurological'
  | 'Fever'
  | 'Respiratory'
  | 'Digestive'
  | 'Musculoskeletal'
  | 'Skin'
  | 'Cardiovascular'
  | 'General / Other'

export type SymptomHistoryFilters = {
  category?: SymptomCategory | 'uncategorized'
  min_severity?: number
  max_severity?: number
  date_from?: string
  date_to?: string
}

export type SymptomCreate = {
  patient_id: string
  symptom_description: string
  severity: number
  category?: SymptomCategory
  notes?: string | null
  possible_triggers?: string | null
  timestamp?: string
}

export type SymptomRecord = {
  id: number
  patient_id: string
  symptom_description: string
  severity: number
  category: SymptomCategory | null
  notes: string | null
  possible_triggers: string | null
  timestamp: string
}

export type SymptomUpdate = Partial<Omit<SymptomCreate, 'patient_id' | 'category'>> & {
  category?: SymptomCategory | null
}

export type MoodSleepRecord = {
  id: number
  patient_id: string
  record_date: string
  mood_rating: number
  mood_label: string | null
  mood_notes: string | null
  sleep_duration_hours: number
  sleep_quality: number
  sleep_notes: string | null
  created_at: string
  updated_at: string
}

export type MoodSleepCreate = Omit<MoodSleepRecord, 'id' | 'created_at' | 'updated_at'>
export type MoodSleepUpdate = Partial<Omit<MoodSleepCreate, 'patient_id'>>

export type DailySeverityPoint = {
  date: string
  average_severity: number
  entry_count: number
}

export type PatientAnalytics = {
  patient_id: string
  window_days: number
  total_entries: number
  average_severity: number | null
  highest_severity: number | null
  daily_trend: DailySeverityPoint[]
}

export type AdvancedAnalytics = {
  patient_id: string
  date_from: string
  date_to: string
  interval: 'daily' | 'weekly' | 'monthly'
  total_entries: number
  average_severity: number | null
  maximum_severity: number | null
  trend: { period_start: string; average_severity: number; maximum_severity: number; entry_count: number }[]
  category_frequency: { category: string; entry_count: number; average_severity: number }[]
  category_severity: { category: string; entry_count: number; average_severity: number }[]
  recurring_patterns: { pattern_type: string; label: string; occurrence_count: number; distinct_dates: string[] }[]
  severity_by_mood_rating: { group: string; average_severity: number; matching_symptom_entries: number }[]
  severity_by_sleep_duration: { group: string; average_severity: number; matching_symptom_entries: number }[]
}

export type AISummary = {
  patient_id: string
  entry_count: number
  model: string
  summary: string
  disclaimer: string
}

export type RAGSource = { title: string; url: string }
export type RAGAnswer = { question: string; answer: string; sources: RAGSource[] }
export type HealthFinding = {
  code: string
  finding_type: string
  summary: string
  supporting_metrics: Record<string, number | string>
  evidence_references: string[]
  sample_size?: number
}
export type SymptomAnalysisResult = {
  agent_status: string
  key_findings: HealthFinding[]
  warnings: string[]
  limitations: string[]
  concise_explanation: string
}
export type LifestyleAnalysisResult = {
  agent_status: string
  key_findings: HealthFinding[]
  missing_mood_dates: string[]
  missing_sleep_dates: string[]
  warnings: string[]
  limitations: string[]
  concise_explanation: string
}
export type MedicalKnowledgeResult = {
  agent_status: 'complete' | 'no_relevant_information' | 'unavailable'
  question: string
  answer: string
  sources: RAGSource[]
  warnings: string[]
  limitations: string[]
}
export type HealthIntelligenceReport = {
  executive_summary: string
  patient_recorded_facts: string[]
  deterministic_observations: string[]
  symptom_analysis: SymptomAnalysisResult | null
  lifestyle_analysis: LifestyleAnalysisResult | null
  medical_knowledge_context: MedicalKnowledgeResult | null
  general_educational_information: string | null
  educational_sources: RAGSource[]
  ai_generated_explanations: string[]
  ai_explanation_status: 'generated' | 'skipped_no_records' | 'unavailable'
  warnings: string[]
  limitations: string[]
  disclaimer: string
  prototype_notice: string
}
export type HealthIntelligenceResponse = {
  request_id: string
  patient_id: string
  date_from: string
  date_to: string
  symptom_analysis: SymptomAnalysisResult
  lifestyle_analysis: LifestyleAnalysisResult
  medical_knowledge: MedicalKnowledgeResult | null
  report: HealthIntelligenceReport
  warnings: string[]
}
export type ApiRoot = { message: string }
export type HealthResponse = { status: string }

type FastApiValidationDetail = Array<{ loc?: Array<string | number>; msg?: string }>

export class ApiError extends Error {
  readonly status: number | null
  readonly detail: unknown

  constructor(message: string, status: number | null = null, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const DEFAULT_TIMEOUT_MS = 10_000
const AI_TIMEOUT_MS = 45_000
const HEALTH_INTELLIGENCE_TIMEOUT_MS = 90_000

function formatValidationDetail(detail: FastApiValidationDetail): string {
  return detail.map((item) => {
    const location = (item.loc ?? []).filter((part) => part !== 'body').join('.')
    const message = item.msg ?? 'Invalid value'
    return location ? `${location}: ${message}` : message
  }).join('; ')
}

async function requestJson<T>(
  path: string,
  options: { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown; signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  const abortFromCaller = () => controller.abort()
  options.signal?.addEventListener('abort', abortFromCaller, { once: true })

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? 'GET',
      headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    })

    let payload: unknown
    try {
      payload = await response.json()
    } catch {
      payload = undefined
    }

    if (!response.ok) {
      const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
        ? (payload as { detail: unknown }).detail
        : undefined
      const message = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? formatValidationDetail(detail as FastApiValidationDetail)
          : `The API returned ${response.status} ${response.statusText || 'error'}.`
      throw new ApiError(message, response.status, detail)
    }

    if (response.status === 204) return undefined as T
    if (payload === undefined) {
      throw new ApiError('The API returned an empty or invalid JSON response.', response.status)
    }

    return payload as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (options.signal?.aborted) throw error
      throw new ApiError('The request timed out. Check the backend and try again.')
    }
    throw new ApiError('Could not reach the HealthTrack API. Check that FastAPI is running on port 8000.')
  } finally {
    window.clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abortFromCaller)
  }
}

function patientPath(patientId: string, resource: string): string {
  const cleaned = patientId.trim()
  if (!cleaned) throw new ApiError('Enter a patient ID first.')
  if (cleaned.includes('/')) throw new ApiError('Patient IDs cannot contain a slash because they are used in API paths.')
  return `/${resource}/${encodeURIComponent(cleaned)}`
}

export const api = {
  getRoot: (signal?: AbortSignal) => requestJson<ApiRoot>(API_BASE_URL ? '/' : '/api-root', { signal }),
  getHealth: (signal?: AbortSignal) => requestJson<HealthResponse>('/health', { signal }),
  getSymptoms: (patientId: string, signal?: AbortSignal, filters?: SymptomHistoryFilters) => {
    const query = new URLSearchParams()
    Object.entries(filters ?? {}).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, String(value))
    })
    const queryString = query.toString()
    return requestJson<SymptomRecord[]>(`${patientPath(patientId, 'symptoms')}${queryString ? `?${queryString}` : ''}`, { signal })
  },
  createSymptom: (payload: SymptomCreate) => requestJson<SymptomRecord>('/symptoms', { method: 'POST', body: payload }),
  updateSymptom: (patientId: string, recordId: number, body: SymptomUpdate) => requestJson<SymptomRecord>(`${patientPath(patientId, 'symptoms')}/${recordId}`, { method: 'PATCH', body }),
  deleteSymptom: (patientId: string, recordId: number) => requestJson<void>(`${patientPath(patientId, 'symptoms')}/${recordId}`, { method: 'DELETE' }),
  getMoodSleepHistory: (patientId: string, signal?: AbortSignal) => requestJson<MoodSleepRecord[]>(patientPath(patientId, 'mood-sleep'), { signal }),
  createMoodSleepRecord: (payload: MoodSleepCreate) => requestJson<MoodSleepRecord>('/mood-sleep', { method: 'POST', body: payload }),
  updateMoodSleepRecord: (patientId: string, recordId: number, body: MoodSleepUpdate) => requestJson<MoodSleepRecord>(`${patientPath(patientId, 'mood-sleep')}/${recordId}`, { method: 'PATCH', body }),
  deleteMoodSleepRecord: (patientId: string, recordId: number) => requestJson<void>(`${patientPath(patientId, 'mood-sleep')}/${recordId}`, { method: 'DELETE' }),
  getAnalytics: (patientId: string, signal?: AbortSignal) => requestJson<PatientAnalytics>(patientPath(patientId, 'analytics'), { signal }),
  getAdvancedAnalytics: (patientId: string, query: { date_from: string; date_to: string; interval: 'daily' | 'weekly' | 'monthly' }, signal?: AbortSignal) => {
    const params = new URLSearchParams(query)
    return requestJson<AdvancedAnalytics>(`${patientPath(patientId, 'analytics')}/advanced?${params}`, { signal })
  },
  generateSummary: (patientId: string) => requestJson<AISummary>(patientPath(patientId, 'ai/summary'), { method: 'POST', timeoutMs: AI_TIMEOUT_MS }),
  generateHealthIntelligence: (patientId: string, body: { date_from: string; date_to: string; educational_question?: string }) => requestJson<HealthIntelligenceResponse>(patientPath(patientId, 'ai/health-intelligence'), { method: 'POST', body, timeoutMs: HEALTH_INTELLIGENCE_TIMEOUT_MS }),
  askHealthQuestion: (question: string) => requestJson<RAGAnswer>('/rag/ask', { method: 'POST', body: { question }, timeoutMs: AI_TIMEOUT_MS }),
}

export const apiBaseUrl = API_BASE_URL || 'Vite proxy → http://127.0.0.1:8000'

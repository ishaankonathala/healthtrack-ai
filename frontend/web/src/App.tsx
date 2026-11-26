import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, ArrowDownRight, ArrowRight, AudioLines, BrainCircuit, Check,
  CircleHelp, Clock3, Command, ChevronDown, HeartPulse, LayoutDashboard,
  Menu, MessageCircleQuestion, Moon, ScanLine, Search, ShieldCheck, Sparkles,
  Stethoscope, X, type LucideIcon,
} from 'lucide-react'
import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, type AdvancedAnalytics, type HealthFinding, type HealthIntelligenceResponse, type MoodSleepRecord, type SymptomCategory, type SymptomHistoryFilters, type SymptomRecord } from './api/client'
import { useApiResource } from './api/useApiResource'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const AdvancedAnalyticsCharts = lazy(() => import('./components/AdvancedAnalyticsCharts'))
const AnatomyViewer = lazy(() => import('./components/AnatomyViewer'))

type PageId = 'overview' | 'tracking' | 'mood-sleep' | 'analytics' | 'summary' | 'education'
type NavItem = { id: PageId; label: string; icon: LucideIcon; index: string }

const navigation: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, index: '01' },
  { id: 'tracking', label: 'Symptom tracking', icon: Activity, index: '02' },
  { id: 'mood-sleep', label: 'Mood & sleep', icon: Moon, index: '03' },
  { id: 'analytics', label: 'Analytics', icon: AudioLines, index: '04' },
  { id: 'summary', label: 'AI summary', icon: BrainCircuit, index: '05' },
  { id: 'education', label: 'Health education', icon: MessageCircleQuestion, index: '06' },
]

const pageInfo: Record<PageId, { title: string; subtitle: string }> = {
  overview: { title: 'Overview', subtitle: 'A clearer view of your health story.' },
  tracking: { title: 'Symptom tracking', subtitle: 'Capture how you feel, with context that matters.' },
  'mood-sleep': { title: 'Mood & sleep', subtitle: 'Keep a simple daily record of how you feel and rest.' },
  analytics: { title: 'Analytics', subtitle: 'See patterns across your recent symptom history.' },
  summary: { title: 'AI summary', subtitle: 'Prepare a structured record for a clinician visit.' },
  education: { title: 'Health education', subtitle: 'Explore general health information from trusted sources.' },
}

const systems = [
  { id: 'muscular', label: 'Muscular' },
  { id: 'skeletal', label: 'Skeletal' },
  { id: 'cardiovascular', label: 'Cardiovascular' },
  { id: 'respiratory', label: 'Respiratory' },
  { id: 'nervous', label: 'Nervous' },
  { id: 'digestive', label: 'Digestive' },
  { id: 'urinary', label: 'Urinary' },
  { id: 'integumentary', label: 'Skin' },
  { id: 'other', label: 'Other' },
]

const symptomCategories: SymptomCategory[] = [
  'Headache / Neurological', 'Fever', 'Respiratory', 'Digestive',
  'Musculoskeletal', 'Skin', 'Cardiovascular', 'General / Other',
]

function Button({
  children, onClick, variant = 'primary', disabled = false, className = '',
}: {
  children: React.ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'quiet'
  disabled?: boolean
  className?: string
}) {
  return <button className={`button button-${variant} ${className}`} onClick={onClick} disabled={disabled}>{children}</button>
}

function BrandMark({ small = false }: { small?: boolean }) {
  return <div className={`brand-mark ${small ? 'brand-mark-small' : ''}`} aria-hidden="true"><HeartPulse size={small ? 17 : 20} strokeWidth={1.8} /></div>
}

function Sidebar({
  activePage, onNavigate, mobileOpen, onClose,
}: {
  activePage: PageId
  onNavigate: (page: PageId) => void
  mobileOpen: boolean
  onClose: () => void
}) {
  return <>
    {mobileOpen && <button className="mobile-scrim" onClick={onClose} aria-label="Close navigation" />}
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-topline">
        <div className="brand-lockup"><BrandMark /><div><div className="brand-name">HealthTrack<span>AI</span></div><div className="brand-caption">PERSONAL HEALTH JOURNAL</div></div></div>
        <button className="mobile-close" onClick={onClose} aria-label="Close navigation"><X size={19} /></button>
      </div>
      <div className="sidebar-label"><span>WORKSPACE</span><span className="label-line" /></div>
      <nav className="primary-nav" aria-label="Main navigation">
        {navigation.map(({ id, label, icon: Icon, index }) => <button key={id} className={`nav-item ${activePage === id ? 'nav-item-active' : ''}`} onClick={() => { onNavigate(id); onClose() }} aria-current={activePage === id ? 'page' : undefined}>
          <span className="nav-icon"><Icon size={17} strokeWidth={1.8} /></span><span className="nav-label">{label}</span><span className="nav-index">{index}</span>
        </button>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-lab-card"><div className="lab-card-orbit orbit-one" /><div className="lab-card-orbit orbit-two" />
          <div className="lab-card-head"><span className="live-dot" /> ATLAS MODULE</div><div className="lab-card-title">Anatomy, in focus.</div>
          <div className="lab-card-copy">An interactive reference atlas is ready to connect.</div>
          <button className="lab-card-link" onClick={() => onNavigate('overview')}>Open atlas <ArrowRight size={14} /></button>
        </div>
        <div className="sidebar-footer"><div className="footer-emblem"><ShieldCheck size={15} /></div><div><div className="footer-title">Prototype workspace</div><div className="footer-note">Use synthetic data only</div></div></div>
      </div>
    </aside>
  </>
}

function Topbar({
  page, onMenu, patientId, onApplyPatient, connection,
}: {
  page: PageId
  onMenu: () => void
  patientId: string
  onApplyPatient: (patientId: string) => void
  connection: 'loading' | 'connected' | 'offline'
}) {
  const [draftPatientId, setDraftPatientId] = useState(patientId)
  useEffect(() => setDraftPatientId(patientId), [patientId])
  const apply = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onApplyPatient(draftPatientId.trim())
  }
  return <header className="topbar">
    <div className="topbar-left"><button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu size={20} /></button><div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{pageInfo[page].title}</strong></div></div>
    <div className="topbar-right">
      <form className="patient-selector" onSubmit={apply}>
        <label htmlFor="patient-context">PATIENT ID</label>
        <input id="patient-context" value={draftPatientId} maxLength={100} onChange={(event) => setDraftPatientId(event.target.value)} placeholder="Enter patient ID" />
        <button type="submit" disabled={!draftPatientId.trim() || draftPatientId.trim() === patientId}>Load</button>
        <button type="button" className="example-patient" title="README example ID; records may be empty" onClick={() => { setDraftPatientId('patient-001'); onApplyPatient('patient-001') }}>Use README example</button>
        {patientId && <button type="button" className="clear-patient" onClick={() => { setDraftPatientId(''); onApplyPatient('') }}>Clear</button>}
      </form>
      <div className={`connection-state connection-${connection}`}><span className="connection-dot" /><span>{connection === 'connected' ? 'API connected' : connection === 'offline' ? 'API unavailable' : 'Checking API'}</span></div>
      <span className="topbar-divider" /><button className="icon-button help-button" aria-label="About HealthTrack AI"><CircleHelp size={18} /></button><div className="preview-chip"><span className="preview-chip-dot" /> PREVIEW</div>
    </div>
  </header>
}

function PageHeading({ page, patientId, eyebrow }: { page: PageId; patientId?: string; eyebrow?: string }) {
  const sideNote = page === 'education' ? 'Curated resources' : patientId ? `Patient · ${patientId}` : 'No patient selected'
  return <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-mark" />{eyebrow ?? 'HEALTHTRACK / YOUR WORKSPACE'}</div><h1>{pageInfo[page].title}<span className="heading-period">.</span></h1><p>{pageInfo[page].subtitle}</p></div><div className="heading-side-note"><span className="heading-note-icon"><Clock3 size={15} /></span><span>{sideNote}</span></div></div>
}

function Panel({ children, className = '', glow = false }: { children: React.ReactNode; className?: string; glow?: boolean }) {
  return <section className={`panel ${glow ? 'panel-glow' : ''} ${className}`}>{children}</section>
}

function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return <div className="empty-state"><div className="empty-orbit"><span className="empty-orbit-core"><Icon size={22} strokeWidth={1.5} /></span></div><h3>{title}</h3><p>{description}</p></div>
}

function usePatientData(patientId: string) {
  const selectedId = patientId.trim()
  const historyLoad = useCallback((signal: AbortSignal) => api.getSymptoms(selectedId, signal), [selectedId])
  const analyticsLoad = useCallback((signal: AbortSignal) => api.getAnalytics(selectedId, signal), [selectedId])
  const history = useApiResource(selectedId ? `symptoms:${selectedId}` : null, historyLoad)
  const analytics = useApiResource(selectedId ? `analytics:${selectedId}` : null, analyticsLoad)
  return { history, analytics }
}

function LoadingState({ label }: { label: string }) {
  return <div className="request-state request-loading" role="status"><span className="loading-spinner" /><span>{label}</span></div>
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="request-state request-error" role="alert"><span>{message}</span><button onClick={onRetry}>Try again <ArrowRight size={13} /></button></div>
}

function errorMessage(error: unknown, context: 'summary' | 'rag' | 'general' = 'general') {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
  if (error.status === 409) return 'A daily mood and sleep record already exists for this date. Choose Edit on that record to update it.'
  if (context === 'summary' && error.status === 404) return 'There are no recorded symptoms for this patient to summarize yet.'
  if (context === 'summary' && error.status === 503) return 'Gemini is unavailable. Check that the backend has a valid GEMINI_API_KEY.'
  if (context === 'summary' && error.status === 502) return 'Gemini could not generate the summary. Please try again later.'
  if (context === 'rag' && error.status === 429) return 'The health education service has reached its request limit. Please try again later.'
  if (context === 'rag' && error.status === 503) return 'The health education service is not configured. Check the backend Gemini configuration.'
  if (context === 'rag' && error.status === 504) return 'The health education request timed out. Please try again.'
  if (context === 'rag' && error.status === 502) return 'The health education provider could not answer. Please try again later.'
  return error.message
}
function cleanGeneratedMarkdown(value: string): string {
  return value
    .replace(/\\(?=#{1,6}\s)/g, '')
    .replace(/\\(?=\*\*)/g, '')
    .replace(/\\(?=\*)/g, '')
    .replace(/^\\(?=-\s)/gm, '')
}
function formatTimestamp(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(date)} UTC`
}

function defaultReportWindow() {
  const end = new Date()
  end.setUTCHours(0, 0, 0, 0)
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - 29)
  return { from: start.toISOString().slice(0, 10), to: end.toISOString().slice(0, 10) }
}

function chronological(records: SymptomRecord[]) {
  return [...records].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp) || a.id - b.id)
}

function StatCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="patient-stat"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
}

function AnatomyAtlas() {
  const [activeSystem, setActiveSystem] = useState('muscular')
  return <Panel className="anatomy-panel" glow>
    <div className="anatomy-panel-header"><div className="anatomy-heading-lockup"><div className="anatomy-icon"><ScanLine size={17} /></div><div><div className="panel-kicker">REFERENCE ATLAS <span className="kicker-dot" /></div><h2>Human anatomy</h2></div></div><div className="atlas-ready"><span className="atlas-ready-icon"><Check size={12} /></span> ORIGINAL GLB SYSTEMS</div></div>
    <div className="anatomy-stage">
      <div className="stage-grid" /><div className="stage-rings"><span /><span /><span /></div><div className="stage-axis axis-x" /><div className="stage-axis axis-y" />
      <div className="stage-coordinates coordinate-top">ATLAS / 01</div><div className="stage-coordinates coordinate-bottom">Y+ <span>·</span> Z+ <span>·</span> REFERENCE VIEW</div>
      <Suspense fallback={<div className="viewer-loading-overlay" role="status"><span className="viewer-spinner" /><strong>Preparing the 3D viewer</strong><span>Loading the anatomy renderer…</span></div>}><AnatomyViewer selectedSystem={activeSystem} /></Suspense>
      <div className="anatomy-stage-footer"><span><span className="live-dot" /> 3D VIEWPORT</span><span>Drag to rotate <i /> Scroll to zoom</span></div>
    </div>
    <div className="system-selector"><div className="selector-label">SHOW SYSTEM</div><div className="system-pills">{systems.map(({ id, label }) => <button key={id} data-system={id} onClick={() => setActiveSystem(id)} className={`system-pill ${activeSystem === id ? 'system-pill-active' : ''}`} aria-pressed={activeSystem === id}>{activeSystem === id && <span className="system-pill-dot" />}{label}</button>)}</div></div>
    <div className="atlas-attribution">Atlas models: <a href="https://github.com/Z-Anatomy/Models-of-human-anatomy" target="_blank" rel="noreferrer">Z-Anatomy</a> / BodyParts3D<span className="attribution-separator">·</span><a href="/anatomy/LICENSE.md" target="_blank" rel="noreferrer">CC BY-SA 4.0 license</a></div>
  </Panel>
}

function OverviewPage({ onNavigate, patientId }: { onNavigate: (page: PageId) => void; patientId: string }) {
  const { history, analytics } = usePatientData(patientId)
  const historyRecords = history.status === 'success' ? history.data : []
  const analyticsData = analytics.status === 'success' ? analytics.data : null
  const latest = historyRecords.length > 0 ? chronological(historyRecords).at(-1) : undefined
  return <>
    <PageHeading page="overview" patientId={patientId} />
    <div className="overview-grid">
      <AnatomyAtlas />
      <div className="overview-rail">
        <Panel className="workspace-panel"><div className="rail-title-row"><div><div className="panel-kicker">YOUR JOURNAL</div><h2>Patient overview</h2></div><div className="rail-title-icon"><HeartPulse size={17} /></div></div>
          {!patientId ? <div className="workspace-empty"><div className="workspace-empty-art"><div className="pulse-ring ring-a" /><div className="pulse-ring ring-b" /><HeartPulse size={22} /></div><h3>Select a patient ID.</h3><p>Use the patient control above to load records and analytics from the backend.</p></div>
            : history.status === 'loading' || analytics.status === 'loading' ? <LoadingState label="Loading patient records…" />
              : history.status === 'error' ? <ErrorState message={errorMessage(history.error)} onRetry={history.reload} />
                : analytics.status === 'error' ? <ErrorState message={errorMessage(analytics.error)} onRetry={analytics.reload} />
                  : historyRecords.length === 0 ? <div className="workspace-empty"><div className="workspace-empty-art"><div className="pulse-ring ring-a" /><div className="pulse-ring ring-b" /><HeartPulse size={22} /></div><h3>No records found.</h3><p>This patient ID has no symptom entries yet. Record the first one when ready.</p><Button variant="secondary" onClick={() => onNavigate('tracking')}>Go to symptom tracking <ArrowRight size={15} /></Button></div>
                    : <div className="patient-overview-content">{analyticsData && <div className="patient-stat-grid"><StatCard label="ENTRIES · 30 DAYS" value={String(analyticsData.total_entries)} detail="Recorded symptoms" /><StatCard label="AVG. SEVERITY" value={analyticsData.average_severity === null ? '—' : `${analyticsData.average_severity.toFixed(1)} / 10`} detail="Last 30 days" /><StatCard label="PEAK SEVERITY" value={analyticsData.highest_severity === null ? '—' : `${analyticsData.highest_severity} / 10`} detail="Last 30 days" /></div>}{latest && <div className="latest-entry"><div className="panel-kicker">LATEST ENTRY</div><p>{latest.symptom_description}</p><div><span className="latest-severity">Severity {latest.severity}/10</span><span>{formatTimestamp(latest.timestamp)}</span></div></div>}</div>}
          <div className="panel-footnote"><span className="footnote-icon"><ShieldCheck size={13} /></span> Only records returned by the API appear here.</div>
        </Panel>
        <Panel className="connection-card"><div className="connection-card-icon"><Activity size={17} /></div><div className="connection-card-copy"><div className="connection-card-title">FastAPI connection</div><div className="connection-card-subtitle">{history.status === 'success' ? 'Patient records loaded' : 'Live status shown above'}</div></div><span className={`connection-state-dot ${history.status === 'success' ? 'is-connected' : ''}`} /></Panel>
        <button className="safety-link" onClick={() => onNavigate('education')}><span><Stethoscope size={15} /></span><span>HealthTrack is an informational journal, not a diagnostic tool.</span><ArrowDownRight size={14} /></button>
      </div>
    </div>
    <div className="below-fold-heading"><div><div className="panel-kicker">YOUR RECENT ACTIVITY</div><h2>Symptom history</h2></div><span className="muted-note">{history.status === 'success' ? `${historyRecords.length} recorded entr${historyRecords.length === 1 ? 'y' : 'ies'}` : patientId ? 'Loading history' : 'Select a patient'}</span></div>
    <Panel className="timeline-empty">{!patientId ? <EmptyState icon={Clock3} title="Select a patient to view their timeline" description="History is loaded directly from the existing FastAPI symptom endpoint." />
      : history.status === 'loading' ? <LoadingState label="Loading chronological history…" />
        : history.status === 'error' ? <ErrorState message={errorMessage(history.error)} onRetry={history.reload} />
          : historyRecords.length === 0 ? <EmptyState icon={Clock3} title="No symptom entries yet" description="There are no records for this patient ID. New entries will appear here after they are saved." />
            : <div className="overview-timeline">{chronological(historyRecords).slice(-4).reverse().map((record) => <div className="overview-timeline-row" key={record.id}><span className="timeline-event-dot" /><div className="overview-timeline-date">{formatTimestamp(record.timestamp)}</div><div className="overview-timeline-description">{record.symptom_description}</div><span className="overview-timeline-severity">{record.severity}/10</span></div>)}<button className="timeline-action" onClick={() => onNavigate('tracking')}>View full history <ArrowRight size={14} /></button></div>}</Panel>
  </>
}

function TrackingPage({ patientId }: { patientId: string }) {
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [minSeverity, setMinSeverity] = useState('')
  const [maxSeverity, setMaxSeverity] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [appliedFilters, setAppliedFilters] = useState<SymptomHistoryFilters>({})
  const historyLoad = useCallback(
    (signal: AbortSignal) => api.getSymptoms(patientId, signal, appliedFilters),
    [patientId, appliedFilters],
  )
  const history = useApiResource(patientId ? `symptoms:${patientId}:${JSON.stringify(appliedFilters)}` : null, historyLoad)
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState(5)
  const [category, setCategory] = useState<SymptomCategory | ''>('General / Other')
  const [notes, setNotes] = useState('')
  const [possibleTriggers, setPossibleTriggers] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const submitLock = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [filterError, setFilterError] = useState<string | null>(null)

  const resetForm = () => {
    setDescription('')
    setSeverity(5)
    setCategory('General / Other')
    setNotes('')
    setPossibleTriggers('')
    setEditingId(null)
  }

  useEffect(() => {
    resetForm()
    setError(null)
    setSuccess(null)
    setAppliedFilters({})
    setCategoryFilter('all')
    setMinSeverity('')
    setMaxSeverity('')
    setDateFrom('')
    setDateTo('')
  }, [patientId])

  const applyFilters = () => {
    setFilterError(null)
    const minimum = minSeverity === '' ? undefined : Number(minSeverity)
    const maximum = maxSeverity === '' ? undefined : Number(maxSeverity)
    if ([minimum, maximum].some((value) => value !== undefined && (!Number.isInteger(value) || value < 1 || value > 10))) {
      setFilterError('Severity filters must be whole numbers from 1 to 10.')
      return
    }
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) {
      setFilterError('Minimum severity must be less than or equal to maximum severity.')
      return
    }
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setFilterError('Start date must be on or before end date.')
      return
    }
    setAppliedFilters({
      ...(categoryFilter !== 'all' ? { category: categoryFilter as SymptomCategory | 'uncategorized' } : {}),
      ...(minimum !== undefined ? { min_severity: minimum } : {}),
      ...(maximum !== undefined ? { max_severity: maximum } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    })
  }

  const clearFilters = () => {
    setCategoryFilter('all')
    setMinSeverity('')
    setMaxSeverity('')
    setDateFrom('')
    setDateTo('')
    setFilterError(null)
    setAppliedFilters({})
  }

  const beginEdit = (record: SymptomRecord) => {
    setEditingId(record.id)
    setDescription(record.symptom_description)
    setSeverity(record.severity)
    setCategory(record.category ?? '')
    setNotes(record.notes ?? '')
    setPossibleTriggers(record.possible_triggers ?? '')
    setError(null)
    setSuccess(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSuccess(null)
    const cleaned = description.trim()
    if (!patientId.trim()) { setError('Select a patient ID above before saving a symptom.'); return }
    if (!cleaned) { setError('Enter a symptom description.'); return }
    if (cleaned.length > 2000) { setError('Symptom descriptions must be 2,000 characters or fewer.'); return }
    if (submitLock.current) return

    submitLock.current = true
    setSubmitting(true)
    try {
      const body = {
        symptom_description: cleaned,
        severity,
        category: category || null,
        notes: notes.trim() || null,
        possible_triggers: possibleTriggers.trim() || null,
      }
      if (editingId !== null) {
        await api.updateSymptom(patientId.trim(), editingId, body)
        setSuccess('Symptom record updated.')
      } else {
        const created = await api.createSymptom({ patient_id: patientId.trim(), ...body, category: category || 'General / Other' })
        setSuccess(`Saved entry #${created.id} for ${created.patient_id}.`)
      }
      resetForm()
      history.reload()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      submitLock.current = false
      setSubmitting(false)
    }
  }

  const records = history.status === 'success' ? chronological(history.data) : []
  const removeRecord = async (record: SymptomRecord) => {
    if (deletingId !== null || !window.confirm(`Delete this symptom record from ${formatTimestamp(record.timestamp)}?`)) return
    setError(null)
    setSuccess(null)
    setDeletingId(record.id)
    try {
      await api.deleteSymptom(patientId, record.id)
      setSuccess('Symptom record deleted.')
      if (editingId === record.id) resetForm()
      history.reload()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setDeletingId(null)
    }
  }

  return <>
    <PageHeading page="tracking" patientId={patientId} />
    {error && <div className="form-feedback feedback-error symptom-feedback" role="alert">{error}</div>}
    {success && <div className="form-feedback feedback-success symptom-feedback" role="status"><Check size={14} />{success}</div>}
    <div className="symptom-workspace">
      <Panel className="feature-panel symptom-form-panel">
        <div className="feature-panel-top"><div><div className="panel-kicker">SYMPTOM JOURNAL</div><h2>{editingId === null ? 'Make space for how you feel.' : 'Edit symptom record.'}</h2><p>Record a symptom with a category and severity from 1 to 10.</p></div><div className="feature-symbol"><Activity size={22} /></div></div>
        <form className="form-preview symptom-form" onSubmit={submit}>
          <label className="field-label" htmlFor="symptom-category">CATEGORY</label>
          <select className="symptom-input" id="symptom-category" value={category} onChange={(event) => setCategory(event.target.value as SymptomCategory | '')}>{editingId !== null && <option value="">Legacy · uncategorized</option>}{symptomCategories.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <label className="field-label" htmlFor="symptom-note">SYMPTOM DESCRIPTION</label>
          <textarea id="symptom-note" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} placeholder="Describe the symptom…" required aria-describedby="symptom-count" />
          <div className="character-count" id="symptom-count">{description.length.toLocaleString()} / 2,000 characters</div>
          <div className="severity-control"><label htmlFor="severity-slider">SEVERITY <strong>{severity}<span> / 10</span></strong></label><input id="severity-slider" type="range" min="1" max="10" step="1" value={severity} onChange={(event) => setSeverity(Number(event.target.value))} /><div className="severity-scale"><span>Mild</span><span>Severe</span></div></div>
          <label className="field-label" htmlFor="symptom-notes">ADDITIONAL NOTES <span className="field-optional">OPTIONAL</span></label>
          <textarea className="symptom-optional-text" id="symptom-notes" value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} placeholder="Add context you want to remember…" />
          <label className="field-label" htmlFor="symptom-triggers">POSSIBLE TRIGGERS <span className="field-optional">OPTIONAL</span></label>
          <textarea className="symptom-optional-text" id="symptom-triggers" value={possibleTriggers} onChange={(event) => setPossibleTriggers(event.target.value)} maxLength={2000} placeholder="For example: stress, activity, food, or lack of sleep…" />
          <div className="trigger-disclaimer">Possible triggers are patient-reported observations, not medically verified causes.</div>
          {!patientId && <div className="form-disabled-note"><span className="pending-indicator"><span /></span> Choose a patient ID above to enable saving.</div>}
          <div className="form-controls"><div className="form-footnote">Entries use the backend’s UTC timestamp when saved.</div><div className="symptom-form-actions">{editingId !== null && <button type="button" className="button button-quiet" onClick={resetForm}>Cancel edit</button>}<Button disabled={!patientId || submitting}>{submitting ? <><span className="button-spinner" /> Saving…</> : <>{editingId === null ? 'Save symptom' : 'Update symptom'} <ArrowRight size={15} /></>}</Button></div></div>
        </form>
      </Panel>

      <Panel className="history-panel symptom-history-panel">
        <div className="rail-title-row"><div><div className="panel-kicker">CHRONOLOGICAL RECORD</div><h2>Symptom history</h2></div><div className="rail-title-icon"><Clock3 size={17} /></div></div>
        <div className="symptom-filters" aria-label="Symptom history filters">
          <label><span>CATEGORY</span><select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}><option value="all">All categories</option>{symptomCategories.map((item) => <option value={item} key={item}>{item}</option>)}<option value="uncategorized">Legacy · uncategorized</option></select></label>
          <label><span>MIN SEVERITY</span><input type="number" min="1" max="10" value={minSeverity} onChange={(event) => setMinSeverity(event.target.value)} placeholder="1" /></label>
          <label><span>MAX SEVERITY</span><input type="number" min="1" max="10" value={maxSeverity} onChange={(event) => setMaxSeverity(event.target.value)} placeholder="10" /></label>
          <label><span>FROM · UTC</span><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
          <label><span>TO · UTC</span><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
          <div className="symptom-filter-actions"><button type="button" className="button button-secondary" onClick={applyFilters}>Apply filters</button><button type="button" className="button button-quiet" onClick={clearFilters}>Clear</button></div>
        </div>
        {filterError && <div className="form-feedback feedback-error" role="alert">{filterError}</div>}
        {!patientId ? <EmptyState icon={Clock3} title="Choose a patient ID" description="Select a documented example or enter a patient ID to load its history." />
          : history.status === 'loading' ? <LoadingState label="Loading symptom history…" />
            : history.status === 'error' ? <ErrorState message={errorMessage(history.error)} onRetry={history.reload} />
              : records.length === 0 ? <EmptyState icon={Clock3} title={Object.keys(appliedFilters).length ? 'No records match these filters' : 'No entries found'} description={Object.keys(appliedFilters).length ? 'Try widening the category, severity, or date range.' : `There are no symptom records for ${patientId}. Your first saved note will appear here.`} />
                : <div className="symptom-record-list">{records.map((record) => <article className="symptom-record-card" key={record.id}>
                  <div className="symptom-record-top"><div><span className="symptom-record-date">{formatTimestamp(record.timestamp)}</span><span className="symptom-category-tag">{record.category ?? 'Legacy · uncategorized'}</span></div><div className="record-actions"><button type="button" onClick={() => beginEdit(record)} aria-label={`Edit symptom from ${formatTimestamp(record.timestamp)}`}>Edit</button><button type="button" className="record-delete" onClick={() => void removeRecord(record)} disabled={deletingId === record.id} aria-label={`Delete symptom from ${formatTimestamp(record.timestamp)}`}>{deletingId === record.id ? 'Deleting…' : 'Delete'}</button></div></div>
                  <div className="symptom-record-description">{record.symptom_description}</div><div className="symptom-record-severity">Severity <strong>{record.severity}<small>/10</small></strong></div>
                  {record.notes && <p className="symptom-record-note"><strong>Notes</strong>{record.notes}</p>}
                  {record.possible_triggers && <p className="symptom-record-note"><strong>Patient-reported possible triggers</strong>{record.possible_triggers}</p>}
                </article>)}</div>}
      </Panel>
    </div>
    <div className="privacy-strip"><ShieldCheck size={16} /><span>Use synthetic patient data in this prototype. Trigger notes are self-reported, not verified causes.</span><span className="strip-end">PATIENT-SCOPED RECORDS</span></div>
  </>
}

const moodScale = [
  { value: 1, label: 'Very low' },
  { value: 2, label: 'Low' },
  { value: 3, label: 'Neutral' },
  { value: 4, label: 'Good' },
  { value: 5, label: 'Very good' },
]
const sleepQualityScale = [
  { value: 1, label: 'Very poor' },
  { value: 2, label: 'Poor' },
  { value: 3, label: 'Fair' },
  { value: 4, label: 'Good' },
  { value: 5, label: 'Excellent' },
]

function MoodSleepPage({ patientId }: { patientId: string }) {
  const historyLoad = useCallback((signal: AbortSignal) => api.getMoodSleepHistory(patientId, signal), [patientId])
  const history = useApiResource(patientId ? `mood-sleep:${patientId}` : null, historyLoad)
  const [recordDate, setRecordDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [moodRating, setMoodRating] = useState(3)
  const [moodLabel, setMoodLabel] = useState('')
  const [moodNotes, setMoodNotes] = useState('')
  const [sleepDuration, setSleepDuration] = useState('8')
  const [sleepQuality, setSleepQuality] = useState(3)
  const [sleepNotes, setSleepNotes] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const submitLock = useRef(false)

  const clearForm = () => {
    setRecordDate(new Date().toISOString().slice(0, 10))
    setMoodRating(3)
    setMoodLabel('')
    setMoodNotes('')
    setSleepDuration('8')
    setSleepQuality(3)
    setSleepNotes('')
    setEditingId(null)
  }

  useEffect(() => {
    setRecordDate(new Date().toISOString().slice(0, 10))
    setMoodRating(3)
    setMoodLabel('')
    setMoodNotes('')
    setSleepDuration('8')
    setSleepQuality(3)
    setSleepNotes('')
    setEditingId(null)
    setError(null)
    setSuccess(null)
  }, [patientId])

  const beginEdit = (record: MoodSleepRecord) => {
    setError(null)
    setSuccess(null)
    setEditingId(record.id)
    setRecordDate(record.record_date)
    setMoodRating(record.mood_rating)
    setMoodLabel(record.mood_label ?? '')
    setMoodNotes(record.mood_notes ?? '')
    setSleepDuration(String(record.sleep_duration_hours))
    setSleepQuality(record.sleep_quality)
    setSleepNotes(record.sleep_notes ?? '')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const saveRecord = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setSuccess(null)
    if (!patientId.trim()) { setError('Select a patient ID above before saving a daily record.'); return }
    if (!recordDate) { setError('Choose the UTC date for this record.'); return }
    const duration = Number(sleepDuration)
    if (!Number.isFinite(duration) || duration < 0 || duration > 24) {
      setError('Sleep duration must be between 0 and 24 hours.')
      return
    }
    if (submitLock.current) return
    if (editingId === null && history.status === 'success' && history.data.some((record) => record.record_date === recordDate)) {
      setError('A daily record already exists for this date. Choose Edit on that record to update it.')
      return
    }

    submitLock.current = true
    setSubmitting(true)
    try {
      const body = {
        record_date: recordDate,
        mood_rating: moodRating,
        mood_label: moodLabel.trim() || null,
        mood_notes: moodNotes.trim() || null,
        sleep_duration_hours: duration,
        sleep_quality: sleepQuality,
        sleep_notes: sleepNotes.trim() || null,
      }
      if (editingId !== null) {
        await api.updateMoodSleepRecord(patientId, editingId, body)
        setSuccess(`Updated daily record for ${recordDate}.`)
      } else {
        await api.createMoodSleepRecord({ patient_id: patientId.trim(), ...body })
        setSuccess(`Saved mood and sleep for ${recordDate}.`)
      }
      clearForm()
      history.reload()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      submitLock.current = false
      setSubmitting(false)
    }
  }

  const removeRecord = async (record: MoodSleepRecord) => {
    if (deletingId !== null || !window.confirm(`Delete the mood and sleep record for ${record.record_date}?`)) return
    setError(null)
    setSuccess(null)
    setDeletingId(record.id)
    try {
      await api.deleteMoodSleepRecord(patientId, record.id)
      setSuccess(`Deleted daily record for ${record.record_date}.`)
      if (editingId === record.id) clearForm()
      history.reload()
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setDeletingId(null)
    }
  }

  const records = history.status === 'success' ? [...history.data].sort((a, b) => a.record_date.localeCompare(b.record_date) || a.id - b.id).reverse() : []
  return <>
    <PageHeading page="mood-sleep" patientId={patientId} />
    <div className="mood-sleep-intro"><div className="mood-sleep-intro-icon"><Moon size={18} /></div><div><strong>A daily check-in, all in one place.</strong><span>One combined mood and sleep record per patient for each UTC calendar day.</span></div><span className="mood-sleep-endpoint">PATIENT-SCOPED HISTORY</span></div>
    {error && <div className="form-feedback feedback-error mood-sleep-feedback" role="alert">{error}</div>}
    {success && <div className="form-feedback feedback-success mood-sleep-feedback" role="status"><Check size={14} />{success}</div>}
    <div className="mood-sleep-grid">
      <Panel className="mood-sleep-form-panel">
        <div className="mood-sleep-form-heading"><div><div className="panel-kicker">DAILY WELLNESS</div><h2>{editingId === null ? 'How are you today?' : 'Edit your check-in'}</h2><p>These are personal reflections, not a health assessment.</p></div><div className="mood-sleep-form-symbol"><HeartPulse size={19} /></div></div>
        <form className="mood-sleep-form" onSubmit={saveRecord}>
          <label className="field-label" htmlFor="mood-sleep-date">RECORD DATE · UTC</label>
          <input className="mood-sleep-input" id="mood-sleep-date" type="date" value={recordDate} onChange={(event) => setRecordDate(event.target.value)} required />

          <fieldset className="rating-fieldset"><legend className="field-label">HOW WOULD YOU RATE YOUR MOOD?</legend><div className="rating-selector">{moodScale.map((option) => <button key={option.value} type="button" className={`rating-choice ${moodRating === option.value ? 'rating-choice-active' : ''}`} aria-pressed={moodRating === option.value} aria-label={`Mood ${option.value}: ${option.label}`} onClick={() => setMoodRating(option.value)}><span className="rating-number">{option.value}</span><span>{option.label}</span></button>)}</div></fieldset>
          <label className="field-label" htmlFor="mood-label">MOOD LABEL <span className="field-optional">OPTIONAL</span></label>
          <input className="mood-sleep-input" id="mood-label" maxLength={50} value={moodLabel} onChange={(event) => setMoodLabel(event.target.value)} placeholder="Add a short label" />
          <label className="field-label" htmlFor="mood-notes">MOOD NOTES <span className="field-optional">OPTIONAL</span></label>
          <textarea className="mood-sleep-textarea" id="mood-notes" maxLength={2000} value={moodNotes} onChange={(event) => setMoodNotes(event.target.value)} placeholder="Anything you'd like to remember about today…" />

          <div className="sleep-section-heading"><div className="sleep-section-icon"><Moon size={15} /></div><div><div className="panel-kicker">SLEEP</div><strong>How did you rest?</strong></div></div>
          <div className="sleep-input-row"><label className="field-label" htmlFor="sleep-duration">DURATION · HOURS</label><div className="sleep-duration-control"><input className="mood-sleep-input" id="sleep-duration" type="number" min="0" max="24" step="0.25" value={sleepDuration} onChange={(event) => setSleepDuration(event.target.value)} required /><span>hours</span></div></div>
          <fieldset className="rating-fieldset"><legend className="field-label">SLEEP QUALITY</legend><div className="rating-selector">{sleepQualityScale.map((option) => <button key={option.value} type="button" className={`rating-choice ${sleepQuality === option.value ? 'rating-choice-active' : ''}`} aria-pressed={sleepQuality === option.value} aria-label={`Sleep quality ${option.value}: ${option.label}`} onClick={() => setSleepQuality(option.value)}><span className="rating-number">{option.value}</span><span>{option.label}</span></button>)}</div></fieldset>
          <label className="field-label" htmlFor="sleep-notes">SLEEP NOTES <span className="field-optional">OPTIONAL</span></label>
          <textarea className="mood-sleep-textarea" id="sleep-notes" maxLength={2000} value={sleepNotes} onChange={(event) => setSleepNotes(event.target.value)} placeholder="Optional details about your sleep…" />
          {!patientId && <div className="form-disabled-note"><span className="pending-indicator"><span /></span> Choose a patient ID above to enable saving.</div>}
          <div className="mood-sleep-form-actions"><span>Saved with UTC timestamps</span><div>{editingId !== null && <button type="button" className="button button-quiet" onClick={clearForm}>Cancel edit</button>}<Button disabled={!patientId || submitting}>{submitting ? <><span className="button-spinner" /> Saving…</> : <>{editingId === null ? 'Save daily check-in' : 'Update check-in'} <ArrowRight size={15} /></>}</Button></div></div>
        </form>
      </Panel>

      <Panel className="mood-sleep-history-panel">
        <div className="rail-title-row"><div><div className="panel-kicker">YOUR HISTORY</div><h2>Mood & sleep</h2></div><div className="rail-title-icon"><Clock3 size={17} /></div></div>
        {!patientId ? <EmptyState icon={Moon} title="Choose a patient ID" description="Select a documented example or enter a patient ID to load daily records." />
          : history.status === 'loading' ? <LoadingState label="Loading mood and sleep history…" />
            : history.status === 'error' ? <ErrorState message={errorMessage(history.error)} onRetry={history.reload} />
              : records.length === 0 ? <EmptyState icon={Moon} title="No daily check-ins yet" description="There are no mood and sleep records for this patient. Your first check-in will appear here." />
                : <div className="mood-sleep-record-list">{records.map((record) => <article className="mood-sleep-record" key={record.id}>
                  <div className="mood-sleep-record-top"><div><span className="record-date-label">{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(`${record.record_date}T00:00:00Z`))}</span><span className="record-mood-label">{record.mood_label || moodScale[record.mood_rating - 1].label}</span></div><div className="record-actions"><button type="button" onClick={() => beginEdit(record)} aria-label={`Edit record for ${record.record_date}`}>Edit</button><button type="button" className="record-delete" onClick={() => void removeRecord(record)} disabled={deletingId === record.id} aria-label={`Delete record for ${record.record_date}`}>{deletingId === record.id ? 'Deleting…' : 'Delete'}</button></div></div>
                  <div className="mood-sleep-record-stats"><div><span className="record-stat-label">MOOD</span><strong>{record.mood_rating}<small> / 5</small></strong></div><div><span className="record-stat-label">SLEEP</span><strong>{record.sleep_duration_hours}<small> hrs</small></strong></div><div><span className="record-stat-label">QUALITY</span><strong>{record.sleep_quality}<small> / 5</small></strong></div></div>
                  {(record.mood_notes || record.sleep_notes) && <div className="mood-sleep-record-notes">{record.mood_notes && <p><strong>Mood</strong>{record.mood_notes}</p>}{record.sleep_notes && <p><strong>Sleep</strong>{record.sleep_notes}</p>}</div>}
                </article>)}</div>}
        <div className="panel-footnote"><span className="footnote-icon"><ShieldCheck size={13} /></span> One entry per patient per UTC date. Your records are loaded from the API.</div>
      </Panel>
    </div>
    <div className="privacy-strip"><ShieldCheck size={16} /><span>Use synthetic patient data in this prototype. Never enter real patient information.</span><span className="strip-end">DAILY WELLNESS RECORD</span></div>
  </>
}

function AnalyticsPage({ patientId }: { patientId: string }) {
  const today = new Date().toISOString().slice(0, 10)
  const defaultStart = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10)
  const [dateFrom, setDateFrom] = useState(defaultStart)
  const [dateTo, setDateTo] = useState(today)
  const [interval, setInterval] = useState<'daily' | 'weekly' | 'monthly'>('daily')
  const [result, setResult] = useState<AdvancedAnalytics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => {
    if (!patientId || dateFrom > dateTo) return
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    api.getAdvancedAnalytics(patientId, { date_from: dateFrom, date_to: dateTo, interval }, controller.signal)
      .then((data) => setResult(data))
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(errorMessage(reason)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [patientId, dateFrom, dateTo, interval, reloadKey])

  return <><PageHeading page="analytics" patientId={patientId} /><div className="analytics-intro"><div><div className="panel-kicker">PATTERNS OVER TIME</div><h2>Understand the shape of your days.</h2><p>Deterministic summaries of recorded symptoms, mood and sleep. No causal claims.</p></div>
      <div className="advanced-filters"><label>FROM<input type="date" value={dateFrom} max={dateTo} onChange={(event) => setDateFrom(event.target.value)} /></label><label>TO<input type="date" value={dateTo} min={dateFrom} onChange={(event) => setDateTo(event.target.value)} /></label><label>BUCKET<select value={interval} onChange={(event) => setInterval(event.target.value as typeof interval)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label></div>
    </div>
    {!patientId ? <Panel className="analytics-no-patient"><EmptyState icon={Activity} title="Select a patient to load analytics" description="Choose the documented README example or enter an existing patient ID." /></Panel>
      : dateFrom > dateTo ? <Panel className="analytics-loading"><p className="advanced-empty">Choose a start date on or before the end date.</p></Panel>
        : loading ? <Panel className="analytics-loading"><LoadingState label="Calculating patient analytics…" /></Panel>
          : error ? <Panel className="analytics-loading"><ErrorState message={error} onRetry={() => setReloadKey((value) => value + 1)} /></Panel>
            : result ? <>
              <div className="analytics-metrics"><StatCard label="SYMPTOM ENTRIES" value={String(result.total_entries)} detail={`${result.date_from} to ${result.date_to}`} /><StatCard label="AVERAGE SEVERITY" value={result.average_severity === null ? '—' : `${result.average_severity.toFixed(2)} / 10`} detail="Across matching entries" /><StatCard label="MAXIMUM SEVERITY" value={result.maximum_severity === null ? '—' : `${result.maximum_severity} / 10`} detail="In selected date range" /></div>
              <Suspense fallback={<Panel className="analytics-loading"><LoadingState label="Preparing charts…" /></Panel>}><AdvancedAnalyticsCharts data={result} /></Suspense>
              <div className="panel recurring-panel"><div className="panel-kicker">REPEATED REPORTING</div><h2>Recurring symptom patterns</h2><p>Patterns require at least three distinct UTC dates. Repetition describes entries and does not establish a cause or diagnosis.</p>
                {result.recurring_patterns.length ? <div className="recurring-list">{result.recurring_patterns.map((pattern) => <article key={`${pattern.pattern_type}:${pattern.label}`}><div><strong>{pattern.label}</strong><span>{pattern.pattern_type === 'category' ? 'Category' : 'Description'}</span></div><b>{pattern.occurrence_count} entries</b><small>{pattern.distinct_dates.join(' · ')}</small></article>)}</div> : <div className="advanced-empty">No category or description met the three-distinct-date recurrence rule.</div>}
              </div>
              <div className="analytics-bottom-grid"><Panel className="analytics-note"><div className="note-orb"><Sparkles size={17} /></div><div><div className="panel-kicker">A NOTE ON YOUR DATA</div><h3>Patterns, not predictions.</h3><p>Comparison charts include only UTC dates with both symptom and mood or sleep data. They summarize co-occurrence and do not imply causation.</p></div></Panel><Panel className="analytics-empty-side"><div className="panel-kicker">ANALYSIS WINDOW</div><div className="window-detail"><span>Patient</span><strong>{result.patient_id}</strong></div><div className="window-detail"><span>Bucket interval</span><strong>{result.interval}</strong></div><div className="window-detail"><span>Dates with symptoms</span><strong>{result.trend.length}</strong></div></Panel></div>
            </> : null}
  </>
}

function ReportBulletList({ items, emptyText }: { items: string[]; emptyText: string }) {
  return items.length ? <ul className="health-report-list">{items.map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul> : <div className="health-report-empty">{emptyText}</div>
}

function reportMetric(findings: HealthFinding[], codes: string[], key: string): number | null {
  for (const code of codes) {
    const finding = findings.find((item) => item.code === code)
    const value = finding?.supporting_metrics[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
  }
  return null
}

function normalizeFindingText(value: string) {
  return value.toLocaleLowerCase().replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim()
}

function materiallySimilar(left: string, right: string) {
  const a = normalizeFindingText(left)
  const b = normalizeFindingText(right)
  if (!a || !b) return false
  if (a === b) return true
  const leftWords = new Set(a.split(' ').filter((word) => word.length > 2))
  const rightWords = new Set(b.split(' ').filter((word) => word.length > 2))
  if (leftWords.size < 6 || rightWords.size < 6) return false
  const overlap = [...leftWords].filter((word) => rightWords.has(word)).length
  return overlap / new Set([...leftWords, ...rightWords]).size >= 0.88
}

function formatLifestyleComparison(finding: HealthFinding): string | null {
  const metrics = finding.supporting_metrics
  if (finding.code === 'symptom_severity_by_sleep_quality') {
    const groups = new Set(Object.keys(metrics).map((key) => key.match(/^quality_(\d+)_average_symptom_severity$/)?.[1]).filter(Boolean))
    const sentences = [...groups].flatMap((quality) => {
      const average = metrics[`quality_${quality}_average_symptom_severity`]
      const count = metrics[`quality_${quality}_matched_dates`]
      return typeof average === 'number' && typeof count === 'number'
        ? [`For sleep-quality rating ${quality}, average symptom severity was ${average.toFixed(2)} across ${count} matching dates.`]
        : []
    })
    return sentences.length ? sentences.join(' ') : null
  }

  const groupIndexes = new Set(Object.keys(metrics).map((key) => key.match(/^group_(\d+)$/)?.[1]).filter(Boolean))
  const label = finding.code === 'symptom_severity_by_mood' ? 'mood rating' : 'sleep-duration group'
  const sentences = [...groupIndexes].flatMap((index) => {
    const group = metrics[`group_${index}`]
    const average = metrics[`group_${index}_average_severity`]
    const count = metrics[`group_${index}_matching_symptom_entries`]
    return group !== undefined && typeof average === 'number' && typeof count === 'number'
      ? [`For ${label} ${group}, average symptom severity was ${average.toFixed(2)} across ${count} matching entries.`]
      : []
  })
  return sentences.length ? sentences.join(' ') : null
}

function formatKeyObservation(finding: HealthFinding): string | null {
  if (finding.code === 'recurring_categories') {
    const categories = Object.keys(finding.supporting_metrics)
    return categories.length ? `Repeated symptom categories: ${categories.join(', ')}.` : null
  }
  if (finding.code === 'severity_increase') return 'Average symptom severity was higher later in the selected period than earlier.'
  if (finding.code === 'severity_decrease') return 'Average symptom severity was lower later in the selected period than earlier.'
  if (finding.code === 'severity_stable') return 'Average symptom severity did not show a meaningful change across the selected period.'
  if (finding.code === 'mood_change_comparison') {
    const earlier = finding.supporting_metrics.earlier_mean_rating
    const later = finding.supporting_metrics.later_mean_rating
    return typeof earlier === 'number' && typeof later === 'number'
      ? `Average recorded mood was ${earlier.toFixed(2)} / 5 earlier and ${later.toFixed(2)} / 5 later in the period.`
      : null
  }
  return null
}

function conciseQualityMessage(message: string) {
  if (/severity change was not assessed|not enough dates/i.test(message)) return 'Severity change is not summarized because too few symptom dates were recorded.'
  if (/mood change comparison requires|too few daily check-ins/i.test(message)) return 'Mood change is not summarized because too few check-ins were recorded.'
  if (/no same-date|matching .* unavailable/i.test(message)) return 'Mood and sleep comparisons need dates with both lifestyle and symptom records.'
  if (/requires at least/i.test(message)) return 'There are not enough matching records for this comparison.'
  return message
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    generated: 'Gemini response generated',
    unavailable: 'AI explanation unavailable',
    skipped_no_records: 'No records to explain',
    empty: 'No records in this period',
    insufficient_data: 'Limited data',
    complete: 'Analysis complete',
  }
  return labels[status] ?? 'Status unavailable'
}

function ReportMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="health-report-metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

function ReportDetailFindings({ title, findings, summaryForFinding }: {
  title: string
  findings: HealthFinding[]
  summaryForFinding?: (finding: HealthFinding) => string | null
}) {
  if (!findings.length) return null
  return <div className="health-report-detail-group">
    <h4>{title}</h4>
    {findings.map((finding, index) => <article className="health-report-detail-finding" key={`${finding.code}:${index}`}>
      <strong>{finding.code.replaceAll('_', ' ')}</strong>
      {finding.sample_size !== undefined && <span>Sample size · {finding.sample_size}</span>}
      <p>{summaryForFinding?.(finding) ?? finding.summary}</p>
      {Object.keys(finding.supporting_metrics).length > 0 && <dl>{Object.entries(finding.supporting_metrics).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl>}
      {finding.evidence_references.length > 0 && <small>Evidence references · {finding.evidence_references.join(' · ')}</small>}
    </article>)}
  </div>
}

function HealthIntelligencePanel({ patientId }: { patientId: string }) {
  const window = defaultReportWindow()
  const [dateFrom, setDateFrom] = useState(window.from)
  const [dateTo, setDateTo] = useState(window.to)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<HealthIntelligenceResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const requestLock = useRef(false)
  const requestVersion = useRef(0)
  useEffect(() => {
    requestVersion.current += 1
    requestLock.current = false
    setResult(null)
    setError(null)
    setLoading(false)
    return () => { requestVersion.current += 1 }
  }, [patientId])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!patientId.trim() || requestLock.current) return
    if (dateFrom > dateTo) { setError('Choose a start date on or before the end date.'); return }
    if (question.trim().length > 1000) { setError('The optional education question must be 1,000 characters or fewer.'); return }
    requestLock.current = true
    const requestId = ++requestVersion.current
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const payload: { date_from: string; date_to: string; educational_question?: string } = { date_from: dateFrom, date_to: dateTo }
      if (question.trim()) payload.educational_question = question.trim()
      const response = await api.generateHealthIntelligence(patientId.trim(), payload)
      if (requestVersion.current === requestId) setResult(response)
    } catch (requestError) {
      if (requestVersion.current === requestId) setError(errorMessage(requestError))
    } finally {
      if (requestVersion.current === requestId) {
        requestLock.current = false
        setLoading(false)
      }
    }
  }

  const report = result?.report
  const knowledge = result?.medical_knowledge ?? report?.medical_knowledge_context
  const symptomFindings = report?.symptom_analysis?.key_findings ?? []
  const lifestyleFindings = report?.lifestyle_analysis?.key_findings ?? []
  const symptomCount = reportMetric(symptomFindings, ['symptom_frequency', 'no_symptoms'], 'total_entries')
  const averageSeverity = reportMetric(symptomFindings, ['severity_summary'], 'average_severity')
  const highestSeverity = reportMetric(symptomFindings, ['severity_summary'], 'maximum_severity')
  const checkinCount = reportMetric(lifestyleFindings, ['mood_distribution', 'no_lifestyle_records'], 'checkin_count')
    ?? lifestyleFindings.find((finding) => finding.code === 'mood_distribution')?.sample_size
    ?? null
  const averageMood = reportMetric(lifestyleFindings, ['mood_distribution'], 'average_mood_rating')
  const averageSleep = reportMetric(lifestyleFindings, ['sleep_duration_summary'], 'average_hours')
  const averageSleepQuality = reportMetric(lifestyleFindings, ['sleep_quality_distribution'], 'average_quality')
  const missingDates = report?.lifestyle_analysis?.missing_mood_dates ?? []
  const missingSleepDates = report?.lifestyle_analysis?.missing_sleep_dates ?? []
  const missingListsMatch = missingDates.length === missingSleepDates.length && missingDates.every((day, index) => day === missingSleepDates[index])
  const rangeDays = result ? Math.floor((Date.parse(`${result.date_to}T00:00:00Z`) - Date.parse(`${result.date_from}T00:00:00Z`)) / 86400000) + 1 : 0
  const uncategorizedCount = reportMetric(symptomFindings, ['category_distribution'], 'Uncategorized')
  const categoryWarning = report?.symptom_analysis?.warnings.some((warning) => warning.includes('no category')) ?? false
  const comparisonFindings = lifestyleFindings.filter((finding) => ['symptom_severity_by_mood', 'symptom_severity_by_sleep_duration', 'symptom_severity_by_sleep_quality'].includes(finding.code))
  const formattedComparisons = comparisonFindings.map(formatLifestyleComparison).filter((value): value is string => value !== null)
  const observations = [
    ...symptomFindings.filter((finding) => ['recurring_categories', 'severity_increase', 'severity_decrease', 'severity_stable'].includes(finding.code)).map(formatKeyObservation).filter((value): value is string => value !== null),
    ...(categoryWarning || (uncategorizedCount !== null && uncategorizedCount > 0) ? ['Some symptom entries do not have a category.'] : []),
    ...lifestyleFindings.filter((finding) => finding.code === 'mood_change_comparison').map(formatKeyObservation).filter((value): value is string => value !== null),
    ...formattedComparisons,
  ].filter((value, index, values) => values.indexOf(value) === index)
  const deterministicText = [...(report?.deterministic_observations ?? []), ...observations]
  const additionalAiExplanations = (report?.ai_generated_explanations ?? []).filter((explanation) => !deterministicText.some((observation) => materiallySimilar(explanation, observation)))
  const qualityMessages = report ? [...new Set([
    ...result.warnings,
    ...report.warnings,
    ...(report.symptom_analysis?.warnings ?? []),
    ...(report.lifestyle_analysis?.warnings ?? []),
  ])].filter((message) => /insufficient|not enough|requires at least|no same-date|matching .* unavailable|severity change was not assessed|too few daily check-ins/i.test(message)
    && !/AI-generated explanations|authorization/i.test(message)).map(conciseQualityMessage) : []
  if (comparisonFindings.length > formattedComparisons.length) qualityMessages.push('Some mood or sleep comparisons did not include enough matching metrics to summarize.')
  if (lifestyleFindings.some((finding) => finding.code === 'no_matched_symptom_data') && !qualityMessages.some((message) => /mood and sleep comparisons need dates/i.test(message))) {
    qualityMessages.push('No same-date symptom information was available to compare with mood or sleep.')
  }
  const technicalWarnings = report ? [...new Set([
    ...result.warnings,
    ...report.warnings,
    ...report.limitations,
    ...(report.symptom_analysis?.warnings ?? []),
    ...(report.symptom_analysis?.limitations ?? []),
    ...(report.lifestyle_analysis?.warnings ?? []),
    ...(report.lifestyle_analysis?.limitations ?? []),
  ])] : []
  const symptomCategoryFindings = symptomFindings.filter((finding) => finding.code === 'category_distribution')
  const otherSymptomFindings = symptomFindings.filter((finding) => finding.code !== 'category_distribution')
  const otherLifestyleFindings = lifestyleFindings.filter((finding) => !['symptom_severity_by_mood', 'symptom_severity_by_sleep_duration', 'symptom_severity_by_sleep_quality'].includes(finding.code))
  const hasEducationDetails = Boolean(report?.general_educational_information || report?.educational_sources.length || knowledge)
  return <div className="health-intelligence-wrap">
    <Panel className="health-intelligence-form" glow>
      <div className="health-intelligence-form-head"><div><div className="panel-kicker">BOUNDED, EXPLICIT ANALYSIS</div><h2>Health Intelligence Report</h2><p>Combines deterministic symptom and lifestyle findings. An education question is optional and is handled separately from your patient record.</p></div><div className="health-report-mark"><BrainCircuit size={20} /></div></div>
      <form onSubmit={submit}>
        <div className="health-report-controls"><label>FROM · UTC<input type="date" value={dateFrom} max={dateTo} onChange={(event) => setDateFrom(event.target.value)} /></label><label>TO · UTC<input type="date" value={dateTo} min={dateFrom} onChange={(event) => setDateTo(event.target.value)} /></label></div>
        <label className="health-question-label">OPTIONAL GENERAL EDUCATION QUESTION<textarea value={question} maxLength={1000} onChange={(event) => setQuestion(event.target.value)} placeholder="Example: What is a fever?" rows={2} /><span>{question.length} / 1,000 · Only this question is sent to the existing education retrieval flow.</span></label>
        <div className="health-intelligence-form-foot"><span>{patientId ? `Patient scope · ${patientId}` : 'Select a patient ID above before continuing.'}</span><Button disabled={!patientId.trim() || loading}>{loading ? <><span className="button-spinner" /> Building report…</> : <>Generate report <ArrowRight size={14} /></>}</Button></div>
      </form>
    </Panel>
    {error && <div className="integration-alert" role="alert"><div className="alert-icon">!</div><div><strong>Health Intelligence unavailable</strong><p>{error}</p></div></div>}
    {loading ? <Panel className="summary-result"><LoadingState label="Gathering bounded evidence and preparing the report…" /></Panel>
      : !report ? <Panel className="summary-result"><EmptyState icon={BrainCircuit} title={patientId ? 'No report requested' : 'Select a patient to continue'} description={patientId ? 'Nothing is analyzed until you explicitly generate a report.' : 'Enter an existing patient ID above, then choose Generate report.'} /></Panel>
        : <div className="health-report">
          <Panel className="health-report-executive" glow>
            <div className="health-report-title-row"><div><div className="panel-kicker">HEALTH INTELLIGENCE REPORT</div><h2>Executive summary</h2></div><span className={`health-report-ai-status status-${report.ai_explanation_status}`}>{statusLabel(report.ai_explanation_status)}</span></div>
            <p className="health-report-summary">{report.executive_summary}</p>
            <div className="health-report-scope"><span>Patient scope</span><strong>{result.patient_id}</strong><span>Report period</span><strong>{result.date_from} — {result.date_to} UTC</strong></div>
          </Panel>

          <Panel className="health-report-section">
            <div className="health-report-section-heading"><div><div className="panel-kicker">AT A GLANCE</div><h3>Recorded during this period</h3></div></div>
            <div className="health-report-metrics">
              <ReportMetric label="SYMPTOM ENTRIES" value={symptomCount === null ? '—' : String(symptomCount)} />
              <ReportMetric label="AVERAGE SEVERITY" value={averageSeverity === null ? '—' : `${averageSeverity.toFixed(2)} / 10`} />
              <ReportMetric label="HIGHEST SEVERITY" value={highestSeverity === null ? '—' : `${highestSeverity} / 10`} />
              <ReportMetric label="MOOD & SLEEP CHECK-INS" value={checkinCount === null ? '—' : String(checkinCount)} />
            </div>
          </Panel>

          <Panel className="health-report-section">
            <div className="panel-kicker">DETERMINISTIC ANALYSIS</div><h3>Key observations</h3>
            {observations.length ? <ReportBulletList items={observations} emptyText="No key observations were returned." /> : <div className="health-report-empty">No recurring categories or meaningful severity changes were identified in the available records.</div>}
          </Panel>

          <Panel className="health-report-section">
            <div className="panel-kicker">PATIENT-RECORDED MOOD & SLEEP</div><h3>Lifestyle overview</h3>
            <div className="health-report-lifestyle-metrics">
              <ReportMetric label="AVERAGE MOOD" value={averageMood === null ? '—' : `${averageMood.toFixed(2)} / 5`} />
              <ReportMetric label="AVERAGE SLEEP" value={averageSleep === null ? '—' : `${averageSleep.toFixed(2)} hours`} />
              <ReportMetric label="AVERAGE SLEEP QUALITY" value={averageSleepQuality === null ? '—' : `${averageSleepQuality.toFixed(2)} / 5`} />
            </div>
            {!checkinCount && <p className="health-report-empty">No mood and sleep check-ins were recorded in this period.</p>}
          </Panel>

          <Panel className="health-report-section health-report-ai">
            <div className="health-report-section-heading"><div><div className="panel-kicker">AI-GENERATED EXPLANATIONS</div><h3>Additional plain-language context</h3></div><span className={`health-report-ai-status status-${report.ai_explanation_status}`}>{statusLabel(report.ai_explanation_status)}</span></div>
            {report.ai_explanation_status === 'generated' && additionalAiExplanations.length
              ? <ReportBulletList items={additionalAiExplanations} emptyText="No additional explanation was returned." />
              : <p className="health-report-ai-fallback">{report.ai_explanation_status === 'unavailable' ? 'AI explanations could not be generated. Recorded facts and deterministic observations remain available above.' : 'No additional AI explanation is available beyond the findings shown above.'}</p>}
          </Panel>

          {knowledge && <Panel className="health-report-section health-education-context"><div className="panel-kicker">GENERAL HEALTH EDUCATION</div><h3>{knowledge.question}</h3><p className="health-agent-status">General information · Not a conclusion about this patient.</p><blockquote>{knowledge.answer}</blockquote>{knowledge.sources.length ? <div className="source-list">{knowledge.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer"><span>{source.title}</span><ArrowRight size={13} /></a>)}</div> : <p className="health-report-empty">No relevant source was returned.</p>}</Panel>}

          <Panel className="health-report-section health-report-quality">
            <div className="panel-kicker">DATA QUALITY & LIMITATIONS</div><h3>What to keep in mind</h3>
            <div className="health-report-quality-summary">
              {rangeDays > 0 && <p>{missingDates.length} of {rangeDays} days have no mood and sleep check-in.</p>}
              {!rangeDays && <p>No daily mood or sleep check-in data was returned for this report.</p>}
              {qualityMessages.length ? <ul>{qualityMessages.slice(0, 3).map((message) => <li key={message}>{message}</li>)}</ul> : <p>No additional data warnings were returned.</p>}
              {qualityMessages.length > 3 && <span>{qualityMessages.length - 3} additional notes are available in advanced details.</span>}
            </div>
          </Panel>

          <details className="health-report-advanced">
            <summary><span><small>ADVANCED TECHNICAL DETAILS</small><strong>Supporting metrics, evidence & full records</strong></span><ChevronDown size={17} /></summary>
            <div className="health-report-advanced-body">
              {report.patient_recorded_facts.length > 0 && <section className="health-report-detail-group"><h4>Patient-recorded facts</h4><ReportBulletList items={report.patient_recorded_facts} emptyText="" /></section>}
              {report.deterministic_observations.length > 0 && <section className="health-report-detail-group"><h4>Deterministic observations</h4><ReportBulletList items={report.deterministic_observations} emptyText="" /></section>}
              <ReportDetailFindings title="Symptom category distribution" findings={symptomCategoryFindings} />
              <ReportDetailFindings title="Symptom findings & supporting evidence" findings={otherSymptomFindings} />
              <ReportDetailFindings title="Same-date comparisons, matching counts & evidence" findings={comparisonFindings} summaryForFinding={(finding) => formatLifestyleComparison(finding) ?? 'No matching values were returned for this comparison.'} />
              <ReportDetailFindings title="Lifestyle findings & supporting evidence" findings={otherLifestyleFindings} />
              {report.symptom_analysis?.concise_explanation && <section className="health-report-detail-group"><h4>Symptom analysis explanation</h4><p>{report.symptom_analysis.concise_explanation}</p></section>}
              {report.lifestyle_analysis?.concise_explanation && <section className="health-report-detail-group"><h4>Lifestyle analysis explanation</h4><p>{report.lifestyle_analysis.concise_explanation}</p></section>}
              {missingListsMatch
                ? missingDates.length > 0 && <section className="health-report-detail-group"><h4>Missing mood & sleep check-in dates</h4><p>{missingDates.join(' · ')}</p></section>
                : <>
                  {missingDates.length > 0 && <section className="health-report-detail-group"><h4>Missing mood check-in dates</h4><p>{missingDates.join(' · ')}</p></section>}
                  {missingSleepDates.length > 0 && <section className="health-report-detail-group"><h4>Missing sleep check-in dates</h4><p>{missingSleepDates.join(' · ')}</p></section>}
                </>}
              {technicalWarnings.length > 0 && <section className="health-report-detail-group"><h4>Warnings & limitations</h4><ReportBulletList items={technicalWarnings} emptyText="" /></section>}
              {hasEducationDetails && <section className="health-report-detail-group"><h4>Education information & source references</h4>
                {knowledge && <><p>Status · {knowledge.agent_status}</p><p>Question · {knowledge.question}</p></>}
                {report.general_educational_information && <p>{report.general_educational_information}</p>}
                {(report.educational_sources.length ? report.educational_sources : knowledge?.sources ?? []).map((source) => <p key={source.url}>{source.title} · {source.url}</p>)}
                {knowledge && [...knowledge.warnings, ...knowledge.limitations].length > 0 && <ReportBulletList items={[...knowledge.warnings, ...knowledge.limitations]} emptyText="" />}
              </section>}
              <section className="health-report-detail-group"><h4>Report identifiers</h4><p>Request · {result.request_id}</p><p>Patient · {result.patient_id}</p><p>Report period · {result.date_from} — {result.date_to} UTC</p></section>
            </div>
          </details>

          <Panel className="health-report-disclaimer"><ShieldCheck size={16} /><div><strong>Educational prototype · not clinical decision support</strong><p>{report.prototype_notice} {report.disclaimer}</p></div></Panel>
        </div>}
  </div>
}


function SummaryPage({ patientId }: { patientId: string }) {
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof api.generateSummary>> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requestVersion = useRef(0)
  const requestLock = useRef(false)

  useEffect(() => {
    requestVersion.current += 1
    setSummary(null)
    setError(null)
    setLoading(false)

    return () => {
      requestVersion.current += 1
    }
  }, [patientId])

  const generate = async () => {
    if (!patientId.trim() || requestLock.current) return

    requestLock.current = true
    const requestId = ++requestVersion.current

    setError(null)
    setSummary(null)
    setLoading(true)

    try {
      const response = await api.generateSummary(patientId.trim())

      if (requestVersion.current === requestId) {
        setSummary(response)
      }
    } catch (requestError) {
      if (requestVersion.current === requestId) {
        setError(errorMessage(requestError, 'summary'))
      }
    } finally {
      requestLock.current = false

      if (requestVersion.current === requestId) {
        setLoading(false)
      }
    }
  }

  return (
    <>
      <PageHeading page="summary" patientId={patientId} />

      <div className="summary-layout">
        <Panel className="summary-hero" glow>
          <div className="summary-hero-orb">
            <div className="summary-orbit orbit-a" />
            <div className="summary-orbit orbit-b" />
            <div className="summary-orbit orbit-c" />
            <BrainCircuit size={28} strokeWidth={1.35} />
          </div>

          <div className="summary-hero-content">
            <div className="panel-kicker">
              PREPARE FOR YOUR NEXT VISIT
            </div>

            <h2>
              A thoughtful summary.
              <br />
              <span>On your terms.</span>
            </h2>

            <p>
              This sends the selected patient’s recorded symptom history
              to Gemini to create a non-diagnostic visit summary.
            </p>

            <Button
              onClick={generate}
              disabled={!patientId.trim() || loading}
            >
              {loading ? (
                <>
                  <span className="button-spinner" />
                  Generating…
                </>
              ) : (
                <>
                  Generate summary
                  <Sparkles size={15} />
                </>
              )}
            </Button>

            <div className="summary-hero-foot">
              <span className={patientId ? 'live-dot' : 'pending-indicator'}>
                {!patientId && <span />}
              </span>

              {patientId
                ? `Patient · ${patientId}`
                : 'Select a patient ID before continuing'}
            </div>
          </div>

          <div className="summary-decor summary-decor-one" />
          <div className="summary-decor summary-decor-two" />
        </Panel>

        <div className="summary-side">
          <Panel className="summary-process">
            <div className="panel-kicker">HOW IT WORKS</div>
            <h3>Built around your record.</h3>

            <div className="process-list">
              <div className="process-item">
                <span className="process-number">01</span>
                <span className="process-line" />
                <div>
                  <strong>Your entries</strong>
                  <p>Only recorded symptoms provide context.</p>
                </div>
              </div>

              <div className="process-item">
                <span className="process-number">02</span>
                <span className="process-line" />
                <div>
                  <strong>AI-assisted structure</strong>
                  <p>Facts and generated observations stay distinct.</p>
                </div>
              </div>

              <div className="process-item">
                <span className="process-number">03</span>
                <span className="process-line" />
                <div>
                  <strong>You choose what to share</strong>
                  <p>Review a draft before discussing it with a clinician.</p>
                </div>
              </div>
            </div>
          </Panel>

          <Panel className="summary-safety">
            <div className="safety-icon">
              <ShieldCheck size={17} />
            </div>

            <div>
              <div className="panel-kicker">YOUR CONTROL</div>
              <h3>Nothing is generated automatically.</h3>
              <p>
                Summary generation is an explicit action.
                This tool does not diagnose or prescribe.
              </p>
            </div>
          </Panel>
        </div>
      </div>

      {error && (
        <div className="integration-alert" role="alert">
          <div className="alert-icon">!</div>
          <div>
            <strong>Summary unavailable</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {loading ? (
        <Panel className="summary-result">
          <LoadingState label="Requesting a summary from Gemini…" />
        </Panel>
      ) : summary ? (
        <Panel className="summary-result summary-result-filled">
          <div className="summary-result-header">
            <div>
              <div className="panel-kicker">
                GENERATED FOR {summary.patient_id}
              </div>
              <h2>Doctor-visit summary</h2>
            </div>

            <span className="summary-model">
              {summary.model}
            </span>
          </div>

          <div className="summary-record">
            <div className="summary-record-meta">
              Based on {summary.entry_count} recorded{' '}
              {summary.entry_count === 1 ? 'entry' : 'entries'}
            </div>

            <div className="summary-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {cleanGeneratedMarkdown(summary.summary)}
              </ReactMarkdown>
            </div>

            <div className="summary-disclaimer">
              <ShieldCheck size={14} />
              <span>{summary.disclaimer}</span>
            </div>
          </div>
        </Panel>
      ) : (
        <Panel className="summary-result">
          <EmptyState
            icon={BrainCircuit}
            title={
              patientId
                ? 'No summary requested'
                : 'Select a patient to continue'
            }
            description={
              patientId
                ? 'Nothing has been sent to Gemini. Choose Generate summary when you are ready.'
                : 'Enter a patient ID above, then choose Generate summary to request a result.'
            }
          />
        </Panel>
      )}

      <HealthIntelligencePanel patientId={patientId} />
    </>
  )
}


function EducationPage() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Awaited<ReturnType<typeof api.askHealthQuestion>> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const requestLock = useRef(false)

  const submitQuestion = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const cleaned = question.trim()
    setError(null)
    if (!cleaned) { setError('Enter a question before submitting.'); return }
    if (cleaned.length > 1000) { setError('Questions must be 1,000 characters or fewer.'); return }
    if (requestLock.current) return
    requestLock.current = true
    setLoading(true)
    setAnswer(null)
    try { setAnswer(await api.askHealthQuestion(cleaned)) }
    catch (requestError) { setError(errorMessage(requestError, 'rag')) }
    finally { requestLock.current = false; setLoading(false) }
  }

  return <><PageHeading page="education" /><Panel className="education-hero" glow>
    <div className="education-content"><div className="panel-kicker"><span className="kicker-sparkle"><Sparkles size={13} /></span> GROUNDED HEALTH INFORMATION</div><h2>Curiosity is a good<br /><span>place to start.</span></h2><p>Ask a general health question and explore an answer grounded in curated MedlinePlus resources.</p>
      <form onSubmit={submitQuestion}><div className="education-search"><Search size={18} /><input value={question} maxLength={1000} onChange={(event) => setQuestion(event.target.value)} placeholder="What would you like to understand?" aria-label="Health education question" /><span className="search-shortcut"><Command size={12} /> ↵</span></div><div className="education-search-foot"><span>Health education only · not for diagnosis</span><Button disabled={question.trim().length === 0 || loading}>{loading ? <><span className="button-spinner" /> Searching…</> : <>Ask question <ArrowRight size={15} /></>}</Button></div></form><div className="education-disabled-note">Questions are sent only when you choose Ask question. Maximum 1,000 characters.</div>
    </div>
    <div className="education-visual" aria-hidden="true"><div className="edu-orbit edu-orbit-large" /><div className="edu-orbit edu-orbit-small" /><div className="edu-core"><MessageCircleQuestion size={29} strokeWidth={1.2} /></div><div className="edu-satellite satellite-one"><HeartPulse size={16} /></div><div className="edu-satellite satellite-two"><Sparkles size={15} /></div><span className="edu-star star-one" /><span className="edu-star star-two" /><span className="edu-star star-three" /></div>
  </Panel>
  {error && <div className="integration-alert" role="alert"><div className="alert-icon">!</div><div><strong>Answer unavailable</strong><p>{error}</p></div></div>}
  {loading ? <Panel className="rag-response"><LoadingState label="Searching the curated health education sources…" /></Panel>
    : answer ? <Panel className="rag-response"><div className="rag-answer-heading"><div><div className="panel-kicker">HEALTH EDUCATION RESPONSE</div><h2>{answer.question}</h2></div><span className="grounded-badge"><ShieldCheck size={13} /> GROUNDED</span></div><div className="rag-answer-body">{answer.answer}</div><div className="rag-disclaimer">General health education only. This answer is not a diagnosis or substitute for professional medical advice.</div>{answer.sources.length > 0 ? <div className="source-list"><div className="panel-kicker">SOURCES RETURNED BY THE API</div>{answer.sources.map((source) => <a key={`${source.title}:${source.url}`} href={source.url} target="_blank" rel="noreferrer"><span>{source.title}</span><ArrowRight size={14} /></a>)}</div> : <div className="no-sources">The API returned no matching source references for this answer.</div>}</Panel>
      : <Panel className="rag-response"><EmptyState icon={MessageCircleQuestion} title="Ask when you’re ready" description="The answer and any available source references will appear here after you submit a question." /></Panel>}
  <div className="education-lower-head"><div><div className="panel-kicker">CURATED SOURCES</div><h2>A small library, carefully chosen.</h2></div><span className="muted-note">Four reference topics</span></div>
  <div className="topic-grid">{[{ title: 'Headache', code: '01', icon: BrainCircuit, color: 'violet' }, { title: 'Fever', code: '02', icon: Activity, color: 'coral' }, { title: 'Dehydration', code: '03', icon: HeartPulse, color: 'blue' }, { title: 'Common cold', code: '04', icon: AudioLines, color: 'mint' }].map(({ title, code, icon: Icon, color }) => <div key={title} className="topic-card"><div className={`topic-icon topic-${color}`}><Icon size={17} /></div><div className="topic-code">TOPIC / {code}</div><h3>{title}</h3><span className="topic-arrow"><ArrowRight size={15} /></span></div>)}</div>
  <div className="education-source-note"><ShieldCheck size={15} /><span>Answers are grounded in curated public health education documents.</span><span className="source-note-tail">MEDLINEPLUS REFERENCES</span></div></>
}

function PageContent({ page, onNavigate, patientId }: { page: PageId; onNavigate: (page: PageId) => void; patientId: string }) {
  switch (page) {
    case 'overview': return <OverviewPage onNavigate={onNavigate} patientId={patientId} />
    case 'tracking': return <TrackingPage patientId={patientId} />
    case 'mood-sleep': return <MoodSleepPage patientId={patientId} />
    case 'analytics': return <AnalyticsPage patientId={patientId} />
    case 'summary': return <SummaryPage patientId={patientId} />
    case 'education': return <EducationPage />
  }
}

export default function App() {
  const [activePage, setActivePage] = useState<PageId>('overview')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [patientId, setPatientId] = useState('')
  const backendCheck = useCallback(async (signal: AbortSignal) => {
    await Promise.all([api.getRoot(signal), api.getHealth(signal)])
  }, [])
  const backend = useApiResource('backend-status', backendCheck)
  const connection = backend.status === 'success' ? 'connected' : backend.status === 'error' ? 'offline' : 'loading'
  return <div className="app-shell"><div className="ambient-glow ambient-glow-one" /><div className="ambient-glow ambient-glow-two" />
    <Sidebar activePage={activePage} onNavigate={setActivePage} mobileOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
    <div className="main-shell"><Topbar page={activePage} onMenu={() => setMobileNavOpen(true)} patientId={patientId} onApplyPatient={setPatientId} connection={connection} /><main className="main-content">
      <AnimatePresence mode="wait" initial={false}><motion.div key={activePage} className="page-transition" initial={{ opacity: 0, y: 9, filter: 'blur(3px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, y: -5, filter: 'blur(2px)' }} transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}><PageContent page={activePage} onNavigate={setActivePage} patientId={patientId} /></motion.div></AnimatePresence>
      <footer className="page-footer"><span>HEALTHTRACK AI <i /> PERSONAL HEALTH JOURNAL</span><span>Designed for clarity, not diagnosis.</span></footer>
    </main></div>
  </div>
}

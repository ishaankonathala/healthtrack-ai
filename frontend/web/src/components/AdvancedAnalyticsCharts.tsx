import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { AdvancedAnalytics } from '../api/client'

const axis = { fill: '#819399', fontSize: 9 }
const tooltip = { border: '1px solid rgba(144,174,188,.2)', borderRadius: 9, background: 'rgba(9,16,24,.97)', color: '#d9e8e8', fontSize: 10 }

export default function AdvancedAnalyticsCharts({ data }: { data: AdvancedAnalytics }) {
  const dateLabel = (value: string) => value.slice(5)
  return <div className="advanced-chart-grid">
    <section className="panel advanced-chart-panel"><div className="panel-kicker">HEALTH TREND</div><h2>{data.interval[0].toUpperCase() + data.interval.slice(1)} symptom severity</h2>
      {data.trend.length ? <div className="advanced-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.trend}><CartesianGrid stroke="rgba(138,163,171,.13)" strokeDasharray="4 6" vertical={false} /><XAxis dataKey="period_start" tickFormatter={dateLabel} tick={axis} /><YAxis domain={[0,10]} tick={axis} /><Tooltip labelFormatter={(label) => dateLabel(String(label))} contentStyle={tooltip} /><Line type="monotone" dataKey="average_severity" name="Average severity" stroke="#56dbc9" strokeWidth={2.4} dot={false} /><Line type="monotone" dataKey="maximum_severity" name="Maximum severity" stroke="#e5a36e" strokeWidth={1.5} dot={false} /></LineChart></ResponsiveContainer></div> : <p className="advanced-empty">No symptoms recorded in this date range.</p>}
    </section>
    <section className="panel advanced-chart-panel"><div className="panel-kicker">SYMPTOM FREQUENCY</div><h2>Entries by category</h2>
      {data.category_frequency.length ? <div className="advanced-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.category_frequency} layout="vertical" margin={{ left: 8 }}><CartesianGrid stroke="rgba(138,163,171,.13)" strokeDasharray="4 6" horizontal={false} /><XAxis type="number" tick={axis} /><YAxis type="category" dataKey="category" width={120} tick={axis} /><Tooltip contentStyle={tooltip} /><Bar dataKey="entry_count" name="Entries" fill="#56dbc9" radius={[0,4,4,0]} /></BarChart></ResponsiveContainer></div> : <p className="advanced-empty">Category counts will appear when symptom records are available.</p>}
    </section>
    <section className="panel advanced-chart-panel"><div className="panel-kicker">CATEGORY SEVERITY</div><h2>Average severity by category</h2>
      {data.category_severity.length ? <div className="advanced-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.category_severity} layout="vertical" margin={{ left: 8 }}><CartesianGrid stroke="rgba(138,163,171,.13)" strokeDasharray="4 6" horizontal={false} /><XAxis type="number" domain={[0,10]} tick={axis} /><YAxis type="category" dataKey="category" width={120} tick={axis} /><Tooltip contentStyle={tooltip} /><Bar dataKey="average_severity" name="Average severity" fill="#77b9ed" radius={[0,4,4,0]} /></BarChart></ResponsiveContainer></div> : <p className="advanced-empty">Category severity will appear when symptom records are available.</p>}
    </section>
    <section className="panel advanced-chart-panel"><div className="panel-kicker">SLEEP COMPARISON</div><h2>Severity by sleep duration</h2>
      {data.severity_by_sleep_duration.length ? <ComparisonChart rows={data.severity_by_sleep_duration} /> : <p className="advanced-empty">No dates have both symptom and sleep records in this range.</p>}
    </section>
    <section className="panel advanced-chart-panel"><div className="panel-kicker">MOOD COMPARISON</div><h2>Severity by mood rating</h2>
      {data.severity_by_mood_rating.length ? <ComparisonChart rows={data.severity_by_mood_rating} /> : <p className="advanced-empty">No dates have both symptom and mood records in this range.</p>}
    </section>
  </div>
}

function ComparisonChart({ rows }: { rows: AdvancedAnalytics['severity_by_mood_rating'] }) {
  return <div className="advanced-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows}><CartesianGrid stroke="rgba(138,163,171,.13)" strokeDasharray="4 6" vertical={false} /><XAxis dataKey="group" tick={axis} /><YAxis domain={[0,10]} tick={axis} /><Tooltip contentStyle={tooltip} formatter={(value, name, item) => [Number(value).toFixed(2), `${String(name)} · ${item.payload.matching_symptom_entries} matched entries`]} /><Bar dataKey="average_severity" name="Average severity" fill="#b19ae9" radius={[4,4,0,0]} /></BarChart></ResponsiveContainer></div>
}

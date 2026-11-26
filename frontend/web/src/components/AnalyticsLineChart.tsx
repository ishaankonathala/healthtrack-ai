import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { DailySeverityPoint } from '../api/client'

export default function AnalyticsLineChart({
  data,
  formatDate,
}: {
  data: DailySeverityPoint[]
  formatDate: (date: string) => string
}) {
  return <div className="real-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 18, right: 12, bottom: 2, left: -16 }}>
    <CartesianGrid stroke="rgba(138, 163, 171, .13)" strokeDasharray="4 6" vertical={false} />
    <XAxis dataKey="date" tickFormatter={formatDate} tick={{ fill: '#819399', fontSize: 9 }} axisLine={{ stroke: 'rgba(138,163,171,.16)' }} tickLine={false} minTickGap={22} />
    <YAxis domain={[0, 10]} ticks={[0, 2, 4, 6, 8, 10]} tick={{ fill: '#819399', fontSize: 9 }} axisLine={false} tickLine={false} />
    <Tooltip
      labelFormatter={(label) => formatDate(String(label))}
      formatter={(value, _name, item) => [`${Number(value).toFixed(2)} / 10 · ${item.payload.entry_count} entr${item.payload.entry_count === 1 ? 'y' : 'ies'}`, 'Average severity']}
      contentStyle={{ border: '1px solid rgba(144,174,188,.2)', borderRadius: 9, background: 'rgba(9,16,24,.97)', color: '#d9e8e8', fontSize: 10 }}
      labelStyle={{ color: '#9eb3b6', marginBottom: 4 }}
      itemStyle={{ color: '#65dec9' }}
      cursor={{ stroke: 'rgba(93,210,195,.25)' }}
    />
    <Line type="monotone" dataKey="average_severity" name="Average severity" stroke="#56dbc9" strokeWidth={2.4} dot={{ r: 3.5, fill: '#071017', stroke: '#73e5d3', strokeWidth: 2 }} activeDot={{ r: 5, fill: '#74ead8', stroke: '#102a2a', strokeWidth: 2 }} />
  </LineChart></ResponsiveContainer></div>
}

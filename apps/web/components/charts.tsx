'use client';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { SimResult } from '@sih/types';

const BRAND = '#0b5d4b', SAFF = '#b7791f', INK = '#6b7c89';

export function SensitivityChart({ data, metric, metricLabel }: { data: SimResult['sensitivity'][string]; metric: string; metricLabel: string }) {
  const pts = data.points.map((p) => ({ x: p.value, y: p[metric] as number }));
  const cur = pts.find((p) => p.x === data.current);
  return (
    <div className="h-64 w-full" role="img" aria-label={`Sensitivity of ${metricLabel} to ${data.label}`}>
      <ResponsiveContainer>
        <LineChart data={pts} margin={{ top: 10, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="#e7ebee" strokeDasharray="3 3" />
          <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} ticks={pts.map((p) => p.x)} tick={{ fontSize: 11, fill: INK }} label={{ value: `${data.label} (${data.unit})`, position: 'insideBottom', offset: -10, fontSize: 11, fill: INK }} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11, fill: INK }} width={44} />
          <Tooltip formatter={(v: number) => [v.toFixed(1), metricLabel]} labelFormatter={(l) => `${data.label}: ${l}`} />
          <Line type="monotone" dataKey="y" stroke={BRAND} strokeWidth={2} dot={{ r: 3 }} />
          {cur && <ReferenceDot x={cur.x} y={cur.y} r={6} fill={SAFF} stroke="#fff" strokeWidth={2} />}
        </LineChart>
      </ResponsiveContainer>
    </div>);
}

export function TornadoChart({ rows }: { rows: SimResult['tornado'] }) {
  const data = rows.map((r) => ({ name: r.label, low: (r.low_output ?? r.base_output) - r.base_output, high: (r.high_output ?? r.base_output) - r.base_output }));
  return (
    <div className="h-64 w-full" role="img" aria-label="One-at-a-time sensitivity of the composite impact index (±10% of each input)">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }} stackOffset="sign">
          <CartesianGrid stroke="#e7ebee" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11, fill: INK }} />
          <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 11, fill: INK }} />
          <Tooltip formatter={(v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)} pts`} /><Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="low" name="−10% input" fill={SAFF} stackId="s" />
          <Bar dataKey="high" name="+10% input" fill={BRAND} stackId="s" />
        </BarChart>
      </ResponsiveContainer>
    </div>);
}

export function BaselineBars({ outputs }: { outputs: SimResult['outputs'] }) {
  const data = outputs.filter((o) => o.key !== 'coverage_gap').map((o) => ({ name: o.label.replace(' index', ''), Baseline: o.baseline, Scenario: o.scenario }));
  return (
    <div className="h-64 w-full" role="img" aria-label="Baseline versus scenario indicator values">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#e7ebee" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: INK }} interval={0} />
          <YAxis tick={{ fontSize: 11, fill: INK }} width={40} /><Tooltip />
          <Bar dataKey="Baseline" fill="#9aa7b1" radius={[3, 3, 0, 0]} /><Bar dataKey="Scenario" fill={BRAND} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>);
}

export function Trend({ series, good }: { series: { period: number; value: number }[]; good?: boolean | null }) {
  if (series.length < 2) return null;
  return (
    <div className="h-12 w-28"><ResponsiveContainer><LineChart data={series}><Line type="monotone" dataKey="value" stroke={good === false ? '#a12b2b' : BRAND} strokeWidth={2} dot={false} />
      <YAxis hide domain={['auto', 'auto']} /><Tooltip formatter={(v: number) => v.toFixed(1)} labelFormatter={(_, p) => String(p?.[0]?.payload?.period ?? '')} /></LineChart></ResponsiveContainer></div>);
}

export function StateBars({ rows, unit }: { rows: { state: string; value: number }[]; unit: string }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="h-40 w-full"><ResponsiveContainer><BarChart data={rows} layout="vertical" margin={{ left: 0, right: 24, top: 0, bottom: 0 }}>
      <XAxis type="number" hide domain={[0, max * 1.1]} /><YAxis type="category" dataKey="state" width={80} tick={{ fontSize: 11, fill: INK }} axisLine={false} tickLine={false} />
      <Tooltip formatter={(v: number) => [`${v.toFixed(1)} ${unit}`, '']} />
      <Bar dataKey="value" radius={[0, 3, 3, 0]}>{rows.map((_, i) => <Cell key={i} fill={i % 2 ? '#0e6e58' : BRAND} />)}</Bar></BarChart></ResponsiveContainer></div>);
}

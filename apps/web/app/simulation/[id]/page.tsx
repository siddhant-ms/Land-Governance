'use client';
import { ArrowDown, ArrowUp, Download, Minus } from 'lucide-react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import type { ScenarioRow, SimResult } from '@sih/types';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { fmtNum, fmtPct } from '@/lib/format';
import { BaselineBars, SensitivityChart, TornadoChart } from '@/components/charts';
import SaveToWorkspace from '@/components/SaveToWorkspace';
import { Badge, Button, Card, DemoBadge, ErrorState, LinkButton, LoginGate, Notice, Skeleton } from '@/components/ui';

interface RunResp { run_id: string; result: SimResult }
interface ScenarioDetail extends ScenarioRow { runs: { id: string; created_at: string }[] }
interface Compare { runs: { run_id: string; scenario: string; inputs: Record<string, number> }[]; outputs: { key: string; label: string; baseline: number; values: number[] }[]; note: string }

function Detail() {
  const { id } = useParams<{ id: string }>();
  const runParam = useSearchParams().get('run');
  const { role, loading } = useAuth();
  const [sc, setSc] = useState<ScenarioDetail | null>(null);
  const [run, setRun] = useState<RunResp | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [metric, setMetric] = useState('composite_impact_index');
  const [param, setParam] = useState('target_coverage');
  const [others, setOthers] = useState<ScenarioRow[]>([]);
  const [cmp, setCmp] = useState<Compare | null>(null);
  const [exportErr, setExportErr] = useState<string | null>(null);

  useEffect(() => {
    if (loading || !can.run(role)) return;
    (async () => {
      try {
        const s = await api<ScenarioDetail>(`/scenarios/${id}`); setSc(s);
        const rid = runParam ?? s.runs[0]?.id;
        if (rid) setRun(await api<RunResp>(`/scenarios/${id}/runs/${rid}`));
        setOthers((await api<ScenarioRow[]>('/scenarios')).filter((o) => o.id !== id && o.latest_run_id));
      } catch (e) { setErr(e); }
    })();
  }, [id, runParam, role, loading]);

  if (loading) return <Skeleton className="h-64" />;
  if (!can.run(role)) return <LoginGate what="Viewing scenarios" />;
  if (err) return <ErrorState error={err} />;
  if (!sc || !run) return <Skeleton className="h-96" />;
  const r = run.result;
  const compareWith = async (other: ScenarioRow) => setCmp(await api<Compare>(`/scenarios/compare?run_ids=${run.run_id},${other.latest_run_id}`));
  const exportMd = async () => {
    setExportErr(null);
    try { const e = await api<{ filename: string; content: string }>(`/scenarios/${id}/runs/${run.run_id}/export`);
      const url = URL.createObjectURL(new Blob([e.content], { type: 'text/markdown' })); const a = document.createElement('a'); a.href = url; a.download = e.filename; a.click(); URL.revokeObjectURL(url); }
    catch (e) { setExportErr(e instanceof Error ? e.message : 'Export failed'); }
  };
  const sens = r.sensitivity[param];
  const metricLabel = r.outputs.find((o) => o.key === metric)?.label ?? metric;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="label text-brand">Scenario result</p><h1 className="text-3xl font-semibold">{sc.name}</h1>
        <p className="mt-1 text-sm text-ink-500">{r.baseline_context.region?.name} · {r.model.name} <Badge>v{r.model.version}</Badge> <Badge tone={r.model.review_status === 'unreviewed' ? 'saffron' : 'brand'}>{r.model.review_status.replace(/_/g, ' ')}</Badge> {r.is_demo_calibration && <DemoBadge label="DEMO CALIBRATION" />}</p></div>
        <div className="flex flex-wrap gap-2"><SaveToWorkspace item={{ item_type: 'scenario', ref_id: sc.id, title: sc.name, payload: { scenario_id: sc.id, run_id: run.run_id, outputs: r.outputs, inputs: r.inputs, model_name: r.model.name, model_version: r.model.version, input_hash: r.hashes.input_hash, is_demo: true } }} />
          <LinkButton variant="secondary" href={`/simulation?region=${sc.region?.id ?? ''}`}>New scenario</LinkButton>
          {can.export(role) ? <Button variant="secondary" onClick={exportMd}><Download className="h-4 w-4" />Export report</Button> : <span title="Analyst, expert or admin role required" className="inline-flex cursor-not-allowed items-center gap-2 rounded-md border border-ink-100 px-4 py-2 text-sm text-ink-300"><Download className="h-4 w-4" />Export (analyst+)</span>}</div></div>
      {exportErr && <p role="alert" className="text-sm text-alert">{exportErr}</p>}
      <div role="note" className="rounded-md border-l-4 border-saffron bg-saffron-50 px-4 py-3 text-sm font-medium">⚠ {r.disclaimer}</div>

      <Card className="overflow-hidden"><div className="grid gap-0 lg:grid-cols-[1.4fr_1fr]">
        <div><h2 className="border-b border-ink-100 px-5 py-3 font-serif text-lg font-semibold">Baseline vs scenario</h2>
          <table className="w-full text-sm" data-testid="results-table"><thead className="bg-ink-50 text-left"><tr>{['Indicator', 'Baseline', 'Scenario', 'Change'].map((h) => <th key={h} className="label px-5 py-2">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-ink-100">{r.outputs.map((o) => (<tr key={o.key}><td className="px-5 py-3"><p className="font-medium">{o.label}</p><p className="text-xs text-ink-400">{o.unit}</p></td>
              <td className="px-5 py-3 tabular-nums">{fmtNum(o.baseline)}</td><td className="px-5 py-3 font-semibold tabular-nums">{fmtNum(o.scenario)}</td>
              <td className={`px-5 py-3 tabular-nums ${o.direction === 'improved' ? 'text-brand' : o.direction === 'worsened' ? 'text-alert' : 'text-ink-400'}`}>
                <span className="inline-flex items-center gap-1">{o.direction === 'improved' ? (o.delta < 0 ? <ArrowDown className="h-3.5 w-3.5" /> : <ArrowUp className="h-3.5 w-3.5" />) : o.direction === 'worsened' ? (o.delta < 0 ? <ArrowDown className="h-3.5 w-3.5" /> : <ArrowUp className="h-3.5 w-3.5" />) : <Minus className="h-3.5 w-3.5" />}{fmtPct(o.delta_pct)}</span>
                <span className="block text-[10px] uppercase">{o.direction}</span></td></tr>))}</tbody></table></div>
        <div className="border-l border-ink-100 p-4"><BaselineBars outputs={r.outputs} /></div></div></Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5"><h2 className="mb-1 font-serif text-lg font-semibold">Inputs</h2><p className="mb-3 text-xs text-ink-400">What was set for this run. Highlighted rows differ from the region baseline.</p>
          <table className="w-full text-sm"><tbody className="divide-y divide-ink-100">{r.inputs.map((i) => (<tr key={i.key} className={i.changed ? 'bg-saffron-50' : ''}><td className="py-2 pr-2">{i.label}</td><td className="py-2 text-right tabular-nums font-semibold">{fmtNum(i.value, 2)}</td><td className="py-2 pl-3 text-right text-xs text-ink-400">baseline {fmtNum(i.baseline_value, 2)}</td></tr>))}</tbody></table></Card>
        <Card className="p-5"><h2 className="mb-1 font-serif text-lg font-semibold">Baseline provenance</h2>
          <p className="text-xs text-ink-500">{r.baseline_context.note}</p>
          <ul className="mt-3 space-y-1 text-xs">{r.baseline_context.sources?.map((s) => <li key={s.indicator} className="flex flex-wrap items-center gap-2">{s.indicator} · {s.period} · {s.source}{s.is_demo && <DemoBadge />}</li>)}</ul>
          <p className="mt-3 break-all font-mono text-[10px] text-ink-300">input {r.hashes.input_hash}<br />output {r.hashes.output_hash}</p></Card></div>

      <Card className="p-5"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-serif text-lg font-semibold">Sensitivity: how much does this assumption matter?</h2>
        <p className="text-xs text-ink-400">Re-runs the model across the range of one input, holding others fixed. The orange dot is your chosen value.</p></div>
        <div className="flex gap-2"><Select2 label="Vary" value={param} onChange={setParam} options={Object.entries(r.sensitivity).map(([k, v]) => [k, v.label])} /><Select2 label="Output" value={metric} onChange={setMetric} options={r.outputs.map((o) => [o.key, o.label])} /></div></div>
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]"><SensitivityChart data={sens} metric={metric} metricLabel={metricLabel} />
          <div className="overflow-auto"><table className="w-full text-xs" data-testid="sensitivity-table"><thead><tr className="text-left"><th className="label py-1">{sens.label}</th><th className="label py-1 text-right">{metricLabel}</th></tr></thead>
            <tbody>{sens.points.map((p) => <tr key={p.value} className={p.value === sens.current ? 'bg-saffron-50 font-semibold' : ''}><td className="py-1 tabular-nums">{fmtNum(p.value, 2)} {sens.unit.split(' ')[0]}</td><td className="py-1 text-right tabular-nums">{fmtNum(p[metric] as number)}</td></tr>)}</tbody></table></div></div>
        <h3 className="mb-1 mt-6 text-sm font-semibold">Which input moves the composite index most? <span className="font-normal text-ink-400">(±10% of each input, one at a time)</span></h3><TornadoChart rows={r.tornado} /></Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5"><h2 className="mb-3 font-serif text-lg font-semibold">How it was calculated</h2>
          <ol className="space-y-1.5 text-sm">{r.equations.map((e) => <li key={e.output}><span className="text-ink-400">{e.output}:</span> <code className="rounded bg-ink-50 px-1.5 py-0.5 text-xs">{e.formula}</code></li>)}</ol>
          <p className="label mb-1 mt-4">With your numbers</p><ul className="space-y-1">{r.substituted.map((s) => <li key={s} className="break-words rounded bg-brand-50 px-2 py-1 font-mono text-[11px]">{s}</li>)}</ul></Card>
        <Card className="p-5"><h2 className="mb-3 font-serif text-lg font-semibold">Coefficients & provenance</h2>
          <ul className="space-y-2 text-xs">{Object.entries(r.coefficient_provenance).map(([k, v]) => <li key={k}><code className="font-semibold">{k} = {r.coefficients[k]}</code><p className="text-ink-500">{v}</p></li>)}</ul></Card></div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5"><h2 className="mb-2 font-serif text-lg font-semibold">Assumptions</h2><ul className="list-disc space-y-1 pl-5 text-sm">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Card>
        <Card className="border-saffron/40 p-5"><h2 className="mb-2 font-serif text-lg font-semibold">What this model does NOT prove</h2><ul className="list-disc space-y-1 pl-5 text-sm">{r.limitations.map((a) => <li key={a}>{a}</li>)}</ul></Card></div>

      <Card className="p-5"><h2 className="mb-1 font-serif text-lg font-semibold">Compare with another saved scenario</h2>
        {others.length === 0 ? <p className="text-sm text-ink-400">Run another scenario to compare it here.</p> : <div className="flex flex-wrap gap-2">{others.map((o) => <Button key={o.id} variant="secondary" size="sm" onClick={() => compareWith(o)}>{o.name} · target {o.parameters.target_coverage}%</Button>)}</div>}
        {cmp && <div className="mt-4 overflow-auto"><table className="w-full text-sm" data-testid="compare-table"><thead className="bg-ink-50 text-left"><tr><th className="label px-3 py-2">Indicator</th><th className="label px-3 py-2">Baseline</th>{cmp.runs.map((x) => <th key={x.run_id} className="label px-3 py-2">{x.scenario}</th>)}</tr></thead>
          <tbody className="divide-y divide-ink-100">{cmp.outputs.map((o) => <tr key={o.key}><td className="px-3 py-2">{o.label}</td><td className="px-3 py-2 tabular-nums text-ink-400">{fmtNum(o.baseline)}</td>{o.values.map((v, i) => <td key={i} className="px-3 py-2 font-semibold tabular-nums">{fmtNum(v)}</td>)}</tr>)}</tbody></table><p className="mt-2 text-xs text-ink-400">{cmp.note}</p></div>}</Card>
      <p className="text-xs text-ink-400">Related evidence: <Link className="text-brand underline" href="/research/results?q=How%20does%20implementation%20capacity%20affect%20the%20benefits%20of%20digitization%3F">capacity &amp; digitization benefits</Link> · <Link className="text-brand underline" href="/research/results?q=Does%20data%20quality%20affect%20digitization%20outcomes%3F">data quality</Link></p>
      <Notice tone="brand">Coverage of expansion beyond the calibrated 60-point range, or a target below current coverage, is rejected with an explicit error rather than extrapolated.</Notice>
    </div>);
}

function Select2({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[][] }) {
  return <label className="text-xs text-ink-500">{label}<select className="ml-1 rounded border border-ink-200 bg-white px-2 py-1 text-xs" value={value} onChange={(e) => onChange(e.target.value)}>{options.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>;
}
export default function ScenarioPage() { return <Suspense fallback={<Skeleton className="h-96" />}><Detail /></Suspense>; }

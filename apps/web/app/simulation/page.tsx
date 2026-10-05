'use client';
import { Play } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import type { RegionLite, ScenarioRow, SimModel } from '@sih/types';
import { ApiError, api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { fmtNum } from '@/lib/format';
import { Badge, Button, Card, DemoBadge, LoginGate, Notice, PageHeader, Select, Skeleton, Spinner } from '@/components/ui';

function Lab() {
  const sp = useSearchParams();
  const router = useRouter();
  const { role, loading } = useAuth();
  const [models, setModels] = useState<SimModel[]>([]);
  const [regions, setRegions] = useState<RegionLite[]>([]);
  const [regionId, setRegionId] = useState(sp.get('region') ?? '');
  const [vals, setVals] = useState<Record<string, number>>({});
  const [base, setBase] = useState<Record<string, number>>({});
  const [ctx, setCtx] = useState<{ note?: string; is_demo?: boolean; period?: number } | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<{ message: string; list: string[] } | null>(null);
  const [mine, setMine] = useState<ScenarioRow[]>([]);
  const model = models[0];

  useEffect(() => { api<SimModel[]>('/models').then(setModels).catch(() => {}); api<RegionLite[]>('/regions').then((r) => { setRegions(r); if (!regionId) { const ka = r.find((x) => x.level === 'state' && x.state_code === 'KA'); if (ka) setRegionId(ka.id); } }); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (can.run(role)) api<ScenarioRow[]>('/scenarios').then(setMine).catch(() => {}); }, [role]);
  useEffect(() => {
    if (!model || !regionId) return;
    api<{ values: Record<string, number>; context: typeof ctx }>(`/models/${model.id}/baseline?region_id=${regionId}`).then(({ values, context }) => {
      setBase(values); setCtx(context);
      const target = Math.min(100, Math.round(values.current_coverage) + 18);
      setVals({ ...values, target_coverage: target, implementation_capacity: model.parameters.find((p) => p.key === 'implementation_capacity')!.default, data_quality: model.parameters.find((p) => p.key === 'data_quality')!.default });
      setProblems(null);
    });
  }, [model, regionId]);

  if (loading) return <Skeleton className="h-64" />;
  if (!can.run(role)) return <div><PageHeader eyebrow="Policy Scenario Lab" title="Scenario Lab" sub="Explainable scenario modelling: baseline → assumptions → transparent formulas → outputs." /><LoginGate what="Running and saving scenarios" /></div>;
  if (!model) return <Spinner />;

  const region = regions.find((r) => r.id === regionId);
  const run = async () => {
    setBusy(true); setProblems(null);
    try {
      const sc = await api<{ id: string }>('/scenarios', { body: { model_id: model.id, region_id: regionId, name: name.trim() || `${region?.name}: ${vals.target_coverage}% digitization`, parameters: vals } });
      const r = await api<{ run_id: string }>(`/scenarios/${sc.id}/run`, { method: 'POST' });
      router.push(`/simulation/${sc.id}?run=${r.run_id}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'SIMULATION_OUT_OF_RANGE') setProblems({ message: e.message, list: e.details.problems ?? [] });
      else setProblems({ message: e instanceof Error ? e.message : 'Failed', list: [] });
    } finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Policy Scenario Lab" title="Scenario Lab" sub="Change a policy assumption and see the modelled effect on indexed indicators. Every step of the calculation is shown on the next screen." />
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><p className="label">Model</p><p className="font-serif text-lg font-semibold leading-tight">{model.name}</p></div><div className="flex gap-1.5"><Badge>v{model.version}</Badge><DemoBadge label="DEMO CALIBRATION" /></div></div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-ink-500">Region (baseline source)<Select className="mt-1 w-full" value={regionId} onChange={(e) => setRegionId(e.target.value)}>
              {regions.map((r) => <option key={r.id} value={r.id}>{r.level === 'state' ? `${r.name} (state mean)` : `${r.name}, ${r.state_code}`}</option>)}</Select></label>
            <label className="text-xs text-ink-500">Scenario name<input className="mt-1 w-full rounded-md border border-ink-200 px-2.5 py-1.5 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Karnataka 80% digitization" /></label></div>
          {ctx?.note && <p className="mt-3 text-xs text-ink-400">{ctx.note}</p>}
          <div className="mt-5 space-y-5">{model.parameters.map((p) => {
            const isBaseline = !!p.baseline_indicator; const v = vals[p.key] ?? p.default; const changed = base[p.key] !== undefined && Math.abs(v - base[p.key]) > 1e-9 && p.key !== 'target_coverage';
            return (<div key={p.key}><div className="flex items-baseline justify-between"><label htmlFor={p.key} className="text-sm font-medium">{p.label}{isBaseline && <span className="ml-2 text-[10px] font-normal uppercase text-ink-300">baseline</span>}</label>
              <span className="tabular-nums text-sm font-semibold text-brand">{fmtNum(v, 2)} <span className="text-xs font-normal text-ink-400">{p.unit.split(' ')[0]}</span></span></div>
              <input id={p.key} type="range" className="mt-1 w-full accent-brand" min={p.min} max={p.max} step={p.step} value={v} onChange={(e) => setVals({ ...vals, [p.key]: Number(e.target.value) })} />
              <p className="text-xs text-ink-400">{p.description}{base[p.key] !== undefined && isBaseline && <> Region baseline: <b>{fmtNum(base[p.key], 1)}</b>{changed && <span className="text-saffron"> · overridden</span>}</>}</p></div>);
          })}</div>
          {problems && <div role="alert" className="mt-5 rounded-md border border-alert/30 bg-alert-50 p-3 text-sm"><p className="font-medium text-alert">Scenario could not be calculated</p><p className="mt-1">{problems.message}</p>
            {problems.list.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-ink-700">{problems.list.map((x) => <li key={x}>{x}</li>)}</ul>}</div>}
          <div className="mt-6 flex items-center gap-3"><Button onClick={run} disabled={busy}><Play className="h-4 w-4" />{busy ? 'Running…' : 'Run scenario'}</Button>
            <span className="text-xs text-ink-400">Results are scenario estimates, not predictions.</span></div>
        </Card>
        <div className="space-y-4">
          <Notice>The model is a <strong>transparent normalized-index model</strong> with a synthetic demo calibration. It shows how assumptions propagate; it does not prove that digitization reduces disputes.</Notice>
          <Card className="p-4"><p className="label mb-2">Your saved scenarios</p>
            {mine.length === 0 ? <p className="text-sm text-ink-400">None yet. Run one to see it here.</p> : <ul className="divide-y divide-ink-100">{mine.slice(0, 6).map((s) => (<li key={s.id} className="py-2"><Link className="text-sm font-medium hover:text-brand hover:underline" href={`/simulation/${s.id}${s.latest_run_id ? `?run=${s.latest_run_id}` : ''}`}>{s.name}</Link>
              <p className="text-xs text-ink-400">{s.region?.name} · target {s.parameters.target_coverage}%</p></li>))}</ul>}</Card>
        </div>
      </div>
    </div>);
}
export default function SimulationPage() { return <Suspense fallback={<Skeleton className="h-96" />}><Lab /></Suspense>; }

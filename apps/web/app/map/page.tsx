'use client';
import { Lock } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo, useState } from 'react';
import type { IndicatorInfo, LayerCollection, RegionLite, RegionProfile } from '@sih/types';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { STATE_NAME, fmtNum } from '@/lib/format';
import { legendSteps } from '@/lib/mapColors';
import { Trend } from '@/components/charts';
import { Badge, Card, DemoBadge, ErrorState, LinkButton, Notice, PageHeader, Select, Skeleton } from '@/components/ui';
import SaveToWorkspace from '@/components/SaveToWorkspace';

const MapView = dynamic(() => import('@/components/MapView'), { ssr: false, loading: () => <Skeleton className="h-[520px]" /> });
const CATEGORY: Record<string, string> = { governance: 'Governance', climate: 'Climate vulnerability', land_use: 'Land use' };

function MapExplorer() {
  const sp = useSearchParams();
  const { role } = useAuth();
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([]);
  const [regions, setRegions] = useState<RegionLite[]>([]);
  const [indKey, setIndKey] = useState(sp.get('indicator') ?? 'digitization_coverage');
  const [stateCode, setStateCode] = useState<string>(sp.get('state') ?? '');
  const [period, setPeriod] = useState<number | null>(null);
  const [showTiles, setShowTiles] = useState(true);
  const [showStates, setShowStates] = useState(true);
  const [layer, setLayer] = useState<LayerCollection | null>(null);
  const [outlines, setOutlines] = useState<unknown>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [profile, setProfile] = useState<RegionProfile | null>(null);
  const [err, setErr] = useState<unknown>(null);

  useEffect(() => { api<IndicatorInfo[]>('/indicators').then(setIndicators).catch(setErr); api<RegionLite[]>('/regions').then(setRegions).catch(setErr); api('/gis/boundaries?level=state').then(setOutlines).catch(() => {}); }, [role]);
  useEffect(() => {
    setErr(null);
    api<LayerCollection>(`/gis/layers/${indKey}?${period ? `period=${period}&` : ''}${stateCode ? `state=${stateCode}` : ''}`).then(setLayer).catch((e) => { setLayer(null); setErr(e); });
  }, [indKey, period, stateCode, role]);
  useEffect(() => { if (!sel) { setProfile(null); return; } api<RegionProfile>(`/regions/${sel}`).then(setProfile).catch(setErr); }, [sel, role]);

  const ind = indicators.find((i) => i.key === indKey);
  const districts = useMemo(() => regions.filter((r) => r.level === 'district' && (!stateCode || r.state_code === stateCode)), [regions, stateCode]);
  const grouped = useMemo(() => Object.entries(CATEGORY).map(([k, label]) => [label, indicators.filter((i) => i.category === k)] as const), [indicators]);
  const prof = profile;

  return (
    <div>
      <PageHeader eyebrow="Spatial Intelligence" title="Map Explorer" sub="Choropleth of district-level indicators. Every layer exposes its source; boundaries are schematic tiles, not official geometry." />
      <div className="grid gap-4 lg:grid-cols-[260px_1fr_320px]">
        <aside className="space-y-4">
          <Card className="space-y-3 p-4">
            <label className="block text-xs text-ink-500">Indicator layer
              <Select className="mt-1 w-full" value={indKey} onChange={(e) => setIndKey(e.target.value)}>
                {grouped.map(([label, items]) => <optgroup key={label} label={label}>{items.map((i) => <option key={i.key} value={i.key}>{i.locked ? '🔒 ' : ''}{i.name}</option>)}</optgroup>)}</Select></label>
            <label className="block text-xs text-ink-500">State<Select className="mt-1 w-full" value={stateCode} onChange={(e) => { setStateCode(e.target.value); setSel(null); }}>
              <option value="">All demo states</option>{Object.entries(STATE_NAME).map(([c, n]) => <option key={c} value={c}>{n}</option>)}</Select></label>
            <label className="block text-xs text-ink-500">District<Select className="mt-1 w-full" value={sel && districts.some((d) => d.id === sel) ? sel : ''} onChange={(e) => setSel(e.target.value || null)}>
              <option value="">Select district…</option>{districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></label>
            {layer && <label className="block text-xs text-ink-500">Year: <b>{layer.meta.period}</b>
              <input type="range" className="mt-1 w-full accent-brand" min={layer.meta.periods[0]} max={layer.meta.periods[layer.meta.periods.length - 1]} step={1} value={layer.meta.period} onChange={(e) => setPeriod(Number(e.target.value))} aria-label="Year" /></label>}
            <fieldset className="space-y-1 text-sm"><legend className="label mb-1">Layers</legend>
              <label className="flex items-center gap-2"><input type="checkbox" checked={showTiles} onChange={(e) => setShowTiles(e.target.checked)} className="accent-brand" />District indicator tiles</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={showStates} onChange={(e) => setShowStates(e.target.checked)} className="accent-brand" />State outlines (schematic)</label></fieldset>
          </Card>
          {layer && ind && <Card className="p-4"><p className="label mb-2">Legend · {ind.unit}</p>
            <div className="flex">{legendSteps(ind.legend, ind.higher_is_better).map((s) => <div key={s.color} className="flex-1"><div className="h-3" style={{ background: s.color }} /><p className="mt-0.5 text-center text-[10px] tabular-nums text-ink-400">{Math.round(s.from * 10) / 10}</p></div>)}</div>
            <p className="mt-1 text-[11px] text-ink-400">{ind.higher_is_better ? 'Higher is better' : 'Higher = more pressure/vulnerability'} · gray = no data</p></Card>}
        </aside>

        <section className="relative min-h-[520px]">
          {err ? <ErrorState error={err} /> : null}
          {!err && <div className="h-[560px] overflow-hidden rounded-lg border border-ink-100"><MapView layer={showTiles ? layer : null} stateOutlines={showStates ? outlines : null} selectedId={sel} onSelect={setSel} focusState={stateCode || null} /></div>}
          <p className="mt-2 text-[11px] text-ink-400">{layer?.meta.geometry_note}</p>
        </section>

        <aside className="space-y-4">
          {ind && <Card className="p-4"><div className="mb-1 flex items-start justify-between gap-2"><p className="font-serif text-lg font-semibold leading-tight">{ind.name}</p>{ind.demo_label && <DemoBadge label="DEMO / SYNTHETIC" />}</div>
            <p className="text-xs text-ink-500">{ind.description}</p>
            {ind.source && <p className="mt-2 text-xs text-ink-400"><b>Source:</b> {ind.source.name}. {ind.source.description}</p>}
            {ind.locked && <div className="mt-2"><Notice tone="alert"><Lock className="mr-1 inline h-3 w-3" />Protected dataset — analyst, expert or admin only.</Notice></div>}</Card>}
          {prof ? (<Card className="p-4"><div className="flex items-start justify-between"><div><p className="label">{prof.region.level} profile</p><h3 className="text-xl font-semibold">{prof.region.name}</h3></div><Badge>{prof.region.state_code}</Badge></div>
            <ul className="mt-3 divide-y divide-ink-100">{prof.indicators.slice(0, 5).map((i) => (<li key={i.key} className="flex items-center justify-between gap-2 py-2"><div className="min-w-0"><p className="truncate text-xs text-ink-500">{i.name}</p>
              <p className="tabular-nums text-sm font-semibold">{i.locked ? <Lock className="inline h-3 w-3 text-ink-300" /> : fmtNum(i.latest?.value)} <span className="text-xs font-normal text-ink-400">{i.locked ? '' : i.unit.split(' ')[0]}</span></p></div>
              {!i.locked && <Trend series={i.series} good={i.trend?.favourable} />}</li>))}</ul>
            <div className="mt-3 flex flex-wrap gap-2"><LinkButton variant="secondary" href={`/map/region/${prof.region.id}`}>Full profile</LinkButton>
              {prof.scenario_shortcut && <LinkButton href={`/simulation?region=${prof.region.id}`}>Run scenario</LinkButton>}
              <SaveToWorkspace size="sm" label="Save map view" item={{ item_type: 'map', ref_id: `${indKey}:${prof.region.id}:${layer?.meta.period}`, title: `${ind?.name ?? indKey} — ${prof.region.name}`, payload: { indicator: indKey, region_id: prof.region.id, region: prof.region.name, period: layer?.meta.period, is_demo: true } }} /></div>
          </Card>) : <Card className="p-4 text-sm text-ink-500">Click a tile to open its region profile.</Card>}
          <p className="text-xs text-ink-400">Need the governance context? <Link className="text-brand underline" href="/research">Search the evidence</Link>.</p>
        </aside>
      </div>
    </div>);
}
export default function MapPage() { return <Suspense fallback={<Skeleton className="h-96" />}><MapExplorer /></Suspense>; }

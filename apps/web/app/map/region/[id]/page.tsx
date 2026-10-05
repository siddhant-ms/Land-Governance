'use client';
import { Lock } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { RegionProfile } from '@sih/types';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { DOC_TYPE_LABEL, fmtNum } from '@/lib/format';
import { Trend } from '@/components/charts';
import { Badge, Card, DemoBadge, ErrorState, LinkButton, Notice, PageHeader, Skeleton } from '@/components/ui';

export default function RegionPage() {
  const { id } = useParams<{ id: string }>();
  const { role } = useAuth();
  const [p, setP] = useState<RegionProfile | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api<RegionProfile>(`/regions/${id}`).then(setP).catch(setErr); }, [id, role]);
  if (err) return <ErrorState error={err} />;
  if (!p) return <Skeleton className="h-96" />;
  const docs = [...p.documents, ...p.research];
  return (
    <div>
      <PageHeader eyebrow={`${p.region.level} profile · ${p.region.state_code}`} title={p.region.name}
        sub={p.region.parent ? <>Part of <Link className="text-brand underline" href={`/map/region/${p.region.parent.id}`}>{p.region.parent.name}</Link>. {p.region.geometry_note}</> : `${p.region.n_districts} demo districts. ${p.aggregation_note ?? ''}`}
        actions={<div className="flex gap-2"><LinkButton variant="secondary" href={`/map?state=${p.region.state_code}`}>Back to map</LinkButton>{p.scenario_shortcut && <LinkButton href={`/simulation?region=${p.region.id}`}>Run scenario for {p.region.name}</LinkButton>}</div>} />
      <Notice>All indicator values below are <strong>DEMO / SYNTHETIC DATA</strong> generated for the prototype.</Notice>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="overflow-hidden"><table className="w-full text-sm"><thead className="bg-ink-50 text-left"><tr>{['Indicator', 'Latest', 'Trend', 'Source'].map((h) => <th key={h} className="label px-4 py-2">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-ink-100">{p.indicators.map((i) => (<tr key={i.key}><td className="px-4 py-3"><p className="font-medium">{i.name}</p><p className="text-xs text-ink-400">{i.unit}</p></td>
            <td className="px-4 py-3 tabular-nums">{i.locked ? <span className="inline-flex items-center gap-1 text-xs text-saffron"><Lock className="h-3 w-3" />Restricted</span> : <><span className="text-lg font-semibold">{fmtNum(i.latest?.value)}</span> <span className="text-xs text-ink-400">{i.latest?.period}</span></>}</td>
            <td className="px-4 py-3">{i.locked ? '—' : <div className="flex items-center gap-2"><Trend series={i.series} good={i.trend?.favourable} /><span className="text-xs tabular-nums text-ink-500">{i.trend ? `${i.trend.change > 0 ? '+' : ''}${fmtNum(i.trend.change)} since ${i.trend.from}` : ''}</span></div>}</td>
            <td className="px-4 py-3 text-xs text-ink-500">{i.source?.name}{i.is_demo && <div className="mt-1"><DemoBadge /></div>}</td></tr>))}</tbody></table></Card>
        <div className="space-y-4">
          <Card className="p-4"><h2 className="mb-3 font-serif text-lg font-semibold">Relevant documents & research</h2>
            {docs.length === 0 ? <p className="text-sm text-ink-400">No documents tagged to this region.</p> : <ul className="space-y-3">{docs.map((d) => (<li key={d.document_id}><Link prefetch={false} className="text-sm font-medium leading-snug hover:text-brand hover:underline" href={`/research/document/${d.document_id}`}>{d.title}</Link>
              <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-400">{DOC_TYPE_LABEL[d.document_type]} · {d.year}{d.state_code === p.region.state_code ? <Badge tone="brand">{d.state_code}</Badge> : <Badge>National</Badge>}{d.is_demo && <DemoBadge />}</p></li>))}</ul>}
            <Link className="mt-3 inline-block text-sm text-brand underline" href={`/research/results?q=${encodeURIComponent(`land records digitization disputes ${p.region.name}`)}&state=${p.region.state_code}`}>Ask the research assistant about {p.region.name}</Link></Card>
          {p.scenario_shortcut && <Card className="bg-brand-50 p-4"><h2 className="font-serif text-lg font-semibold">Scenario shortcut</h2><p className="mt-1 text-sm text-ink-500">Baseline digitization coverage for {p.region.name}: <b>{fmtNum(p.scenario_shortcut.baseline_coverage)}%</b> (demo). Explore what changes if coverage expands.</p>
            <div className="mt-3"><LinkButton href={`/simulation?region=${p.region.id}`}>Open Scenario Lab</LinkButton></div></Card>}
        </div>
      </div>
    </div>);
}

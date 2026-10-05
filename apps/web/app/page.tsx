'use client';
import { ArrowRight, Map as MapIcon, Search, SlidersHorizontal } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { Dashboard } from '@sih/types';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { DOC_TYPE_LABEL } from '@/lib/format';
import { StateBars } from '@/components/charts';
import { Card, DemoBadge, ErrorState, Notice, Skeleton, Stat } from '@/components/ui';

const EXAMPLE = 'What evidence exists on land-record digitization and land-dispute outcomes in India?';

export default function Home() {
  const router = useRouter();
  const { user } = useAuth();
  const [q, setQ] = useState('');
  const [data, setData] = useState<Dashboard | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api<Dashboard>('/dashboard').then(setData).catch(setErr); }, [user]);
  const go = (text: string) => text.trim().length >= 5 && router.push(`/research/results?q=${encodeURIComponent(text.trim())}`);

  return (
    <div className="space-y-8">
      <section className="rounded-xl bg-ink px-6 py-10 text-white sm:px-10">
        <p className="label !text-brand-100">Research question</p>
        <h1 className="mt-2 max-w-3xl text-4xl font-semibold leading-tight">Land-governance answers you can <span className="text-brand-100">trace to the page</span>.</h1>
        <form className="mt-6 flex max-w-3xl flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); go(q); }}>
          <input aria-label="Research question" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask anything about land governance…"
            className="min-w-0 flex-1 rounded-md border border-white/20 bg-white/10 px-4 py-3 text-base text-white placeholder:text-white/50 focus:bg-white/15" />
          <button className="rounded-md bg-brand px-5 py-3 font-medium hover:bg-brand-600">Search evidence</button>
        </form>
        <button onClick={() => go(EXAMPLE)} className="mt-3 text-left text-sm text-brand-100 underline-offset-2 hover:underline">Try: “{EXAMPLE}”</button>
        <div className="mt-6 flex flex-wrap gap-2">
          {[{ href: '/research', icon: Search, t: 'Search Evidence' }, { href: '/map', icon: MapIcon, t: 'Explore Map' }, { href: '/simulation', icon: SlidersHorizontal, t: 'Run Scenario' }].map(({ href, icon: I, t }) => (
            <Link key={href} href={href} className="inline-flex items-center gap-2 rounded-md border border-white/25 px-4 py-2 text-sm hover:bg-white/10"><I className="h-4 w-4" />{t}</Link>))}
        </div>
      </section>

      {err ? <ErrorState error={err} /> : !data ? <Skeleton className="h-40" /> : (<>
        {data.corpus_notice && <Notice>{data.corpus_notice}</Notice>}
        <Card className="grid grid-cols-2 gap-6 p-6 sm:grid-cols-4">
          <Stat value={data.counts.documents} label="Documents in corpus" hint={`${data.counts.passages} citable passages`} />
          <Stat value={data.counts.datasets} label="Indicator datasets" hint={`${data.counts.observations.toLocaleString('en-IN')} observations`} />
          <Stat value={data.counts.case_studies} label="Case studies" /><Stat value={data.counts.research_papers} label="Research papers" />
        </Card>
        <div className="grid gap-6 lg:grid-cols-3">
          {data.featured_indicators.map((f) => (
            <Card key={f.key} className="p-5"><div className="mb-2 flex items-start justify-between gap-2"><div><p className="label">Featured indicator · {f.period}</p><h3 className="text-lg font-semibold">{f.name}</h3></div><DemoBadge label="DEMO / SYNTHETIC" /></div>
              <StateBars rows={f.by_state.map((s) => ({ state: s.state, value: s.value }))} unit={f.unit} />
              <Link href={`/map?indicator=${f.key}`} className="mt-2 inline-flex items-center gap-1 text-sm text-brand hover:underline">View on map <ArrowRight className="h-3.5 w-3.5" /></Link></Card>))}
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="p-5 lg:col-span-1"><h3 className="mb-3 font-serif text-lg font-semibold">Map preview</h3>
            <Link href="/map" className="block rounded-lg border border-ink-100 bg-brand-50 p-4 text-sm text-ink-500 hover:bg-brand-100">Interactive schematic map of {data.counts.regions} demo regions across 4 states. <span className="mt-2 block text-brand">Open Map Explorer →</span></Link></Card>
          <Card className="p-5"><h3 className="mb-3 font-serif text-lg font-semibold">Recent research</h3>
            <ul className="space-y-3">{data.recent_documents.map((d) => (<li key={d.id}><Link prefetch={false} href={`/research/document/${d.id}`} className="text-sm font-medium leading-snug hover:text-brand hover:underline">{d.title}</Link>
              <p className="mt-0.5 flex items-center gap-2 text-xs text-ink-400">{DOC_TYPE_LABEL[d.document_type]} · {d.year}{d.is_demo && <DemoBadge />}</p></li>))}</ul></Card>
          <Card className="p-5"><h3 className="mb-3 font-serif text-lg font-semibold">{user ? 'Your recent scenarios' : 'Recent scenarios'}</h3>
            {user ? (data.recent_scenarios.length ? <ul className="space-y-2">{data.recent_scenarios.map((s) => <li key={s.id}><Link className="text-sm hover:text-brand hover:underline" href={`/simulation/${s.id}${s.run_id ? `?run=${s.run_id}` : ''}`}>{s.name}</Link></li>)}</ul> : <p className="text-sm text-ink-400">None yet — <Link className="text-brand underline" href="/simulation">run one</Link>.</p>)
              : <p className="text-sm text-ink-500"><Link className="text-brand underline" href="/login">Sign in</Link> to run and save scenarios. Demo accounts are on the sign-in page.</p>}
            {user && data.recent_workspaces.length > 0 && <><h4 className="label mb-2 mt-5">Workspaces</h4><ul className="space-y-2">{data.recent_workspaces.map((w) => <li key={w.id}><Link className="text-sm hover:text-brand hover:underline" href={`/workspace/${w.id}`}>{w.title}</Link> <span className="text-xs text-ink-400">{w.items} items</span></li>)}</ul></>}</Card>
        </div>
      </>)}
    </div>);
}

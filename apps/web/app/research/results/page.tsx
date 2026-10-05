'use client';
import { Search } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import type { AskResponse, Filters, SearchResponse } from '@sih/types';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { DOC_TYPE_LABEL, STATE_NAME, fmtDate } from '@/lib/format';
import { AnswerView, SourcePanel } from '@/components/citations';
import SaveToWorkspace from '@/components/SaveToWorkspace';
import { Badge, Card, DemoBadge, EmptyState, ErrorState, Select, Skeleton } from '@/components/ui';

interface Facets { states: string[]; organizations: string[]; document_types: string[]; source_types: string[]; topics: string[]; year_range: [number, number] | null }

function ResultsInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();
  const q = sp.get('q') ?? '';
  const filters: Filters = useMemo(() => ({
    states: sp.getAll('state'), document_types: sp.getAll('type'), topics: sp.getAll('topic'), organizations: sp.getAll('org'),
    ...(sp.get('from') ? { date_from: `${sp.get('from')}-01-01` } : {}),
  }), [sp]);
  const [text, setText] = useState(q);
  const [ask, setAsk] = useState<AskResponse | null>(null);
  const [search, setSearch] = useState<SearchResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => { setText(q); }, [q]);
  useEffect(() => { api<Facets>('/search/facets').then(setFacets).catch(() => {}); }, [user]);
  const run = useCallback(() => {
    if (!q) return;
    setAsk(null); setSearch(null); setErr(null); setActive(null);
    Promise.all([api<AskResponse>('/research/ask', { body: { question: q, filters } }), api<SearchResponse>('/search', { body: { query: q, filters, top_k: 10 } })])
      .then(([a, s]) => { setAsk(a); setSearch(s); }).catch(setErr);
  }, [q, filters]);
  useEffect(run, [run]);

  const setParam = (key: string, value: string | null) => {
    const p = new URLSearchParams(sp.toString()); p.delete(key); if (value) p.set(key, value); router.push(`/research/results?${p.toString()}`);
  };
  const source = ask?.sources.find((s) => s.number === active) ?? null;
  const hasFilters = Object.values(filters).some((v) => (Array.isArray(v) ? v.length : !!v));

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      <aside aria-label="Filters" className="space-y-4 lg:sticky lg:top-4 lg:self-start">
        <p className="label">Filters</p>
        <FilterSelect label="State" value={sp.get('state')} options={(facets?.states ?? []).map((s) => [s, STATE_NAME[s] ?? s])} onChange={(v) => setParam('state', v)} />
        <FilterSelect label="Document type" value={sp.get('type')} options={(facets?.document_types ?? []).map((s) => [s, DOC_TYPE_LABEL[s] ?? s])} onChange={(v) => setParam('type', v)} />
        <FilterSelect label="Topic" value={sp.get('topic')} options={(facets?.topics ?? []).map((s) => [s, s])} onChange={(v) => setParam('topic', v)} />
        <FilterSelect label="Organization" value={sp.get('org')} options={(facets?.organizations ?? []).map((s) => [s, s])} onChange={(v) => setParam('org', v)} />
        {facets?.year_range && <FilterSelect label="Published from" value={sp.get('from')} options={Array.from({ length: facets.year_range[1] - facets.year_range[0] + 1 }, (_, i) => String(facets.year_range![0] + i)).map((y) => [y, y])} onChange={(v) => setParam('from', v)} />}
        {hasFilters && <Link className="text-xs text-brand underline" href={`/research/results?q=${encodeURIComponent(q)}`}>Clear all filters</Link>}
      </aside>

      <div className="min-w-0 space-y-6">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); const p = new URLSearchParams(sp.toString()); p.set('q', text); router.push(`/research/results?${p}`); }}>
          <input aria-label="Research question" value={text} onChange={(e) => setText(e.target.value)} className="min-w-0 flex-1 rounded-md border border-ink-200 bg-white px-4 py-2.5 shadow-card" />
          <button aria-label="Search" className="rounded-md bg-brand px-4 text-white hover:bg-brand-700"><Search className="h-4 w-4" /></button></form>

        {err ? <ErrorState error={err} onRetry={run} /> : !ask || !search ? (<div className="space-y-3"><Skeleton className="h-48" /><Skeleton className="h-24" /></div>) : (<>
          <AnswerView ask={ask} activeN={active} onOpen={setActive} />
          {ask.sources.length > 0 && <div className="flex flex-wrap items-center gap-2">
            <SaveToWorkspace label="Save answer & citations" item={{ item_type: 'answer', title: q, payload: { question: q, claims: ask.claims, sources: ask.sources.map((s) => ({ number: s.number, title: s.title, chunk_id: s.chunk_id })) } }} />
            <SaveToWorkspace label="Save search" item={{ item_type: 'search', title: q, payload: { query: q, filters } }} /></div>}

          <section aria-labelledby="ret-h"><div className="mb-3 flex flex-wrap items-baseline justify-between gap-2"><h2 id="ret-h" className="font-serif text-xl font-semibold">Retrieved evidence <span className="text-base font-normal text-ink-400">({search.results.length} documents)</span></h2>
            <p className="text-xs text-ink-400">{search.candidates_considered} passages considered · {search.timings_ms.total} ms{search.cached ? ' · cached' : ''}</p></div>
            {search.query_analysis.expansions.length > 0 && <p className="mb-3 text-xs text-ink-500">Query expanded with related terms: {search.query_analysis.expansions.slice(0, 6).map((t) => <Badge key={t} className="mx-0.5">{t}</Badge>)}</p>}
            {search.results.length === 0 ? <EmptyState title="No sufficiently relevant evidence was found">{search.empty_message}</EmptyState> : (
              <ul className="space-y-3">{search.results.map((r) => (
                <li key={r.document_id}><Card className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <Link prefetch={false} href={`/research/document/${r.document_id}?chunk=${r.passages[0].chunk_id}`} className="font-serif text-lg font-semibold leading-snug hover:text-brand hover:underline">{r.title}</Link>
                    <div className="flex items-center gap-1.5">{r.is_demo && <DemoBadge />}{r.access_level !== 'public' && <Badge tone="alert">{r.access_level}</Badge>}</div></div>
                  <p className="mt-1 text-xs text-ink-400">{r.organization} · {fmtDate(r.publication_date)} · {DOC_TYPE_LABEL[r.document_type]} · {r.geography}</p>
                  <p className="mt-2 text-sm leading-relaxed text-ink-700"><Snippet text={r.passages[0].snippet} terms={r.why_matched.matched_terms} /></p>
                  <details className="mt-2 text-xs text-ink-500"><summary className="cursor-pointer select-none text-brand">Why this matched</summary>
                    <p className="mt-1">Matched terms: {r.why_matched.matched_terms.join(', ') || 'semantic/concept match'} · p.{r.passages[0].page} · {r.passages[0].section}</p>
                    <p>BM25 rank {r.why_matched.explain.rank_lexical ?? '—'} · dense rank {r.why_matched.explain.rank_dense ?? '—'} · RRF {r.why_matched.explain.rrf} · relevance {r.relevance}</p></details>
                </Card></li>))}</ul>)}
          </section>
          {ask.suggested_followups.length > 0 && !ask.evidence_gap && <div className="text-sm"><p className="label mb-1">Follow-up questions</p><ul className="space-y-1">{ask.suggested_followups.map((f) => <li key={f}><Link className="text-brand hover:underline" href={`/research/results?q=${encodeURIComponent(f)}`}>{f}</Link></li>)}</ul></div>}
        </>)}
      </div>
      <SourcePanel source={source} onClose={() => setActive(null)} />
    </div>);
}

function Snippet({ text, terms }: { text: string; terms: string[] }) {
  if (!terms.length) return <>{text}</>;
  const re = new RegExp(`\\b(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`, 'gi');
  return <>{text.split(re).map((p, i) => (i % 2 ? <mark key={i} className="hl">{p}</mark> : <span key={i}>{p}</span>))}</>;
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string | null; options: string[][]; onChange: (v: string | null) => void }) {
  return (<label className="block text-xs text-ink-500">{label}
    <Select className="mt-1 w-full" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}><option value="">All</option>{options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></label>);
}

export default function ResultsPage() { return <Suspense fallback={<Skeleton className="h-64" />}><ResultsInner /></Suspense>; }

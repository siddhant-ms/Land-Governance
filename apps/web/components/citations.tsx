'use client';
import clsx from 'clsx';
import { ExternalLink, FileText, X } from 'lucide-react';
import Link from 'next/link';
import { useEffect } from 'react';
import type { AskResponse, Explain, Source } from '@sih/types';
import { DOC_TYPE_LABEL, fmtDate } from '@/lib/format';
import { Badge, Button, DemoBadge, Notice } from './ui';
import SaveToWorkspace from './SaveToWorkspace';

export function CitationChip({ n, active, onClick }: { n: number; active?: boolean; onClick: (n: number) => void }) {
  return <button type="button" onClick={() => onClick(n)} aria-label={`Open source ${n}`} aria-pressed={!!active}
    className={clsx('mx-0.5 inline-flex h-5 min-w-[1.4rem] -translate-y-0.5 items-center justify-center rounded border px-1 align-baseline text-[11px] font-semibold tabular-nums transition',
      active ? 'border-brand bg-brand text-white' : 'border-brand/40 bg-brand-50 text-brand hover:bg-brand-100')}>{n}</button>;
}

/** Renders passage text with the supporting span(s) highlighted. Ranges are validated and merged defensively. */
export function HighlightedPassage({ text, ranges, terms = [] }: { text: string; ranges: [number, number][]; terms?: string[] }) {
  const valid = ranges.filter(([a, b]) => a >= 0 && b > a && b <= text.length).sort((x, y) => x[0] - y[0]);
  const merged: [number, number][] = [];
  for (const r of valid) { const last = merged[merged.length - 1]; if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push([r[0], r[1]]); }
  const parts: React.ReactNode[] = []; let i = 0;
  merged.forEach(([a, b], k) => { if (a > i) parts.push(<span key={`t${k}`}>{text.slice(i, a)}</span>); parts.push(<mark key={`m${k}`} className="hl" data-testid="supporting-span">{text.slice(a, b)}</mark>); i = b; });
  if (i < text.length) parts.push(<span key="end">{text.slice(i)}</span>);
  void terms;
  return <p className="font-serif text-[15px] leading-relaxed text-ink-700">{parts}</p>;
}

function ExplainRow({ e }: { e: Explain }) {
  const cells: [string, string][] = [['BM25 rank', e.rank_lexical ? `#${e.rank_lexical}` : '—'], ['Dense rank', e.rank_dense ? `#${e.rank_dense}` : '—'], ['RRF', e.rrf.toFixed(4)], ['Term coverage', `${Math.round(e.query_coverage * 100)}%`]];
  return <dl className="grid grid-cols-4 gap-2 text-xs">{cells.map(([k, v]) => <div key={k}><dt className="label !text-[10px]">{k}</dt><dd className="tabular-nums">{v}</dd></div>)}</dl>;
}

export function SourcePanel({ source, onClose }: { source: Source | null; onClose: () => void }) {
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [onClose]);
  if (!source) return null;
  const s = source;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/30 animate-fade" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label={`Source ${s.number}`} onClick={(e) => e.stopPropagation()}
        className="h-full w-full max-w-md overflow-y-auto border-l border-ink-100 bg-white p-5 shadow-2xl animate-slide">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2"><span className="flex h-6 min-w-6 items-center justify-center rounded bg-brand px-1.5 text-xs font-bold text-white">{s.number}</span><span className="label">Evidence source</span></div>
          <button aria-label="Close source panel" onClick={onClose} className="rounded p-1 hover:bg-ink-100"><X className="h-4 w-4" /></button></div>
        <dl className="space-y-3 text-sm">
          <div><dt className="label">Source</dt><dd className="flex flex-wrap items-center gap-2 font-medium">{s.organization}{s.is_demo ? <DemoBadge label="DEMO SOURCE" /> : <Badge tone="brand">Official</Badge>}</dd></div>
          <div><dt className="label">Document</dt><dd className="font-serif text-lg leading-snug">{s.title}</dd></div>
          <div className="grid grid-cols-3 gap-3">
            <div><dt className="label">Date</dt><dd>{fmtDate(s.publication_date)}</dd></div>
            <div><dt className="label">Page</dt><dd>{s.page}</dd></div>
            <div><dt className="label">Type</dt><dd>{DOC_TYPE_LABEL[s.document_type] ?? s.document_type}</dd></div></div>
          <div><dt className="label">Section</dt><dd>{s.section || '—'}</dd></div>
          <div><dt className="label mb-1">Supporting passage</dt>
            <dd className="rounded-md border-l-4 border-brand bg-paper p-3"><HighlightedPassage text={s.passage} ranges={s.highlights} /></dd>
            <p className="mt-1 text-[11px] text-ink-400">Highlighted text is the sentence the cited claim is checked against.</p></div>
          <div><dt className="label">Source URL</dt><dd className="break-all">{s.source_url && !s.source_url.includes('example.org')
            ? <a href={s.source_url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-brand underline">{s.source_url}<ExternalLink className="h-3 w-3" /></a>
            : <span className="text-ink-400">No public URL — demo document</span>}</dd></div>
          <div><dt className="label mb-1">Retrieval relevance</dt>
            <dd><div className="mb-2 flex items-center gap-2"><div className="h-2 flex-1 overflow-hidden rounded bg-ink-100"><div className="h-full bg-brand" style={{ width: `${Math.min(100, Math.round(s.relevance * 100 * 1.4))}%` }} /></div>
              <span className="text-xs tabular-nums">{s.relevance.toFixed(2)}</span></div><ExplainRow e={s.explain} /></dd></div></dl>
        {s.is_demo && <div className="mt-4"><Notice>This passage comes from the <strong>demo corpus</strong>, authored to exercise the platform. Do not cite it as real evidence.</Notice></div>}
        <div className="mt-5 flex flex-wrap gap-2">
          <Link prefetch={false} href={`/research/document/${s.document_id}?chunk=${s.chunk_id}`} className="inline-flex items-center gap-2 rounded-md bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700"><FileText className="h-3.5 w-3.5" />Open in document</Link>
          <SaveToWorkspace size="sm" item={{ item_type: 'citation', ref_id: s.chunk_id, title: s.title, payload: { title: s.title, organization: s.organization, publication_date: s.publication_date, page: s.page, section: s.section, passage: s.passage, source_url: s.source_url, is_demo: s.is_demo, document_id: s.document_id, chunk_id: s.chunk_id } }} />
        </div>
      </aside>
    </div>);
}

const STRENGTH: Record<AskResponse['evidence_strength'], { label: string; tone: 'brand' | 'saffron' | 'alert' | 'neutral' }> = {
  strong: { label: 'Strong: 3+ documents, well supported', tone: 'brand' }, moderate: { label: 'Moderate: 2 documents', tone: 'saffron' },
  weak: { label: 'Weak: single document', tone: 'alert' }, none: { label: 'No evidence', tone: 'neutral' },
};

export function AnswerView({ ask, activeN, onOpen }: { ask: AskResponse; activeN: number | null; onOpen: (n: number) => void }) {
  if (ask.ai_status === 'failed') {
    return <div role="alert" className="card border-saffron/40 bg-saffron-50 p-5"><p className="font-serif text-lg">AI synthesis unavailable</p>
      <p className="mt-1 text-sm text-ink-700">{ask.ai_message}</p></div>;
  }
  if (ask.evidence_gap) {
    return (<div className="card border-saffron/40 p-5" data-testid="evidence-gap"><p className="label text-saffron">Evidence gap</p>
      <p className="mt-1 font-serif text-xl">{ask.evidence_gap_message}</p>
      <p className="mt-2 text-sm text-ink-500">The platform declines to answer rather than guess. {ask.limitations[0]}</p>
      <ul className="mt-3 list-disc pl-5 text-sm text-ink-500">{ask.suggested_followups.map((f) => <li key={f}>{f}</li>)}</ul></div>);
  }
  const st = STRENGTH[ask.evidence_strength];
  return (
    <div className="card divide-y divide-ink-100">
      <section className="p-5" aria-labelledby="ev-h">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h2 id="ev-h" className="label !text-brand">Evidence-grounded answer</h2><Badge tone={st.tone}>{st.label}</Badge></div>
        <ol className="space-y-3">{ask.claims.map((c, i) => (
          <li key={i} className="font-serif text-[17px] leading-relaxed" data-testid="claim">
            {c.text}{c.numbers.map((n) => <CitationChip key={n} n={n} active={activeN === n} onClick={onOpen} />)}
            <span className="ml-1 align-middle font-sans text-[10px] uppercase tracking-wide text-ink-300">{c.kind === 'source_extract' ? 'verbatim from source' : 'model synthesis'}{c.strength === 'partial' ? ' · partial support' : ''}</span></li>))}</ol>
        <p className="mt-3 text-xs text-ink-400">Every statement above is checked against the retrieved passage it cites. Click a number to inspect the exact source text.</p>
      </section>
      <section className="p-5" aria-labelledby="unc-h"><h2 id="unc-h" className="label mb-2 !text-saffron">Uncertainty &amp; limitations</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-700">{ask.limitations.map((l) => <li key={l}>{l}</li>)}</ul></section>
      {ask.pipeline.validation && <section className="flex flex-wrap gap-x-6 gap-y-1 bg-ink-50 px-5 py-3 text-xs text-ink-500">
        <span>Provider: <b>{ask.pipeline.provider}</b></span><span>Statements proposed → kept: <b>{ask.pipeline.validation.proposed} → {ask.pipeline.validation.kept}</b></span>
        <span>Invalid citation ids discarded: <b>{ask.pipeline.validation.invalid_citation_ids.length}</b></span><span>Retrieval: <b>{ask.pipeline.timings_ms.total} ms</b></span></section>}
    </div>);
}
export { Button };

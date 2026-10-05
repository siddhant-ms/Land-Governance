'use client';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import type { DocumentDetail } from '@sih/types';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { DOC_TYPE_LABEL, fmtDate } from '@/lib/format';
import SaveToWorkspace from '@/components/SaveToWorkspace';
import { Badge, Button, Card, DemoBadge, ErrorState, Notice, Skeleton } from '@/components/ui';

interface Related { related: { document_id: string; title: string; document_type: string; year: number | null; is_demo: boolean; similarity: number; shared_topics: string[] }[]; basis: string }
interface Ann { id: string; kind: string; text: string; created_at: string }

function Viewer() {
  const { id } = useParams<{ id: string }>();
  const chunk = useSearchParams().get('chunk');
  const { role } = useAuth();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [rel, setRel] = useState<Related | null>(null);
  const [anns, setAnns] = useState<Ann[]>([]);
  const [note, setNote] = useState('');
  const [err, setErr] = useState<unknown>(null);
  const cited = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api<DocumentDetail>(`/documents/${id}`).then(setDoc).catch(setErr);
    api<Related>(`/documents/${id}/related`).then(setRel).catch(() => {});
  }, [id, role]);
  useEffect(() => { if (can.review(role)) api<Ann[]>(`/documents/${id}/annotations`).then(setAnns).catch(() => {}); }, [id, role]);
  useEffect(() => { cited.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, [doc]);

  if (err) return <ErrorState error={err} />;
  if (!doc) return <Skeleton className="h-96" />;
  const annotate = async () => { await api(`/documents/${id}/annotations`, { body: { text: note, kind: 'comment', chunk_id: chunk } }); setNote(''); setAnns(await api<Ann[]>(`/documents/${id}/annotations`)); };
  let lastPage = 0;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
      <div className="min-w-0">
        <Link href="/research" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-400 hover:text-brand"><ArrowLeft className="h-3.5 w-3.5" />Research</Link>
        <div className="mb-2 flex flex-wrap items-center gap-2">{doc.is_demo && <DemoBadge label="DEMO DOCUMENT" />}<Badge>{DOC_TYPE_LABEL[doc.document_type]}</Badge>{doc.access_level !== 'public' && <Badge tone="alert">{doc.access_level}</Badge>}
          {doc.document_type === 'legal_text' && <Badge tone="saffron">Source material, not legal advice</Badge>}</div>
        <h1 className="text-3xl font-semibold leading-tight">{doc.title}</h1>
        <p className="mt-1 text-sm text-ink-500">{doc.organization} · {fmtDate(doc.publication_date)} · {doc.geography}</p>
        <div className="mt-6 space-y-4">
          {doc.chunks?.map((c) => {
            const pageHeader = c.page !== lastPage ? (lastPage = c.page, <p key={`p${c.page}`} className="label border-t border-ink-100 pt-3">Page {c.page}</p>) : null;
            const isCited = c.id === chunk;
            return (<div key={c.id}>{pageHeader}
              <div ref={isCited ? cited : undefined} id={c.id} className={isCited ? 'rounded-md border-l-4 border-brand bg-brand-50 p-3' : 'p-3'}>
                {c.section && <p className="label mb-1">{c.section}{isCited && <span className="ml-2 text-brand">· cited passage</span>}</p>}
                <p className="font-serif text-[15px] leading-relaxed text-ink-700">{c.text}</p></div></div>);
          })}
        </div>
      </div>
      <aside className="space-y-4">
        <Card className="p-4 text-sm"><p className="label mb-2">Provenance</p>
          <dl className="space-y-2"><div><dt className="text-xs text-ink-400">Authority</dt><dd>{doc.authority_level}</dd></div>
            <div><dt className="text-xs text-ink-400">Version</dt><dd>v{doc.version?.version_no} · {doc.version?.pages} pages</dd></div>
            <div><dt className="text-xs text-ink-400">SHA-256</dt><dd className="break-all font-mono text-[10px]">{doc.version?.content_hash}</dd></div>
            <div><dt className="text-xs text-ink-400">Extraction quality</dt><dd>{doc.extraction_quality != null ? `${Math.round(doc.extraction_quality * 100)}%` : '—'}</dd></div>
            <div><dt className="text-xs text-ink-400">Source URL</dt><dd>{doc.source_url && !doc.source_url.includes('example.org') ? <a className="inline-flex items-center gap-1 break-all text-brand underline" href={doc.source_url} target="_blank" rel="noreferrer noopener">Open<ExternalLink className="h-3 w-3" /></a> : <span className="text-ink-400">None (demo)</span>}</dd></div></dl>
          {doc.provenance_note && <div className="mt-3"><Notice>{doc.provenance_note}</Notice></div>}
          <div className="mt-3 flex flex-wrap gap-1">{doc.topics.map((t) => <Badge key={t}>{t}</Badge>)}</div>
          <div className="mt-4"><SaveToWorkspace item={{ item_type: 'document', ref_id: doc.id, title: doc.title, payload: { title: doc.title, organization: doc.organization, publication_date: doc.publication_date, is_demo: doc.is_demo, source_url: doc.source_url, document_id: doc.id } }} /></div></Card>
        {rel && rel.related.length > 0 && <Card className="p-4"><p className="label mb-2">Related documents</p>
          <ul className="space-y-3">{rel.related.map((r) => <li key={r.document_id}><Link prefetch={false} className="text-sm leading-snug hover:text-brand hover:underline" href={`/research/document/${r.document_id}`}>{r.title}</Link>
            <p className="text-xs text-ink-400">{DOC_TYPE_LABEL[r.document_type]} · {r.year}{r.shared_topics.length ? ` · shared: ${r.shared_topics.join(', ')}` : ''}</p></li>)}</ul><p className="mt-2 text-[11px] text-ink-300">{rel.basis}</p></Card>}
        {can.review(role) && <Card className="p-4"><p className="label mb-2">Expert annotations</p>
          <ul className="mb-3 space-y-2 text-sm">{anns.map((a) => <li key={a.id} className="rounded bg-ink-50 p-2"><Badge>{a.kind}</Badge> {a.text}</li>)}</ul>
          <textarea className="w-full rounded border border-ink-200 p-2 text-sm" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={chunk ? 'Annotate the cited passage…' : 'Add an annotation…'} />
          <Button size="sm" className="mt-2" disabled={note.trim().length < 3} onClick={annotate}>Add annotation</Button></Card>}
      </aside>
    </div>);
}
export default function DocumentPage() { return <Suspense fallback={<Skeleton className="h-96" />}><Viewer /></Suspense>; }

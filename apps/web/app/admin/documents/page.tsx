'use client';
import { Upload } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import type { DocumentDetail } from '@sih/types';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { DOC_TYPE_LABEL } from '@/lib/format';
import { AdminGate } from '@/components/AdminGate';
import { Badge, Button, Card, DemoBadge, ErrorState, Input, PageHeader, Select } from '@/components/ui';

type Row = DocumentDetail & { job: { status: string; stage: string; error: string; stats: { chunks?: number; warnings?: string[] } } | null };
const TONE = { approved: 'brand', pending_review: 'saffron', failed: 'alert', rejected: 'alert', processing: 'neutral' } as const;

export default function AdminDocs() {
  const { role } = useAuth();
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState({ title: '', organization: '', document_type: 'policy_report', state_code: '', publication_date: '' });
  const file = useRef<HTMLInputElement>(null);
  const load = () => api<Row[]>('/admin/documents').then(setRows).catch(setErr);
  useEffect(() => { if (can.review(role)) { load(); const t = setInterval(load, 4000); return () => clearInterval(t); } }, [role]); // eslint-disable-line react-hooks/exhaustive-deps
  const upload = async (e: React.FormEvent) => {
    e.preventDefault(); const f = file.current?.files?.[0]; if (!f) return; setBusy(true); setErr(null);
    const fd = new FormData(); fd.append('file', f);
    fd.append('metadata', JSON.stringify(Object.fromEntries(Object.entries(meta).filter(([, v]) => v))));
    try { await api('/admin/documents/ingest', { form: fd }); if (file.current) file.current.value = ''; load(); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  const review = async (id: string, act: 'approve' | 'reject') => { try { await api(`/admin/documents/${id}/${act}`, { method: 'POST' }); load(); } catch (x) { setErr(x); } };
  return (
    <AdminGate>
      <PageHeader eyebrow="Administration" title="Evidence documents" sub="Uploads are validated, extracted, chunked and embedded in the background; they become searchable only after approval." />
      {err ? <div className="mb-4"><ErrorState error={err} /></div> : null}
      {can.admin(role) && <Card className="mb-6 p-5"><form onSubmit={upload} className="grid gap-3 md:grid-cols-3">
        <div className="md:col-span-3"><input ref={file} type="file" accept=".pdf,.txt,.md" required aria-label="Document file" className="text-sm" /><span className="ml-2 text-xs text-ink-400">PDF, TXT or Markdown, up to 15 MB</span></div>
        <Input placeholder="Title (optional, else from file)" value={meta.title} onChange={(e) => setMeta({ ...meta, title: e.target.value })} /><Input placeholder="Organization" value={meta.organization} onChange={(e) => setMeta({ ...meta, organization: e.target.value })} />
        <Select value={meta.document_type} onChange={(e) => setMeta({ ...meta, document_type: e.target.value })}>{Object.entries(DOC_TYPE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select>
        <Input placeholder="State code (e.g. KA)" value={meta.state_code} onChange={(e) => setMeta({ ...meta, state_code: e.target.value.toUpperCase() })} /><Input placeholder="Publication date (YYYY-MM-DD)" value={meta.publication_date} onChange={(e) => setMeta({ ...meta, publication_date: e.target.value })} />
        <Button disabled={busy}><Upload className="h-4 w-4" />{busy ? 'Uploading…' : 'Upload & ingest'}</Button></form></Card>}
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-ink-50 text-left"><tr>{['Document', 'Type', 'Status', 'Ingestion', 'Actions'].map((h) => <th key={h} className="label px-4 py-2">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-ink-100">{rows.map((d) => (<tr key={d.id}><td className="max-w-xs px-4 py-3"><Link prefetch={false} className="font-medium hover:text-brand hover:underline" href={`/research/document/${d.id}`}>{d.title}</Link><p className="text-xs text-ink-400">{d.organization} {d.is_demo && <DemoBadge />} {d.access_level !== 'public' && <Badge tone="alert">{d.access_level}</Badge>}</p></td>
          <td className="px-4 py-3 text-xs">{DOC_TYPE_LABEL[d.document_type]}</td><td className="px-4 py-3"><Badge tone={TONE[d.status as keyof typeof TONE] ?? 'neutral'}>{d.status.replace('_', ' ')}</Badge></td>
          <td className="px-4 py-3 text-xs text-ink-500">{d.job ? `${d.job.stage}${d.job.stats.chunks ? ` · ${d.job.stats.chunks} chunks` : ''}${d.job.error ? ` · ${d.job.error}` : ''}` : '—'}{d.extraction_quality != null && d.extraction_quality < 0.5 && <Badge tone="saffron" className="ml-1">low quality</Badge>}</td>
          <td className="px-4 py-3"><div className="flex gap-1.5">{d.status === 'pending_review' && <><Button size="sm" onClick={() => review(d.id, 'approve')}>Approve</Button><Button size="sm" variant="secondary" onClick={() => review(d.id, 'reject')}>Reject</Button></>}</div></td></tr>))}</tbody></table></Card>
    </AdminGate>);
}

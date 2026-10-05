'use client';
import { Download, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { Workspace, WorkspaceItem } from '@sih/types';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { fmtNum, fmtPct } from '@/lib/format';
import { Badge, Button, Card, DemoBadge, EmptyState, ErrorState, LoginGate, PageHeader, Skeleton } from '@/components/ui';

const GROUPS: [string, string][] = [['answer', 'Answers'], ['citation', 'Saved evidence'], ['document', 'Documents'], ['search', 'Searches'], ['map', 'Maps'], ['scenario', 'Scenarios'], ['note', 'Notes']];

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { role, loading } = useAuth();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [note, setNote] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api<Workspace>(`/workspaces/${id}`).then(setWs).catch(setErr);
  useEffect(() => { if (!loading && can.workspace(role)) load(); }, [id, role, loading]); // eslint-disable-line react-hooks/exhaustive-deps
  if (loading) return <Skeleton className="h-40" />;
  if (!can.workspace(role)) return <LoginGate what="Viewing a workspace" />;
  if (err) return <ErrorState error={err} />;
  if (!ws) return <Skeleton className="h-64" />;
  const remove = async (i: WorkspaceItem) => { await api(`/workspaces/${id}/items/${i.id}`, { method: 'DELETE' }); load(); };
  const addNote = async () => { await api(`/workspaces/${id}/items`, { body: { item_type: 'note', title: 'Note', note } }); setNote(''); load(); };
  const exportBrief = async () => {
    const b = await api<{ filename: string; content: string }>(`/workspaces/${id}/brief`);
    const url = URL.createObjectURL(new Blob([b.content], { type: 'text/markdown' })); const a = document.createElement('a'); a.href = url; a.download = b.filename; a.click(); URL.revokeObjectURL(url); setMsg('Brief downloaded.');
  };
  const items = ws.items ?? [];
  return (
    <div>
      <PageHeader eyebrow="Research Workspace" title={ws.title} sub={ws.research_question || ws.description} actions={<Button onClick={exportBrief}><Download className="h-4 w-4" />Export evidence brief</Button>} />
      {msg && <p role="status" className="mb-4 text-sm text-brand">{msg}</p>}
      {items.length === 0 && <EmptyState title="This workspace is empty">Save citations, scenarios, maps or notes from the rest of the platform.</EmptyState>}
      <div className="space-y-8">{GROUPS.map(([type, label]) => { const its = items.filter((i) => i.item_type === type); if (!its.length) return null; return (
        <section key={type}><h2 className="label mb-2">{label} ({its.length})</h2>
          <ul className="space-y-3">{its.map((i) => (<li key={i.id}><Card className="flex items-start justify-between gap-3 p-4"><div className="min-w-0">{renderItem(i)}</div>
            <button aria-label={`Remove ${i.title || i.item_type}`} onClick={() => remove(i)} className="rounded p-1.5 text-ink-300 hover:bg-alert-50 hover:text-alert"><Trash2 className="h-4 w-4" /></button></Card></li>))}</ul></section>); })}</div>
      <Card className="mt-8 p-4"><label className="label" htmlFor="note">Add note</label><textarea id="note" rows={2} className="mt-1 w-full rounded border border-ink-200 p-2 text-sm" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button className="mt-2" size="sm" disabled={note.trim().length < 2} onClick={addNote}>Save note</Button></Card>
    </div>);
}

function renderItem(i: WorkspaceItem) {
  const p = i.payload;
  switch (i.item_type) {
    case 'citation': return (<><p className="flex flex-wrap items-center gap-2 font-medium">{p.title}{p.is_demo && <DemoBadge />}</p><p className="text-xs text-ink-400">{p.organization} · p.{p.page} · {p.section}</p>
      <blockquote className="mt-2 border-l-4 border-brand bg-paper p-2 font-serif text-sm text-ink-700">{String(p.passage ?? '').slice(0, 320)}…</blockquote>
      {p.document_id && <Link prefetch={false} className="mt-1 inline-block text-xs text-brand underline" href={`/research/document/${p.document_id}${p.chunk_id ? `?chunk=${p.chunk_id}` : ''}`}>Open in document</Link>}</>);
    case 'answer': return (<><p className="font-medium">{p.question ?? i.title}</p><ul className="mt-1 list-disc pl-5 text-sm text-ink-700">{(p.claims ?? []).slice(0, 4).map((c: { text: string; numbers: number[] }, k: number) => <li key={k}>{c.text} {c.numbers.map((n) => `[${n}]`).join('')}</li>)}</ul></>);
    case 'scenario': return (<><Link href={`/simulation/${i.ref_id}${p.run_id ? `?run=${p.run_id}` : ''}`} className="font-medium hover:text-brand hover:underline">{i.title}</Link>
      <p className="text-xs text-ink-400">{p.model_name} v{p.model_version} · <span className="font-mono">{String(p.input_hash ?? '').slice(0, 12)}</span></p>
      <ul className="mt-1 grid gap-x-6 text-sm sm:grid-cols-2">{(p.outputs ?? []).slice(0, 5).map((o: { label: string; baseline: number; scenario: number; delta_pct: number | null }) => <li key={o.label}>{o.label}: {fmtNum(o.baseline)} → <b>{fmtNum(o.scenario)}</b> <span className="text-ink-400">({fmtPct(o.delta_pct)})</span></li>)}</ul></>);
    case 'search': return <><p className="font-medium">{p.query}</p><Link className="text-xs text-brand underline" href={`/research/results?q=${encodeURIComponent(String(p.query))}`}>Re-run search</Link></>;
    case 'map': return <><p className="font-medium">{i.title}</p><Link className="text-xs text-brand underline" href={`/map?indicator=${p.indicator}`}>Open map</Link> {p.is_demo && <DemoBadge />}</>;
    case 'document': return <><Link prefetch={false} className="font-medium hover:text-brand hover:underline" href={`/research/document/${p.document_id ?? i.ref_id}`}>{i.title}</Link> {p.is_demo && <DemoBadge />}</>;
    default: return <><Badge>note</Badge><p className="mt-1 text-sm">{i.note}</p></>;
  }
}

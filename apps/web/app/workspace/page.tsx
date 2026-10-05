'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { Workspace } from '@sih/types';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { Button, Card, EmptyState, ErrorState, Input, LoginGate, PageHeader, Skeleton } from '@/components/ui';

export default function Workspaces() {
  const { role, loading } = useAuth();
  const [list, setList] = useState<Workspace[] | null>(null);
  const [title, setTitle] = useState('');
  const [q, setQ] = useState('');
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { if (!loading && can.workspace(role)) api<Workspace[]>('/workspaces').then(setList).catch(setErr); }, [role, loading]);
  if (loading) return <Skeleton className="h-40" />;
  if (!can.workspace(role)) return <div><PageHeader title="Research workspace" /><LoginGate what="Saving research" /></div>;
  const create = async () => { const w = await api<Workspace>('/workspaces', { body: { title, research_question: q } }); setList([w, ...(list ?? [])]); setTitle(''); setQ(''); };
  return (
    <div>
      <PageHeader eyebrow="Research Workspace" title="My workspaces" sub="Collect evidence, citations, searches, maps, scenarios and notes; export an evidence brief with provenance." />
      <Card className="mb-6 grid gap-2 p-4 sm:grid-cols-[1fr_1.5fr_auto]"><Input aria-label="Workspace title" placeholder="Workspace title" value={title} onChange={(e) => setTitle(e.target.value)} /><Input aria-label="Research question" placeholder="Research question (optional)" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button disabled={title.trim().length < 2} onClick={create}>Create workspace</Button></Card>
      {err ? <ErrorState error={err} /> : !list ? <Skeleton className="h-40" /> : list.length === 0 ? <EmptyState title="No workspaces yet">Save an answer or scenario from anywhere in the platform.</EmptyState> : (
        <ul className="grid gap-4 md:grid-cols-2">{list.map((w) => (<li key={w.id}><Link href={`/workspace/${w.id}`} className="card block p-5 transition hover:border-brand/40"><h2 className="font-serif text-xl font-semibold">{w.title}</h2>
          {w.research_question && <p className="mt-1 line-clamp-2 text-sm text-ink-500">{w.research_question}</p>}
          <p className="mt-3 text-xs text-ink-400">{Object.entries(w.counts).map(([k, v]) => `${v} ${k}${v > 1 ? 's' : ''}`).join(' · ') || 'Empty'}</p></Link></li>))}</ul>)}
    </div>);
}

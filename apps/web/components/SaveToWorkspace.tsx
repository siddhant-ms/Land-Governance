'use client';
import { BookmarkPlus, Check } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import type { Workspace } from '@sih/types';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { Button } from './ui';

export interface SaveItem { item_type: string; ref_id?: string | null; title: string; payload?: Record<string, unknown>; note?: string }

export default function SaveToWorkspace({ item, size = 'md', label = 'Save to workspace' }: { item: SaveItem; size?: 'sm' | 'md'; label?: string }) {
  const { role } = useAuth();
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<Workspace[] | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [savedTo, setSavedTo] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (!can.workspace(role)) return <Link href="/login" className="text-xs text-brand underline">Sign in to save</Link>;
  const toggle = async () => { setOpen(!open); setErr(null); if (!list) setList(await api<Workspace[]>('/workspaces').catch(() => [])); };
  const save = async (id: string, title: string) => {
    try { await api(`/workspaces/${id}/items`, { body: item }); setSavedTo(title); setOpen(false); } catch (e) { setErr(e instanceof Error ? e.message : 'Could not save'); }
  };
  const create = async () => {
    if (newTitle.trim().length < 2) return;
    try { const w = await api<Workspace>('/workspaces', { body: { title: newTitle.trim() } }); await save(w.id, w.title); } catch (e) { setErr(e instanceof Error ? e.message : 'Could not create'); }
  };
  return (
    <div className="relative inline-block">
      <Button variant="secondary" size={size} onClick={toggle} aria-expanded={open}>{savedTo ? <Check className="h-3.5 w-3.5 text-brand" /> : <BookmarkPlus className="h-3.5 w-3.5" />}{savedTo ? `Saved to “${savedTo}”` : label}</Button>
      {open && <div className="absolute right-0 z-30 mt-1 w-72 rounded-md border border-ink-100 bg-white p-3 shadow-xl">
        <p className="label mb-2">Choose workspace</p>
        <ul className="max-h-40 space-y-1 overflow-auto">{(list ?? []).map((w) => <li key={w.id}><button className="w-full rounded px-2 py-1.5 text-left text-sm hover:bg-ink-50" onClick={() => save(w.id, w.title)}>{w.title}</button></li>)}
          {list && list.length === 0 && <li className="px-2 text-xs text-ink-400">No workspaces yet.</li>}</ul>
        <div className="mt-2 flex gap-2 border-t border-ink-100 pt-2"><input className="min-w-0 flex-1 rounded border border-ink-200 px-2 py-1 text-sm" placeholder="New workspace title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <Button size="sm" onClick={create}>Create</Button></div>
        {err && <p role="alert" className="mt-2 text-xs text-alert">{err}</p>}</div>}
    </div>);
}

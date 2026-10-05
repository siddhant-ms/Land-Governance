'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { AdminGate } from '@/components/AdminGate';
import { Badge, Button, Card, DemoBadge, ErrorState, Input, PageHeader } from '@/components/ui';

interface M { id: string; key: string; name: string; version: string; status: string; review_status: string; review_notes: string; coefficients: Record<string, number>; coefficient_provenance: Record<string, string> }

export default function AdminModels() {
  const { role } = useAuth();
  const [models, setModels] = useState<M[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [edit, setEdit] = useState<Record<string, Record<string, string>>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const load = () => api<M[]>('/admin/models').then(setModels).catch(setErr);
  useEffect(() => { if (can.review(role)) load(); }, [role]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async (m: M) => {
    const changed = Object.fromEntries(Object.entries(edit[m.id] ?? {}).filter(([k, v]) => v !== '' && Number(v) !== m.coefficients[k]).map(([k, v]) => [k, Number(v)]));
    try { await api(`/admin/models/${m.id}`, { method: 'PATCH', body: { coefficients: changed, change_note: notes[m.id] ?? '' } }); setEdit({}); load(); } catch (e) { setErr(e); }
  };
  const review = async (m: M, status: string) => { try { await api(`/admin/models/${m.id}/review`, { body: { status, notes: notes[m.id] || 'Reviewed via console' } }); load(); } catch (e) { setErr(e); } };
  return (
    <AdminGate>
      <PageHeader eyebrow="Administration" title="Simulation models" sub="Coefficient edits never mutate a version in place: saving creates a new version and deprecates the old one. Experts record assumption reviews." />
      {err ? <div className="mb-4"><ErrorState error={err} /></div> : null}
      <div className="space-y-6">{models.map((m) => (<Card key={m.id} className="p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-serif text-lg font-semibold">{m.name}</h2>
        <p className="mt-1 flex items-center gap-2 text-xs text-ink-400"><Badge>v{m.version}</Badge><Badge tone={m.status === 'active' ? 'brand' : 'neutral'}>{m.status}</Badge><Badge tone="saffron">review: {m.review_status.replace(/_/g, ' ')}</Badge><DemoBadge label="DEMO CALIBRATION" /></p></div></div>
        {m.review_notes && <p className="mt-2 text-sm text-ink-500">Review notes: {m.review_notes}</p>}
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(m.coefficients).map(([k, v]) => (<label key={k} className="text-xs text-ink-500"><span className="font-mono">{k}</span>
          <Input type="number" step="any" disabled={!can.admin(role) || m.status !== 'active'} defaultValue={v} onChange={(e) => setEdit({ ...edit, [m.id]: { ...(edit[m.id] ?? {}), [k]: e.target.value } })} className="mt-1" />
          <span className="mt-0.5 block text-[10px] leading-tight text-ink-300">{m.coefficient_provenance[k]}</span></label>))}</div>
        {m.status === 'active' && <div className="mt-4 flex flex-wrap items-center gap-2"><Input className="max-w-sm" placeholder="Change / review note (required)" value={notes[m.id] ?? ''} onChange={(e) => setNotes({ ...notes, [m.id]: e.target.value })} />
          {can.admin(role) && <Button size="sm" disabled={(notes[m.id] ?? '').length < 5} onClick={() => save(m)}>Save as new version</Button>}
          <Button size="sm" variant="secondary" disabled={(notes[m.id] ?? '').length < 5} onClick={() => review(m, 'approved_for_demo')}>Mark reviewed</Button><Button size="sm" variant="secondary" disabled={(notes[m.id] ?? '').length < 5} onClick={() => review(m, 'needs_changes')}>Needs changes</Button></div>}
      </Card>))}</div>
    </AdminGate>);
}

'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { AdminGate } from '@/components/AdminGate';
import { Badge, Card, ErrorState, PageHeader, Select } from '@/components/ui';

interface Ev { id: string; action: string; actor: string; actor_role: string; entity_type: string; entity_id: string; ip: string; meta: Record<string, unknown>; created_at: string }
const ACTIONS = ['USER_LOGIN', 'SEARCH_EXECUTED', 'AI_QUERY_EXECUTED', 'DOCUMENT_UPLOADED', 'DOCUMENT_APPROVED', 'DOCUMENT_VIEWED', 'SCENARIO_CREATED', 'SCENARIO_RUN', 'SCENARIO_EXPORTED', 'MODEL_UPDATED', 'USER_ROLE_CHANGED', 'RESTRICTED_DOCUMENT_DENIED'];

export default function Audit() {
  const { role } = useAuth();
  const [data, setData] = useState<{ total: number; events: Ev[] } | null>(null);
  const [action, setAction] = useState('');
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { if (can.admin(role)) api<{ total: number; events: Ev[] }>(`/admin/audit?limit=100${action ? `&action=${action}` : ''}`).then(setData).catch(setErr); }, [role, action]);
  return (
    <AdminGate need="admin">
      <PageHeader eyebrow="Administration" title="Audit log" sub="Append-only record of security-relevant actions. Search text is stored only as a short hash." actions={<Select aria-label="Filter action" value={action} onChange={(e) => setAction(e.target.value)}><option value="">All actions</option>{ACTIONS.map((a) => <option key={a}>{a}</option>)}</Select>} />
      {err ? <ErrorState error={err} /> : null}
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-ink-50 text-left"><tr>{['Time', 'Action', 'Actor', 'Entity', 'IP', 'Metadata'].map((h) => <th key={h} className="label px-4 py-2">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-ink-100">{data?.events.map((e) => (<tr key={e.id}><td className="whitespace-nowrap px-4 py-2 text-xs tabular-nums">{new Date(e.created_at).toLocaleString('en-IN')}</td><td className="px-4 py-2"><Badge>{e.action}</Badge></td>
          <td className="px-4 py-2 text-xs">{e.actor}<span className="block text-ink-400">{e.actor_role}</span></td><td className="px-4 py-2 text-xs">{e.entity_type} <span className="font-mono text-ink-400">{e.entity_id.slice(0, 8)}</span></td><td className="px-4 py-2 text-xs">{e.ip}</td>
          <td className="max-w-xs truncate px-4 py-2 font-mono text-[10px] text-ink-500" title={JSON.stringify(e.meta)}>{JSON.stringify(e.meta)}</td></tr>))}</tbody></table>
        {data && <p className="px-4 py-2 text-xs text-ink-400">{data.total} events total · showing latest {data.events.length}</p>}</Card>
    </AdminGate>);
}

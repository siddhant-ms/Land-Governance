'use client';
import { FileText, ScrollText, SlidersHorizontal, Users } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { can, useAuth } from '@/lib/auth';
import { AdminGate } from '@/components/AdminGate';
import { Badge, Card, ErrorState, PageHeader, Select } from '@/components/ui';

interface U { id: string; name: string; email: string; role: string; status: string }
export default function Admin() {
  const { role } = useAuth();
  const [users, setUsers] = useState<U[]>([]);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { if (can.admin(role)) api<U[]>('/admin/users').then(setUsers).catch(setErr); }, [role]);
  const setRole = async (u: U, r: string) => { try { await api(`/admin/users/${u.id}/role`, { method: 'PATCH', body: { role: r } }); setUsers(users.map((x) => (x.id === u.id ? { ...x, role: r } : x))); } catch (e) { setErr(e); } };
  return (
    <AdminGate>
      <PageHeader eyebrow="Administration" title="Admin console" />
      <div className="mb-8 grid gap-4 sm:grid-cols-3">{[{ href: '/admin/documents', t: 'Documents', d: 'Ingest, review and approve evidence', I: FileText }, { href: '/admin/models', t: 'Models', d: 'Coefficients, versions, expert review', I: SlidersHorizontal }, { href: '/admin/audit', t: 'Audit log', d: 'Who did what, when', I: ScrollText }].map(({ href, t, d, I }) => (
        <Link key={href} href={href} className="card p-5 transition hover:border-brand/40"><I className="mb-2 h-5 w-5 text-brand" /><h2 className="font-serif text-lg font-semibold">{t}</h2><p className="text-sm text-ink-500">{d}</p></Link>))}</div>
      {can.admin(role) && <Card className="p-5"><h2 className="mb-3 flex items-center gap-2 font-serif text-lg font-semibold"><Users className="h-4 w-4" />Users &amp; roles</h2>{err ? <ErrorState error={err} /> : null}
        <table className="w-full text-sm"><tbody className="divide-y divide-ink-100">{users.map((u) => (<tr key={u.id}><td className="py-2">{u.name}<p className="text-xs text-ink-400">{u.email}</p></td><td className="py-2 text-right">
          <Select aria-label={`Role for ${u.email}`} value={u.role} onChange={(e) => setRole(u, e.target.value)}>{['researcher', 'analyst', 'expert', 'admin'].map((r) => <option key={r}>{r}</option>)}</Select></td></tr>))}</tbody></table>
        <p className="mt-2 text-xs text-ink-400">Role changes are written to the audit log. Admins cannot change their own role.</p></Card>}
      {!can.admin(role) && <Badge tone="saffron">Expert view: document review and model review only</Badge>}
    </AdminGate>);
}

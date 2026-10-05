'use client';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useAuth } from '@/lib/auth';
import { Badge, Button, Card, Input, PageHeader } from '@/components/ui';

const DEMO = [
  ['researcher@demo.sih', 'Researcher', 'Ask, save workspaces, run & save scenarios'],
  ['analyst@demo.sih', 'Analyst / Official', '+ protected datasets, scenario export'],
  ['expert@demo.sih', 'Expert', '+ approve evidence, annotate, review models'],
  ['admin@demo.sih', 'Admin', '+ ingestion, users, models, audit log'],
] as const;

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await login(email, pw); router.push('/'); } catch (x) { setErr(x instanceof Error ? x.message : 'Sign-in failed'); } finally { setBusy(false); }
  };
  return (
    <div className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
      <div><PageHeader title="Sign in" sub="Public visitors can search the public corpus and view public maps without an account." />
        <Card className="p-5"><form onSubmit={submit} className="space-y-3">
          <label className="block text-sm">Email<Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" className="mt-1" /></label>
          <label className="block text-sm">Password<Input type="password" required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" className="mt-1" /></label>
          {err && <p role="alert" className="text-sm text-alert">{err}</p>}
          <Button disabled={busy} className="w-full">{busy ? 'Signing in…' : 'Sign in'}</Button></form></Card></div>
      <div className="pt-16"><Card className="p-5"><div className="mb-3 flex items-center gap-2"><h2 className="font-serif text-lg font-semibold">Demo accounts</h2><Badge tone="saffron">Demo only</Badge></div>
        <p className="mb-3 text-xs text-ink-500">Password for all: <code className="rounded bg-ink-100 px-1">Demo@12345</code></p>
        <ul className="space-y-2">{DEMO.map(([em, name, desc]) => (<li key={em}><button className="w-full rounded-md border border-ink-100 p-2.5 text-left hover:bg-brand-50" onClick={() => { setEmail(em); setPw('Demo@12345'); }}>
          <span className="block text-sm font-medium">{name}</span><span className="block text-xs text-ink-400">{em} — {desc}</span></button></li>))}</ul></Card></div>
    </div>);
}
